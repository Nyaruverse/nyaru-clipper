from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import pytest
from sqlmodel import select


def _reset_runtime_state() -> None:
    try:
        from app.db import reset_db_runtime
    except ModuleNotFoundError:
        return
    reset_db_runtime()


def _create_task(data_dir: Path, monkeypatch) -> str:
    monkeypatch.setenv("APP_DATA_DIR", str(data_dir))
    monkeypatch.setenv("APP_DATABASE_URL", f"sqlite:///{data_dir.parent / 'task-state.sqlite3'}")
    _reset_runtime_state()

    from app.db import init_db, session_scope
    from app.repositories.tasks import create_task

    init_db()
    with session_scope() as session:
        payload, _ = create_task(session, "https://www.bilibili.com/video/BV1cd411c7mF")
        return payload["task_id"]


def test_public_report_accounting_correction_emits_later_observer_event(tmp_path, monkeypatch):
    task_id = _create_task(tmp_path / "data", monkeypatch)
    from app.db import session_scope
    from app.models import Artifact, Task, WorkstationEvent
    from app.services import reporting
    from app.services.storage import get_task_root

    with session_scope() as session:
        session.get(Task, task_id).status = "success"
        session.commit()
        with reporting.publish_task_report(session, reporting.generate_task_report(session, task_id)):
            session.commit()
    snapshots = []

    def observe():
        with session_scope() as observer:
            events = observer.exec(select(WorkstationEvent).order_by(WorkstationEvent.id)).all()
            return (
                observer.get(Task, task_id).storage_bytes,
                [(event.id, event.event_type) for event in events],
                [artifact.id for artifact in observer.exec(select(Artifact)).all()],
            )

    reconcile = reporting.reconcile_storage_after_cleanup

    def observe_reconciliation(session, *, task_id):
        snapshots.append(observe())
        reconcile(session, task_id=task_id)
        snapshots.append(observe())

    monkeypatch.setattr(reporting, "reconcile_storage_after_cleanup", observe_reconciliation)
    with session_scope() as session:
        with reporting.publish_task_report(session, reporting.generate_task_report(session, task_id)):
            session.commit()
    before, after = snapshots
    cursor = before[1][-1][0]
    assert before[0] > after[0]
    assert [kind for event_id, kind in after[1] if event_id > cursor] == ["task.updated"]
    assert before[2] == after[2]
    assert sum(kind == "artifact.ready" for _, kind in before[1]) == sum(kind == "artifact.ready" for _, kind in after[1]) == 1
    assert after[0] == sum(p.stat().st_size for p in get_task_root(task_id).rglob("*") if p.is_file())


@pytest.mark.parametrize("fault", ["none", "unlink", "accounting"])
def test_public_report_overwrite_persists_final_tree_size(tmp_path, monkeypatch, caplog, fault):
    task_id = _create_task(tmp_path / "data", monkeypatch)
    from app.db import session_scope
    from app.models import Task
    from app.services.reporting import generate_task_report, publish_task_report
    from app.services.storage import get_task_root
    from app.services import storage
    from sqlalchemy.exc import OperationalError

    root = get_task_root(task_id)
    orphan = root / "reports" / "interrupted.previous"
    orphan.write_bytes(b"retained-orphan")
    with session_scope() as session:
        session.get(Task, task_id).status = "success"
        session.commit()
        with publish_task_report(session, generate_task_report(session, task_id)):
            session.commit()
    unlink = Path.unlink

    def fail_owned_cleanup(path, *args, **kwargs):
        if path.name == "task-report.md.previous":
            raise OSError("owned backup cleanup failed")
        return unlink(path, *args, **kwargs)

    with monkeypatch.context() as patch:
        if fault == "unlink":
            patch.setattr(Path, "unlink", fail_owned_cleanup)
        with session_scope() as session:
            original_refresh = storage.refresh_task_storage

            def fail_recount(accounting, *, task_id):
                if accounting is not session:
                    raise OperationalError("recount", {}, RuntimeError("accounting unavailable"))
                original_refresh(accounting, task_id=task_id)

            if fault == "accounting":
                patch.setattr(storage, "refresh_task_storage", fail_recount)
            if fault == "unlink":
                with pytest.raises(OSError, match="owned backup cleanup failed"):
                    with publish_task_report(session, generate_task_report(session, task_id)):
                        session.commit()
            else:
                with publish_task_report(session, generate_task_report(session, task_id)):
                    session.commit()
    with session_scope() as session:
        actual = sum(p.stat().st_size for p in root.rglob("*") if p.is_file())
        if fault == "accounting":
            assert session.get(Task, task_id).storage_bytes > actual
            assert "storage_recount_deferred" in caplog.text
        else:
            assert session.get(Task, task_id).storage_bytes == actual
        assert session.get(Task, task_id).status == "success"
    assert orphan.read_bytes() == b"retained-orphan"
    assert (root / "reports" / "task-report.md.previous").exists() == (fault == "unlink")
    with session_scope() as session:
        with publish_task_report(session, generate_task_report(session, task_id)):
            session.commit()
    with session_scope() as session:
        assert session.get(Task, task_id).storage_bytes == sum(p.stat().st_size for p in root.rglob("*") if p.is_file())


