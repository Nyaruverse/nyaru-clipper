from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from sqlmodel import Session, select

from app.arctime.subtitle_inputs import ExportRequest
from app.arctime.subtitle_templates import TemplateStore
from app.models_unified import OperationStep, UnifiedOperation, UnifiedPublication
from app.services.task_execution import Execution, Executor
from app.services.task_operations import bind_task, enqueue_operation, set_admissions
from app.services.task_publication import Publisher
from app.services.unified_exports import export_result
from test_unified_operations import database
from unification_media import build_media
from unified_edit_fixture import make_editor_fixture


@pytest.mark.skipif(sys.platform != 'darwin', reason='Uses the pinned macOS reference generator')
def test_shared_executor_burn_publishes_document_set_and_reuses_verified_product(tmp_path: Path) -> None:
    bundle = build_media(tmp_path / 'reference')
    fixture = make_editor_fixture(tmp_path / 'candidate', bundle)
    style = TemplateStore(fixture.editor).load_defaults()
    document = fixture.artifacts.document(style)
    document = document.model_copy(update={'cues': [document.cues[0].model_copy(update={'text': 'Unified fixture'})]})
    request = ExportRequest(kind='burn', video='clip-001.mp4', style=style, document=document)
    engine = database(tmp_path)
    with Session(engine) as session:
        source = fixture.artifacts.source
        bind_task(session, source.source_instance_id, source.legacy_id, source.fingerprint, origin='native')
        for _ in range(2):
            enqueue_operation(session, source.task_id, 'export', {'input': request.model_dump(mode='json'), 'config': {}})
        set_admissions(session, paused=False)
        session.commit()
    results = []

    def render(execution: Execution) -> None:
        results.append(export_result(execution, fixture.artifacts, request, TemplateStore(fixture.editor)))

    executor = Executor(engine, fixture.editor, tmp_path / 'host-guard')
    encodes = []
    recording = [True]

    def capture(event: str, args: tuple) -> None:
        if recording[0] and event == 'subprocess.Popen' and '-progress' in args[1]:
            encodes.append(args[1])

    sys.addaudithook(capture)
    try:
        assert executor.iteration(render) is not None
        assert executor.iteration(render) is not None
    finally:
        recording[0] = False
    assert len(encodes) == 1
    with Session(engine) as session:
        assert [row.state for row in session.exec(select(UnifiedOperation)).all()] == ['succeeded', 'succeeded']
        assert len(session.exec(select(UnifiedPublication)).all()) == 1
        assert len([step for step in session.exec(select(OperationStep)).all() if step.reused_publication_id]) == 1
    assert len(results) == 2 and results[0] == results[1]
    receipt = Publisher(engine, fixture.editor).registered(results[0])
    assert {member.role for member in receipt.outputs} == {'product', 'document'}
    saved_document = next(member for member in receipt.outputs if member.role == 'document')
    assert json.loads((fixture.editor / saved_document.target).read_bytes())['cues'][0]['text'] == 'Unified fixture'
    assert fixture.current_source_hashes() == fixture.source_hashes
