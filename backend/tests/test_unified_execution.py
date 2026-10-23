from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event
from uuid import uuid4

import pytest
from sqlmodel import Session, select

from app.models_unified import OperationAttempt, UnifiedOperation
from app.services.task_execution import Executor, Execution
from app.services.task_operations import (
    OperationConflict, begin_step, bind_task, claim_operation, enqueue_operation,
    request_cancel, set_admissions,
)
from test_unified_operations import database


def queued(engine, count: int = 3) -> list[str]:
    with Session(engine) as session:
        binding = bind_task(session, uuid4(), "new", "g", origin="native")
        operations = [enqueue_operation(session, binding.task_id, kind, {}) for kind in ["process_live", "process_recording", "translate"][:count]]
        ids = [operation.id for operation in operations]
        set_admissions(session, paused=False)
        session.commit()
        return ids


def test_live_child_publishes_before_parent_terminal_and_never_claims(tmp_path: Path) -> None:
    engine = database(tmp_path)
    ids = queued(engine)
    observed = []

    def work(execution: Execution) -> None:
        stage = execution.staging("clip-one")
        video, subtitle = stage / "clip.mp4", stage / "clip.srt"
        video.write_bytes(b"video")
        subtitle.write_bytes(b"subtitles")
        execution.publish("clip-one", {"video": video, "subtitles": subtitle})
        with Session(engine) as session:
            assert session.get(UnifiedOperation, ids[0]).state == "running"
            assert len(session.exec(select(OperationAttempt)).all()) == 1
            assert claim_operation(session) is None
            observed.append("first clip while capturing")

    assert Executor(engine, tmp_path / "tasks", tmp_path / "guard").iteration(work) == ids[0]
    assert observed == ["first clip while capturing"]
    with Session(engine) as session:
        assert session.get(UnifiedOperation, ids[0]).state == "succeeded"
        assert session.get(UnifiedOperation, ids[1]).state == "queued"


def test_different_database_executors_share_one_host_slot(tmp_path: Path) -> None:
    first_root, second_root = tmp_path / "one", tmp_path / "two"
    first_root.mkdir()
    second_root.mkdir()
    first, second = database(first_root), database(second_root)
    queued(first, 1)
    ids = queued(second, 1)
    entered, release = Event(), Event()

    def work(execution: Execution) -> None:
        entered.set()
        assert release.wait(10)
        raise OperationConflict("controlled workflow failure")

    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(Executor(first, first_root / "tasks", tmp_path / "guard").iteration, work)
        assert entered.wait(10)
        try:
            assert Executor(second, second_root / "tasks", tmp_path / "guard").iteration(work) is None
            with Session(second) as session:
                assert session.get(UnifiedOperation, ids[0]).attempt == 0
        finally:
            release.set()
        assert future.result(timeout=10) is not None


def test_cancel_kills_real_owned_process_group_before_next_claim(tmp_path: Path) -> None:
    import sys
    from app.models_unified import OperationProcess
    engine = database(tmp_path)
    ids = queued(engine, 2)
    started = Event()

    def work(execution: Execution) -> None:
        with execution.process([sys.executable, "-c", "import time; print('ready',flush=True); time.sleep(60)"]) as process:
            assert process.stdout.readline().strip() == "ready"
            started.set()
            execution.wait(process, timeout=10)

    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(Executor(engine, tmp_path / "tasks", tmp_path / "guard").iteration, work)
        assert started.wait(10)
        with Session(engine) as session:
            request_cancel(session, ids[0])
            session.commit()
        assert future.result(timeout=10) == ids[0]
    with Session(engine) as session:
        assert session.get(UnifiedOperation, ids[0]).state == "cancelled"
        assert all(row.released for row in session.exec(select(OperationProcess)).all())
        assert claim_operation(session).id == ids[1]


def test_engine_settings_use_admission_snapshot_after_host_defaults_change(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.settings import get_settings
    engine = database(tmp_path)
    with Session(engine) as session:
        binding = bind_task(session, uuid4(), 'settings', 'g', origin='native')
        enqueue_operation(session, binding.task_id, 'export', {'input': {}, 'config': {'export_video_backend': 'cpu'}})
        set_admissions(session, paused=False)
        session.commit()
    monkeypatch.setenv('APP_EXPORT_VIDEO_BACKEND', 'windows-amf')
    observed = []

    def work(execution: Execution) -> None:
        observed.append(get_settings().export_video_backend)
        output = execution.staging('result') / 'value.txt'
        output.write_text('registered result')
        execution.publish('result', {'result': output})

    Executor(engine, tmp_path / 'tasks', tmp_path / 'guard').iteration(work)
    assert observed == ['cpu']
    assert get_settings().export_video_backend == 'windows-amf'


def test_executor_reconciles_partial_publication_before_terminalizing_attempt(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.models_unified import UnifiedPublication
    from app.services import task_publication
    engine = database(tmp_path)
    ids = queued(engine, 1)
    actual = task_publication.publish_file
    failed = [False]
    calls = []

    def disk_failure(source: Path, target: Path, checksum: str, size: int) -> None:
        if target.suffix == '.mp4' and not failed[0]:
            failed[0] = True
            raise OSError('one interrupted product publication')
        actual(source, target, checksum, size)

    monkeypatch.setattr(task_publication, 'publish_file', disk_failure)

    def work(execution: Execution) -> None:
        calls.append('engine invoked')
        root = execution.staging('set')
        video, subtitles = root / 'clip.mp4', root / 'clip.srt'
        video.write_bytes(b'video')
        subtitles.write_bytes(b'subtitles')
        execution.publish('set', {'video': video, 'subtitles': subtitles})

    Executor(engine, tmp_path / 'tasks', tmp_path / 'guard').iteration(work)
    with Session(engine) as session:
        assert session.get(UnifiedOperation, ids[0]).state == 'interrupted'
        assert session.exec(select(UnifiedPublication)).one().state == 'committed'
    assert calls == ['engine invoked']