def test_generate_task_report_includes_required_sections(tmp_path, monkeypatch) -> None:
    data_dir = tmp_path / "data"
    task_id = _create_task(data_dir, monkeypatch)

    from app.db import session_scope
    from app.models import ClipCandidate, Task, TaskStage, utc_now
    from app.services.storage import persist_artifact_metadata

    task_root = data_dir / "tasks" / task_id
    export_path = task_root / "exports" / "clip-00012000-00019500.mp4"
    export_path.parent.mkdir(parents=True, exist_ok=True)
    export_path.write_bytes(b"clip")
    source_metadata_path = task_root / "raw" / "source-metadata.json"
    source_metadata_path.parent.mkdir(parents=True, exist_ok=True)
    source_metadata_path.write_text('{"title": "Fixture Stream"}', encoding="utf-8")
    transcript_path = task_root / "work" / "subtitles.zh-ja.json"
    transcript_path.parent.mkdir(parents=True, exist_ok=True)
    transcript_path.write_text("{}", encoding="utf-8")

    with session_scope() as session:
        task = session.get(Task, task_id)
        assert task is not None
        task.status = "success"
        session.add(task)

        stages = session.exec(select(TaskStage).where(TaskStage.task_id == task_id)).all()
        base_time = utc_now()
        for index, stage in enumerate(stages, start=1):
            stage.status = "success"
            stage.attempts = 2 if stage.name == "translation" else 1
            stage.started_at = base_time + timedelta(seconds=index * 10)
            stage.finished_at = stage.started_at + timedelta(seconds=index)
            stage.summary = f"{stage.name} complete"
            session.add(stage)

        persist_artifact_metadata(
            session,
            task_id=task_id,
            stage_name="ingest",
            kind="source_metadata",
            path=source_metadata_path,
            metadata={"source_metadata": {"title": "Fixture Stream", "uploader": "Tester", "duration": 90.0}},
        )
        persist_artifact_metadata(
            session,
            task_id=task_id,
            stage_name="translation",
            kind="bilingual_transcript_json",
            path=transcript_path,
            metadata={
                "elapsed_seconds": 7.5,
                "model_metadata": {"provider": "hf", "model_name": "fixture-translator"},
            },
        )
        persist_artifact_metadata(
            session,
            task_id=task_id,
            stage_name="export",
            kind="clip_export",
            path=export_path,
            metadata={"candidate_id": 4, "start_s": 12.0, "end_s": 19.5, "source_duration_s": 90.0},
        )
        candidate = ClipCandidate(
            task_id=task_id,
            start_seconds=12.0,
            end_seconds=19.5,
            score=0.87,
            reason="fixture",
            status="confirmed",
        )
        session.add(candidate)
        session.flush()
        candidate_id = candidate.id

    from app.db import session_scope
    from app.models import Artifact, TaskStage
    from app.services.reporting import generate_task_report, publish_task_report

    with session_scope() as session:
        result = generate_task_report(session, task_id)
        with publish_task_report(session, result):
            session.commit()

    report_text = result.output_path.read_text(encoding="utf-8")
    assert "# Task Report" in report_text
    assert "Fixture Stream" in report_text
    assert "## Source Metadata" in report_text
    assert "## Stage Timings" in report_text
    assert "## Model Metadata" in report_text
    assert "fixture-translator" in report_text
    assert "## Retries" in report_text
    assert "translation" in report_text
    assert "## Artifacts" in report_text
    assert "## Exported Clips" in report_text
    assert "clip-00012000-00019500.mp4" in report_text
    assert "## Clip Candidates" in report_text
    assert f"Candidate {candidate_id}: 12.0s → 19.5s [confirmed] score=0.87" in report_text

    with session_scope() as session:
        stage = session.exec(
            select(TaskStage).where(TaskStage.task_id == task_id).where(TaskStage.name == "report")
        ).one()
        artifacts = session.exec(
            select(Artifact).where(Artifact.task_id == task_id).where(Artifact.stage_name == "report")
        ).all()
        stage_status = stage.status
        stage_summary = stage.summary
        artifact_kinds = {artifact.kind for artifact in artifacts}

    assert stage_status == "success"
    assert stage_summary == "report complete"
    assert artifact_kinds == {"task_report_markdown"}


