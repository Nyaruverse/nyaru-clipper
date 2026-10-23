from __future__ import annotations

import shutil
from pathlib import Path
from uuid import uuid4

from sqlmodel import Session, select

from app.models_unified import TaskBinding, UnifiedOperation, UnifiedPublication
from app.services.recording_results import publish_companion_result
from app.services.task_execution import Execution, Executor
from app.services.task_operations import bind_task, enqueue_operation, set_admissions
from test_unified_operations import database
from unification_fixtures import build_state


def test_native_checkpoint_becomes_registered_context_without_changing_words(tmp_path: Path) -> None:
    fixture = build_state(tmp_path / 'frozen')
    source = fixture.sources[0] / 'abcdef123456'
    engine = database(tmp_path)
    with Session(engine) as session:
        binding = bind_task(session, uuid4(), 'new-recording', 'g', origin='native')
        task_id = binding.task_id
        enqueue_operation(session, task_id, 'process_recording', {})
        set_admissions(session, paused=False)
        session.commit()
    contexts = []

    def process(execution: Execution) -> None:
        directory = execution.staging('workflow') / 'engine-checkpoint'
        shutil.copytree(source, directory)
        contexts.append(publish_companion_result(execution, directory))

    Executor(engine, tmp_path / 'tasks', tmp_path / 'host-guard').iteration(process)
    with Session(engine) as session:
        assert session.exec(select(UnifiedOperation)).one().state == 'succeeded'
        assert session.get(TaskBinding, task_id).context_json != '{}'
        assert len(session.exec(select(UnifiedPublication)).all()) == 2
    context = contexts[0]
    assert context.source.task_id == task_id and context.source.target_language == 'zh'
    assert context.cues[0].translated_text == '今天天气很好。'
    assert context.cues[0].words[0].confidence == .95
    assert context.source.checked(context.source.transcript).read_bytes() == (source / 'transcript.json').read_bytes()
    assert not (tmp_path / 'tasks' / task_id / 'job.json').exists()
