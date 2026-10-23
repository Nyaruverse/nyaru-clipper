from pathlib import Path

import pytest
from pydantic import SecretStr
from sqlmodel import Session

from app.api.schemas.operations import TranslateOperation
from app.arctime.subtitle_style import SubtitleStyle
from app.models_unified import UnifiedOperation
from app.services.task_artifacts import resolve_workstation
from app.services.task_documents import Documents
from app.services.task_execution import Execution, Executor
from app.services.task_operations import bind_task, enqueue_operation, retry_operation, set_admissions
from app.services.unified_translation import translate_document
from test_unified_artifacts import frozen_source
from test_unified_operations import database


@pytest.mark.parametrize('failure', [False, True])
def test_translation_preserves_edits_and_reuses_committed_result_after_document_commit(tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch, failure: bool) -> None:
    from app.arctime import subtitle_encoding
    monkeypatch.setattr(subtitle_encoding, 'video_metadata', lambda path: (1280, 720, 30.))
    context = resolve_workstation(frozen_source(tmp_path))
    engine = database(tmp_path)
    output = tmp_path / 'output'
    documents = Documents(engine, output)
    with Session(engine) as session:
        bind_task(session, context.source.source_instance_id, context.source.legacy_id, 'generation', origin='native')
        session.commit()
    base = context.document(SubtitleStyle())
    edited = base.model_copy(update={'cues': [base.cues[0].model_copy(update={'text': '保存的编辑'})]})
    document = documents.save(context.source.task_id, edited, base=base)
    request = TranslateOperation(kind='translate', task_id=context.source.task_id, source_language='zh',
        target_language='ja', provider='hf', model='offline-model', document_revision=1)
    with Session(engine) as session:
        operation = enqueue_operation(session, context.source.task_id, 'translate', {})
        identifier = operation.id
        set_admissions(session, paused=False)
        session.commit()
    calls, faults = [], []

    def provider(segments):
        calls.append([segment.text for segment in segments])
        return ['保存した編集' for segment in segments]

    def crash(point: str) -> None:
        if failure and point == 'committed' and not faults:
            faults.append(1)
            raise OSError('injected interruption after document commit')

    documents.fault = crash

    def run(execution: Execution) -> None:
        translate_document(execution, context, request, document, documents, key=SecretStr(''), local_provider=provider)

    executor = Executor(engine, output, tmp_path / 'guard')
    executor.iteration(run)
    if failure:
        with Session(engine) as session:
            assert session.get(UnifiedOperation, identifier).state == 'failed'
            retry_operation(session, identifier)
            session.commit()
        executor.iteration(run)
    assert calls == [['保存的编辑']]
    saved = Documents(engine, output).load(context.source.task_id, base)
    assert saved.revision == 2 and saved.cues[0].text == '保存的编辑'
    assert saved.cues[0].translation == '保存した編集'
    with Session(engine) as session:
        assert session.get(UnifiedOperation, identifier).state == 'succeeded'