@pytest.mark.parametrize("failed_stage", [None, "translation"])
def test_runner_publishes_terminal_report_download(tmp_path, monkeypatch, failed_stage):
    # Given a real runner with only external pipeline stages replaced.
    task_id = _create_task(tmp_path / "data", monkeypatch)
    from app.db import session_scope
    from app.main import app
    from app.models import Artifact, PipelineRun, Task, TaskStage
    from app.services import task_runner
    from fastapi.testclient import TestClient

    def execute(session, current_task_id):
        if failed_stage is not None:
            stage = session.exec(select(TaskStage).where(
                TaskStage.task_id == current_task_id, TaskStage.status == "running"
            )).one()
            if stage.name == failed_stage:
                raise RuntimeError("translation terminal failure")

    for stage_name in task_runner.CANONICAL_STAGE_ORDER[:-1]:
        monkeypatch.setitem(task_runner.STAGE_EXECUTORS, stage_name, execute)

    # When the production runner determines success or a real stage exception.
    with session_scope() as session:
        if failed_stage is None:
            assert task_runner.run_task_pipeline(session, task_id).final_status == "success"
        else:
            with pytest.raises(RuntimeError, match="translation terminal failure"):
                task_runner.run_task_pipeline(session, task_id)

    # Then the downloadable artifact matches persisted terminal state and reason.
    with session_scope() as session:
        task = session.get(Task, task_id)
        run = session.exec(select(PipelineRun).where(PipelineRun.task_id == task_id)).one()
        artifact = session.exec(select(Artifact).where(
            Artifact.task_id == task_id, Artifact.kind == "task_report_markdown"
        )).one()
        with TestClient(app) as client:
            response = client.get(f"/api/tasks/{task_id}/artifacts/{artifact.id}/content/task-report.md")
        assert response.status_code == 200
        assert f"- Task Status: {task.status}" in response.text
        assert f"- Canonical Run ID: `{run.id}`" in response.text
        assert f"- Canonical Run Status: {run.status}" in response.text
        if failed_stage:
            assert "translation terminal failure" in response.text
        else:
            assert "| report | success |" in response.text
        print(f"TERMINAL_REPORT_{task.status.upper()}\n{response.text}")


