import os
import subprocess
import sys
from datetime import timedelta

import pytest
from sqlmodel import Session, select

from test_terminal_retry_atomicity import assert_terminal, database, seed


@pytest.mark.parametrize("status", ["success", "failed", "cancelled"])
def test_process_exit_at_terminal_commit_releases_next_job(database, status):
    from app.worker import claim_next_job
    seed(database, "first")
    seed(database, "next")
    assert claim_next_job().task_id == "first"
    script = """
import os
from sqlalchemy import event
from sqlmodel import Session
from app.db import get_engine
from app.models import Task
from app.services import task_runner
from app.services.task_control import activate_execution, finalize_cancelled
engine = get_engine()
status = os.environ["TEST_TERMINAL_STATUS"]
def execute(session, task_id):
    session.commit()
    if status == "failed":
        raise ValueError("injected failure")
    if status == "cancelled":
        finalize_cancelled(session, task_id=task_id, execution_token="fixture")
        session.commit()
task_runner.STAGE_EXECUTORS = {name: execute for name in task_runner.CANONICAL_STAGE_ORDER}
with Session(engine) as session:
    activate_execution(session, task_id="first", execution_token="fixture")
    def crash_at_terminal(_session):
        with Session(engine) as check:
            if check.get(Task, "first").status == status:
                os._exit(73)
    event.listen(session, "after_commit", crash_at_terminal)
    task_runner.run_task_pipeline(session, "first", start_stage_name="report", claimed_stage_running=True, execution_token="fixture")
raise AssertionError("terminal crash boundary was not reached")
"""
    result = subprocess.run([sys.executable, "-c", script], env={**os.environ, "TEST_TERMINAL_STATUS": status}, capture_output=True, text=True, timeout=15)
    assert result.returncode == 73, result.stderr
    assert_terminal(database, "first", status)
    assert claim_next_job().task_id == "next"


def test_persistent_cleanup_failure_keeps_gpu_guard_and_tracking(database, monkeypatch):
    from app.models import PipelineRun, QueueEntry, TaskExecutionControl, TaskJob
    from app.services import task_runner
    from app.services.pipeline_support import ProcessGroupCleanupError
    from app.services.task_control import activate_execution
    from app.worker import claim_next_job
    seed(database, "first")
    seed(database, "next")
    assert claim_next_job().task_id == "first"

    def failed_cleanup(session, task_id):
        control = session.get(TaskExecutionControl, task_id)
        control.active_process_group_id = 999999
        session.add(control)
        session.commit()
        session.info["process_group_cleanup_failed"] = True
        raise ProcessGroupCleanupError(999999)

    monkeypatch.setattr(task_runner, "STAGE_EXECUTORS", {name: failed_cleanup for name in task_runner.CANONICAL_STAGE_ORDER})
    with Session(database) as session:
        activate_execution(session, task_id="first", execution_token="fixture")
        with pytest.raises(ProcessGroupCleanupError):
            task_runner.run_task_pipeline(session, "first", start_stage_name="report", claimed_stage_running=True, execution_token="fixture")
    with Session(database) as session:
        assert session.get(TaskExecutionControl, "first").active_process_group_id == 999999
        assert session.get(TaskExecutionControl, "first").execution_token == "fixture"
        assert session.get(QueueEntry, "first").state == "running"
        assert session.get(PipelineRun, "run-first").status == "running"
        assert session.exec(select(TaskJob).where(TaskJob.task_id == "first")).one().status == "running"
    assert claim_next_job() is None


def test_stale_recovery_does_not_clear_tracking_until_group_is_gone(database, monkeypatch):
    from app.models import QueueEntry, TaskExecutionControl, TaskJob, utc_now
    from app import worker
    seed(database, "old", status="running", queue="running")
    seed(database, "next")
    with Session(database) as session:
        job = session.exec(select(TaskJob).where(TaskJob.task_id == "old")).one()
        job.updated_at = utc_now() - timedelta(hours=1)
        session.add(job)
        session.add(TaskExecutionControl(task_id="old", execution_token="old-token", active_process_group_id=999999))
        session.commit()
    monkeypatch.setattr(worker, "best_effort_kill_active_process_group", lambda *args, **kwargs: 999999)
    monkeypatch.setattr(worker, "_wait_for_recovered_process_group", lambda pid, **kwargs: False)
    assert worker.claim_next_job() is None
    with Session(database) as session:
        assert session.get(TaskExecutionControl, "old").active_process_group_id == 999999
        assert session.get(QueueEntry, "old").state == "running"
    monkeypatch.setattr(worker, "_wait_for_recovered_process_group", lambda pid, **kwargs: True)
    assert worker.claim_next_job().task_id == "next"
    with Session(database) as session:
        assert session.get(TaskExecutionControl, "old").active_process_group_id is None


@pytest.mark.parametrize("denied_operation", ["signal", "probe"])
@pytest.mark.parametrize("persistent", [False, True])
def test_stale_recovery_retries_permission_denial_without_releasing_guard(database, monkeypatch, denied_operation, persistent):
    import signal
    from app.models import QueueEntry, TaskExecutionControl, TaskJob, utc_now
    from app import worker
    seed(database, "old", status="running", queue="running")
    seed(database, "next")
    with Session(database) as session:
        job = session.exec(select(TaskJob).where(TaskJob.task_id == "old")).one()
        job.updated_at = utc_now() - timedelta(hours=1)
        session.add(job)
        session.add(TaskExecutionControl(task_id="old", execution_token="old-token", active_process_group_id=999999))
        session.commit()
    clock = [0.0]
    denied_calls = []
    allow = [False]

    def killpg(pid, signum):
        assert pid == 999999
        operation = "probe" if signum == 0 else "signal"
        assert signum in {0, signal.SIGKILL}
        if operation == denied_operation and not allow[0]:
            denied_calls.append(signum)
            if persistent or len(denied_calls) <= 2:
                raise PermissionError("injected permission denial")
        if signum == 0:
            raise ProcessLookupError

    def waitpid(pid, flags):
        raise ChildProcessError

    monkeypatch.setattr(worker.os, "killpg", killpg)
    monkeypatch.setattr(worker.os, "waitpid", waitpid)
    monkeypatch.setattr(worker.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(worker.time, "sleep", lambda seconds: clock.__setitem__(0, clock[0] + seconds))
    if persistent:
        with pytest.raises(PermissionError, match="injected"):
            worker.claim_next_job()
        assert 1.0 <= clock[0] <= 1.05
        assert len(denied_calls) > 2
        with Session(database) as session:
            control = session.get(TaskExecutionControl, "old")
            assert (control.execution_token, control.active_process_group_id) == ("old-token", 999999)
            assert session.get(QueueEntry, "old").state == "running"
            assert session.get(QueueEntry, "next").state == "queued"
            assert session.exec(select(TaskJob).where(TaskJob.task_id == "old")).one().status == "running"
        allow[0] = True
    assert worker.claim_next_job().task_id == "next"
    assert len(denied_calls) >= 2
    with Session(database) as session:
        assert session.get(TaskExecutionControl, "old").active_process_group_id is None
        assert session.get(QueueEntry, "old").state == "finished"
