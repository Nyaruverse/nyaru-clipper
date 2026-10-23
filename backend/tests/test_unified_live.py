from __future__ import annotations

import json
import shutil
import threading
from pathlib import Path
from uuid import uuid4

import pytest
from sqlmodel import Session, select

from app.arctime.companion_models import JobInput
from app.arctime.subtitle_style import SubtitleStyle
from app.arctime.subtitle_templates import StyleTemplate, TemplateStore
from app.models_unified import OperationAttempt, OperationStep, UnifiedOperation, UnifiedPublication
from app.services.cpp_live import process_cpp_live
from app.services.cpp_recording import CppConfiguration
from app.services.task_execution import Execution, Executor, ExternalOutcomeUnknown
from app.services.task_operations import bind_task, enqueue_operation, set_admissions
from app.services.task_publication import Publisher
from app.services.unified_files import file_sha256
from test_saozi_live import Adapter, Capture, Selector, recording
from test_unified_operations import database


@pytest.mark.parametrize('translation_failure,style_failure', [(False, False), (True, False), (False, True)])
def test_live_children_publish_while_parent_runs_without_claiming_another_slot(tmp_path: Path, recording,
        monkeypatch: pytest.MonkeyPatch, translation_failure: bool, style_failure: bool) -> None:
    source_directory, sources = recording
    engine = database(tmp_path)
    with Session(engine) as session:
        first = bind_task(session, uuid4(), 'live', 'g', origin='native')
        operation = enqueue_operation(session, first.task_id, 'process_live', {})
        identifier, task_id = operation.id, first.task_id
        second = bind_task(session, uuid4(), 'next-recording', 'g', origin='native')
        waiting = enqueue_operation(session, second.task_id, 'process_recording', {})
        waiting_id = waiting.id
        set_admissions(session, paused=False)
        session.commit()
    output, guard = tmp_path / 'tasks', tmp_path / 'guard'
    model = tmp_path / 'frozen-model-identity'
    model.write_bytes(b'fixture identity only; no inference')
    configuration = CppConfiguration(model=model, model_sha256=file_sha256(model), threads=1)
    from app.arctime.unified_host import NativeHost
    host = NativeHost(engine, task_root=output, settings_root=tmp_path / 'settings',
        credential_root=tmp_path / 'private', guard_root=guard, model=model)
    if style_failure:
        from app.services.task_execution import WorkflowFailure
        def fail_style(*args, **kwargs):
            raise WorkflowFailure('injected_style_failure')
        monkeypatch.setattr('app.services.live_publication.export_result', fail_style)
    template = StyleTemplate(id='default', name='Frozen style', style=SubtitleStyle())
    observed, translation_calls, bilingual_observed = [], [], []

    class FrozenAdapter(Adapter):
        def identity(self):
            return {'engine': 'fixture', 'language': 'ja'}

    def run(execution: Execution) -> None:
        directory = execution.staging('workflow') / execution.task_id
        target = directory / 'capture-0000'
        target.mkdir(parents=True)
        paths = []
        for index, source in enumerate(sources[:8]):
            path = target / f'chunk-{index:05d}.ts'
            shutil.copyfile(source, path)
            paths.append(path)
        (target / 'closed.csv').write_text(''.join(f'{path.name},0,20\n' for path in paths))

        class CheckedCapture(Capture):
            def chunks(self):
                for path in super().chunks():
                    yield path
                    with Session(engine) as session:
                        committed = session.exec(select(UnifiedPublication).where(UnifiedPublication.state == 'committed')).all()
                        products = [row.id for row in committed if any(member.role == 'product' for member in Publisher(engine, output).registered(row.id).outputs)]
                        if products or (style_failure and committed):
                            assert session.get(UnifiedOperation, identifier).state == 'running'
                            assert session.get(UnifiedOperation, waiting_id).attempt == 0
                            assert len(session.exec(select(OperationAttempt)).all()) == 1
                            observed.append(len(committed) if style_failure else len(products))
                            from app.arctime.native_live import clips, file
                            for clip in clips(host, task_id):
                                if clip.bilingual_publication_id:
                                    assert '译文' in file(host, task_id, f'clip-{clip.clip_index:03d}.ja-zh.srt').read_text()
                                    assert host.context(task_id) is None
                                    bilingual_observed.append(clip.clip_index)
                    assert Executor(engine, output, guard).iteration(lambda child: pytest.fail('live child claimed another slot')) is None

        def translate(path: Path, final: bool):
            translation_calls.append(final)
            if translation_failure:
                raise ExternalOutcomeUnknown()
            job = json.loads((path / 'job.json').read_bytes())
            artifacts = {}
            for name in ['subtitles.srt', *(clip['subtitles'] for clip in job['completed_clips'])]:
                from app.arctime import media
                from app.services.subtitles import render_bilingual_srt
                cues = media.read_subtitles(path / name)
                bilingual = path / (Path(name).stem + '.ja-zh.srt')
                bilingual.write_text(render_bilingual_srt(cues, ['译文' for cue in cues]))
                artifacts[bilingual.name] = file_sha256(bilingual)
            (path / 'translation.json').write_text(json.dumps({'state': 'completed' if final else 'partial', 'artifacts': artifacts}))
            return {clip['video'] for clip in job['completed_clips']}

        process_cpp_live(execution, JobInput(url='https://live.bilibili.com/12345', saozi=True, live=True, language='ja'),
            configuration, selector=Selector(), templates=TemplateStore(tmp_path / 'settings'), stop=threading.Event(),
            translate=translate, template=template, capture=CheckedCapture(paths, directory), adapter=FrozenAdapter())

    Executor(engine, output, guard).iteration(run)
    assert observed and observed[0] >= (1 if style_failure else 2)
    with Session(engine) as session:
        operation = session.get(UnifiedOperation, identifier)
        assert operation.state == ('interrupted' if translation_failure else 'failed' if style_failure else 'succeeded')
        if translation_failure:
            assert operation.failure_code == 'external_outcome_unknown_possible_repeat_charge'
            step = session.exec(select(OperationStep).where(OperationStep.step_key == 'live-translation-failure')).one()
            assert step.state == 'failed' and step.failure_code == operation.failure_code
            assert len(translation_calls) == 1
        if style_failure:
            assert operation.failure_code == 'live_style_publication_failed'
            assert session.exec(select(OperationStep).where(OperationStep.failure_code == operation.failure_code)).first() is not None
        assert session.get(UnifiedOperation, waiting_id).attempt == 0
    if not translation_failure:
        assert bilingual_observed
    assert not (output / task_id / 'job.json').exists()