@pytest.mark.parametrize("fault", ["write", "registration", "commit"])
@pytest.mark.parametrize("prior_report", [False, True])
def test_runner_report_publication_fault_restores_previous_output(tmp_path, monkeypatch, fault, prior_report):
    # Given optional historical report bytes and a failing publication boundary.
    task_id = _create_task(tmp_path / "data", monkeypatch)
    from app.db import session_scope
    from app.models import Artifact, PipelineRun, QueueEntry, Task, TaskJob, TaskStage
    from app.services import reporting, task_runner
    from sqlmodel import Session

    report_path = tmp_path / "data" / "tasks" / task_id / "reports" / "task-report.md"
    old_bytes = b"Historical canonical run report\n"
    if prior_report:
        report_path.write_bytes(old_bytes)
        with session_scope() as session:
            reporting._persist_report_artifact(session, task_id=task_id, output_path=report_path)
    for stage_name in task_runner.CANONICAL_STAGE_ORDER[:-1]:
        monkeypatch.setitem(task_runner.STAGE_EXECUTORS, stage_name, lambda session, current_task_id: None)
    original_write = Path.write_text
    original_register = reporting._persist_report_artifact
    original_commit = Session.commit
    original_log = task_runner.append_stage_log

    def append_log(path, message):
        if path.name == "report.log" and ("task_runner:error" in message or "failed_report_error" in message):
            raise OSError("report diagnostic log unavailable")
        original_log(path, message)

    monkeypatch.setattr(task_runner, "append_stage_log", append_log)
    registrations = 0

    def write(path, *args, **kwargs):
        if path.name == "task-report.md.tmp":
            raise OSError("report write fault")
        return original_write(path, *args, **kwargs)

    def register(session, **kwargs):
        nonlocal registrations
        registrations += 1
        if fault == "registration" or registrations > 1:
            raise RuntimeError("report registration fault")
        return original_register(session, **kwargs)

    def commit(session):
        task = session.get(Task, task_id)
        if task is not None and task.status == "success":
            raise RuntimeError("report commit fault")
        return original_commit(session)

    if fault == "write":
        monkeypatch.setattr(Path, "write_text", write)
    else:
        monkeypatch.setattr(reporting, "_persist_report_artifact", register)
    if fault == "commit":
        monkeypatch.setattr(Session, "commit", commit)

    # When publication fails, including a failed secondary diagnostic publication.
    with session_scope() as session:
        with pytest.raises((OSError, RuntimeError), match=f"report {fault} fault"):
            task_runner.run_task_pipeline(session, task_id)

    # Then all terminal projections fail and old bytes/registration survive exactly.
    with session_scope() as session:
        assert session.get(Task, task_id).status == "failed"
        assert session.exec(select(TaskJob).where(TaskJob.task_id == task_id)).one().status == "failed"
        assert session.exec(select(PipelineRun).where(PipelineRun.task_id == task_id)).one().status == "failed"
        report_stage = session.exec(select(TaskStage).where(
            TaskStage.task_id == task_id, TaskStage.name == "report"
        )).one()
        assert report_stage.status == "failed"
        assert report_stage.summary == f"report {fault} fault"
        assert session.exec(select(QueueEntry).where(QueueEntry.task_id == task_id)).one().state == "finished"
        artifacts = session.exec(select(Artifact).where(
            Artifact.task_id == task_id, Artifact.kind == "task_report_markdown"
        )).all()
        assert len(artifacts) == int(prior_report)
    if prior_report:
        assert report_path.read_bytes() == old_bytes
    else:
        assert not report_path.exists()
    assert not report_path.with_suffix(".md.tmp").exists()
    assert not report_path.with_suffix(".md.previous").exists()
    print(f"PUBLICATION_FAULT={fault} PRIOR_REPORT={prior_report} RESTORED=True TERMINAL=failed")


@pytest.mark.parametrize("control_action", ["cancel", "stale"])
def test_runner_checks_control_again_at_terminal_report_boundary(tmp_path, monkeypatch, control_action):
    # Given an active worker and a control change after the last stage checkpoint.
    task_id = _create_task(tmp_path / "data", monkeypatch)
    from app.db import session_scope
    from app.models import Artifact, Task, TaskStage, TaskExecutionControl
    from app.services import task_runner
    from app.services.task_control import activate_execution

    for stage_name in task_runner.CANONICAL_STAGE_ORDER[:-1]:
        monkeypatch.setitem(task_runner.STAGE_EXECUTORS, stage_name, lambda session, current_task_id: None)
    original_begin = task_runner.begin_queue_mutation
    injected = False

    def begin(session):
        nonlocal injected
        stages = session.exec(select(TaskStage).where(TaskStage.task_id == task_id)).all()
        if not injected and all(stage.status == "success" for stage in stages):
            injected = True
            session.rollback()
            with session_scope() as other:
                if control_action == "cancel":
                    control = other.get(TaskExecutionControl, task_id)
                    control.cancel_requested = True
                    other.add(control)
                else:
                    activate_execution(other, task_id=task_id, execution_token="replacement-token")
        original_begin(session)

    monkeypatch.setattr(task_runner, "begin_queue_mutation", begin)
    with session_scope() as session:
        activate_execution(session, task_id=task_id, execution_token="original-token")
    # When the real runner enters its final publication transaction.
    with session_scope() as session:
        result = task_runner.run_task_pipeline(session, task_id, execution_token="original-token")
    # Then control wins, with no successful final artifact exposed.
    assert injected
    assert result.final_status == ("cancelled" if control_action == "cancel" else "running")
    with session_scope() as session:
        assert session.get(Task, task_id).status != "success"
        assert session.exec(select(Artifact).where(
            Artifact.task_id == task_id, Artifact.kind == "task_report_markdown"
        )).first() is None
    assert not (tmp_path / "data" / "tasks" / task_id / "reports" / "task-report.md").exists()
    print(f"TERMINAL_CONTROL={control_action} FINAL_REPORT_ABSENT=True")


def test_failed_report_records_publication_error_without_marking_report_success(tmp_path, monkeypatch):
    # Given a one-off registration failure during successful terminal publication.
    task_id = _create_task(tmp_path / "data", monkeypatch)
    from app.db import session_scope
    from app.models import Artifact, TaskStage
    from app.services import reporting, task_runner

    for stage_name in task_runner.CANONICAL_STAGE_ORDER[:-1]:
        monkeypatch.setitem(task_runner.STAGE_EXECUTORS, stage_name, lambda session, current_task_id: None)
    original_register = reporting._persist_report_artifact
    failed = False

    def register(session, **kwargs):
        nonlocal failed
        if not failed:
            failed = True
            raise RuntimeError("first report registration failed")
        return original_register(session, **kwargs)

    monkeypatch.setattr(reporting, "_persist_report_artifact", register)
    # When diagnostic publication succeeds after the primary failure.
    with session_scope() as session:
        with pytest.raises(RuntimeError, match="first report registration failed"):
            task_runner.run_task_pipeline(session, task_id)
    # Then the final report truthfully retains the failed report stage and cause.
    with session_scope() as session:
        artifact = session.exec(select(Artifact).where(
            Artifact.task_id == task_id, Artifact.kind == "task_report_markdown"
        )).one()
        content = Path(artifact.path).read_text()
        assert "- Task Status: failed" in content
        assert "| report | failed |" in content
        assert "first report registration failed" in content
        assert session.exec(select(TaskStage).where(
            TaskStage.task_id == task_id, TaskStage.name == "report"
        )).one().status == "failed"
        print(f"REPORT_FAILURE_DIAGNOSTIC\n{content}")


@pytest.mark.parametrize("log_failed", [False, True])
def test_failed_report_error_does_not_replace_translation_failure(tmp_path, monkeypatch, caplog, log_failed):
    # Given an upstream failure and unavailable report storage.
    task_id = _create_task(tmp_path / "data", monkeypatch)
    from app.db import session_scope
    from app.models import Task, TaskStage
    from app.services import reporting, task_runner

    def fail_translation(session, current_task_id):
        raise RuntimeError("original translation failure")

    def fail_registration(session, **kwargs):
        raise OSError("secondary report storage unavailable")

    for stage_name in task_runner.CANONICAL_STAGE_ORDER[:-1]:
        monkeypatch.setitem(task_runner.STAGE_EXECUTORS, stage_name, lambda session, current_task_id: None)
    monkeypatch.setitem(task_runner.STAGE_EXECUTORS, "translation", fail_translation)
    monkeypatch.setattr(reporting, "_persist_report_artifact", fail_registration)
    if log_failed:
        original_log = task_runner.append_stage_log

        def append_log(path, message):
            if "failed_report_error" in message:
                raise OSError("secondary diagnostic log unavailable")
            original_log(path, message)

        monkeypatch.setattr(task_runner, "append_stage_log", append_log)
    # When the original pipeline error is followed by a report error.
    with session_scope() as session:
        with pytest.raises(RuntimeError, match="^original translation failure$"):
            task_runner.run_task_pipeline(session, task_id)
    # Then the original cause remains authoritative and secondary failure is logged.
    with session_scope() as session:
        assert session.get(Task, task_id).status == "failed"
        stage = session.exec(select(TaskStage).where(
            TaskStage.task_id == task_id, TaskStage.name == "translation"
        )).one()
        assert stage.summary == "original translation failure"
    from app.services.storage import log_file_for_stage
    if log_failed:
        assert "Failed to write report failure diagnostic" in caplog.text
    else:
        assert "secondary report storage unavailable" in log_file_for_stage(task_id, "report").read_text()
    print(f"PRIMARY_TRANSLATION_FAILURE_PRESERVED=True DIAGNOSTIC_LOG_FAILED={log_failed}")


def test_generic_failure_log_error_preserves_primary_and_terminal_report(tmp_path, monkeypatch, caplog):
    # Given an upstream exception and an unwritable generic failure log.
    task_id = _create_task(tmp_path / "data", monkeypatch)
    from app.db import session_scope
    from app.models import Artifact, PipelineRun, QueueEntry, Task, TaskJob, TaskStage
    from app.services import task_runner

    def fail_translation(session, current_task_id):
        raise RuntimeError("primary upstream failure")

    original_log = task_runner.append_stage_log

    def append_log(path, message):
        if message.startswith("task_runner:error"):
            raise OSError("generic failure log unavailable")
        original_log(path, message)

    for stage_name in task_runner.CANONICAL_STAGE_ORDER[:-1]:
        monkeypatch.setitem(task_runner.STAGE_EXECUTORS, stage_name, lambda session, current_task_id: None)
    monkeypatch.setitem(task_runner.STAGE_EXECUTORS, "translation", fail_translation)
    monkeypatch.setattr(task_runner, "append_stage_log", append_log)
    # When the real runner catches the upstream failure and logs its diagnostic.
    with session_scope() as session:
        with pytest.raises(RuntimeError, match="^primary upstream failure$"):
            task_runner.run_task_pipeline(session, task_id)
    # Then logging failure cannot interrupt terminal persistence or final report publication.
    with session_scope() as session:
        assert session.get(Task, task_id).status == "failed"
        assert session.exec(select(TaskJob).where(TaskJob.task_id == task_id)).one().status == "failed"
        assert session.exec(select(PipelineRun).where(PipelineRun.task_id == task_id)).one().status == "failed"
        assert session.exec(select(QueueEntry).where(QueueEntry.task_id == task_id)).one().state == "finished"
        stage = session.exec(select(TaskStage).where(
            TaskStage.task_id == task_id, TaskStage.name == "translation"
        )).one()
        assert stage.status == "failed"
        assert stage.summary == "primary upstream failure"
        artifact = session.exec(select(Artifact).where(
            Artifact.task_id == task_id, Artifact.kind == "task_report_markdown"
        )).one()
        report = Path(artifact.path).read_text()
        assert "- Task Status: failed" in report
        assert "- Canonical Run Status: failed" in report
        assert "primary upstream failure" in report
    assert "Failed to write translation failure diagnostic" in caplog.text
    print("GENERIC_FAILURE_LOG_FAULT PRIMARY_PRESERVED=True TASK_JOB_RUN_FAILED=True QUEUE_FINISHED=True FINAL_REPORT_FAILED=True")
