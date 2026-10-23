from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlmodel import select


def _reset_runtime_state() -> None:
    try:
        from app.db import reset_db_runtime
    except ModuleNotFoundError:
        return
    reset_db_runtime()


@pytest.fixture()
def backend_env(tmp_path, monkeypatch) -> dict[str, Path | str]:
    data_dir = tmp_path / "data"
    db_path = tmp_path / "task-state.sqlite3"
    monkeypatch.setenv("APP_DATA_DIR", str(data_dir))
    monkeypatch.setenv("APP_DATABASE_URL", f"sqlite:///{db_path}")
    _reset_runtime_state()
    return {"data_dir": data_dir, "db_path": db_path}


@pytest.fixture()
def client(backend_env) -> TestClient:
    from app.main import app

    with TestClient(app) as test_client:
        yield test_client


def _seed_task_with_candidate(data_dir: Path) -> tuple[str, int]:
    from app.db import init_db, session_scope
    from app.models import ClipCandidate
    from app.repositories.tasks import create_task
    from app.services.storage import persist_artifact_metadata

    init_db()
    with session_scope() as session:
        payload, _ = create_task(session, "https://www.bilibili.com/video/BV1ab411c7mE")
        task_id = payload["task_id"]
        task_root = data_dir / "tasks" / task_id
        source_path = task_root / "raw" / "source.mp4"
        media_probe_path = task_root / "work" / "media-probe.json"
        source_path.parent.mkdir(parents=True, exist_ok=True)
        media_probe_path.parent.mkdir(parents=True, exist_ok=True)
        source_path.write_bytes(b"source-video")
        media_probe_path.write_text(
            json.dumps({"format": {"duration": "90.0"}}, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        persist_artifact_metadata(
            session,
            task_id=task_id,
            stage_name="ingest",
            kind="source_video",
            path=source_path,
            metadata={"output_file_path": str(source_path)},
        )
        persist_artifact_metadata(
            session,
            task_id=task_id,
            stage_name="media_prep",
            kind="media_probe",
            path=media_probe_path,
            metadata={"ffprobe_metadata": {"format": {"duration": "90.0"}}},
        )
        candidate = ClipCandidate(
            task_id=task_id,
            start_seconds=11.0,
            end_seconds=18.0,
            score=0.9,
            reason="peak-moment",
            status="candidate",
        )
        session.add(candidate)
        session.flush()
        session.refresh(candidate)
        return task_id, int(candidate.id)


def test_post_clips_exports_confirmed_candidate(client: TestClient, backend_env, monkeypatch) -> None:
    task_id, candidate_id = _seed_task_with_candidate(Path(backend_env["data_dir"]))

    def fake_run(args: list[str], **kwargs) -> subprocess.CompletedProcess[str]:
        output_path = Path(args[-1])
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"clip")
        return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")

    monkeypatch.setattr("subprocess.run", fake_run)

    response = client.post(
        f"/api/tasks/{task_id}/clips",
        json={"candidate_id": candidate_id, "start_s": 12.0, "end_s": 19.5},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["task_id"] == task_id
    assert body["candidate_id"] == candidate_id
    assert body["start_s"] == 12.0
    assert body["end_s"] == 19.5
    assert body["filename"] == "clip-00012000-00019500.mp4"
    assert body["path"] == f"/api/tasks/{task_id}/artifacts/{body['artifact_id']}/content/clip-00012000-00019500.mp4"

    artifact_response = client.get(body["path"])

    assert artifact_response.status_code == 200
    assert artifact_response.content == b"clip"
    assert "attachment; filename=\"clip-00012000-00019500.mp4\"" in artifact_response.headers["content-disposition"]

    from app.db import session_scope
    from app.models import Artifact, ClipCandidate

    with session_scope() as session:
        artifacts = session.exec(
            select(Artifact).where(Artifact.task_id == task_id).where(Artifact.stage_name == "export")
        ).all()
        candidate = session.exec(select(ClipCandidate).where(ClipCandidate.id == candidate_id)).one()
        artifact_kinds = {artifact.kind for artifact in artifacts}
        candidate_status = candidate.status

    assert artifact_kinds == {"clip_export"}
    assert candidate_status == "exported"


def test_post_clips_persists_public_stage_event_after_successful_manual_export(
    client: TestClient, backend_env, monkeypatch
) -> None:
    # Given: a manually exportable candidate and an ffmpeg invocation that creates its output.
    task_id, candidate_id = _seed_task_with_candidate(Path(backend_env["data_dir"]))

    def fake_run(args: list[str], **kwargs) -> subprocess.CompletedProcess[str]:
        output_path = Path(args[-1])
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"clip")
        return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")

    monkeypatch.setattr("subprocess.run", fake_run)

    # When: the v1 clip export route completes the manual export transaction.
    response = client.post(f"/api/tasks/{task_id}/clips", json={"candidate_id": candidate_id})

    # Then: the committed stage state has a replayable public projection.
    from app.db import session_scope
    from app.models import WorkstationEvent

    with session_scope() as session:
        events = session.exec(
            select(WorkstationEvent)
            .where(WorkstationEvent.entity_id == task_id)
            .where(WorkstationEvent.event_type == "stage.updated")
        ).all()
        payloads = [json.loads(event.payload_json) for event in events]
    assert response.status_code == 201
    assert {
        "task_id": task_id,
        "stage_name": "export",
        "status": "success",
        "failure_code": None,
        "attempts": 0,
    } in payloads


def test_pending_manual_failure_records_operation_without_failing_scheduled_pipeline(
    client: TestClient, backend_env, monkeypatch
) -> None:
    # Given: an exportable candidate whose ffmpeg command fails.
    task_id, candidate_id = _seed_task_with_candidate(Path(backend_env["data_dir"]))

    def fake_run(args: list[str], **kwargs) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args=args, returncode=1, stdout="", stderr="ffmpeg failed")

    monkeypatch.setattr("subprocess.run", fake_run)

    # When: the v1 clip export route handles that failed manual export.
    response = client.post(f"/api/tasks/{task_id}/clips", json={"candidate_id": candidate_id})

    # Then: the failed manual operation is replayable while pipeline scheduling stays pending.
    from app.db import session_scope
    from app.models import PipelineRun, TaskJob, QueueEntry, WorkstationEvent

    with session_scope() as session:
        events = session.exec(select(WorkstationEvent).where(WorkstationEvent.entity_id == task_id)).all()
        payloads_by_type = [(event.event_type, json.loads(event.payload_json)) for event in events]
        assert session.exec(select(TaskJob).where(TaskJob.task_id == task_id)).one().status == "pending"
        assert session.get(QueueEntry, task_id).state == "queued"
        assert session.exec(select(PipelineRun).where(PipelineRun.task_id == task_id).where(PipelineRun.trigger == "create")).one().status == "pending"
        assert session.exec(select(PipelineRun).where(PipelineRun.task_id == task_id).where(PipelineRun.trigger == "manual_export")).one().status == "failed"
    assert response.status_code == 400
    assert ("task.updated", {"task_id": task_id, "status": "failed"}) not in payloads_by_type
    assert client.get(f"/api/tasks/{task_id}").json()["status"] == "pending"
    overview = client.get(f"/api/v2/tasks/{task_id}").json()
    assert overview["status"] == "pending"
    assert next(stage for stage in overview["stages"] if stage["name"] == "export")["status"] == "failed"
    assert (
        "stage.updated",
        {
            "task_id": task_id,
            "stage_name": "export",
            "status": "failed",
            "failure_code": None,
            "attempts": 0,
        },
    ) in payloads_by_type


def test_post_clips_rejects_invalid_range(client: TestClient, backend_env) -> None:
    task_id, candidate_id = _seed_task_with_candidate(Path(backend_env["data_dir"]))

    response = client.post(
        f"/api/tasks/{task_id}/clips",
        json={"candidate_id": candidate_id, "start_s": 12.0, "end_s": 120.0},
    )

    assert response.status_code == 400
    assert "outside the source duration" in response.json()["detail"]


def _finish_seeded_pipeline(task_id: str, *, other_failure: bool = False) -> str:
    from app.db import session_scope
    from app.models import PipelineRun, Task, TaskJob, TaskStage, utc_now
    from app.services.workstation_queue import begin_queue_mutation, finish_queue_entry
    from app.services.workstation_runs import sync_stage_run

    with session_scope() as session:
        begin_queue_mutation(session)
        session.get(Task, task_id).status = "failed" if other_failure else "success"
        job = session.exec(select(TaskJob).where(TaskJob.task_id == task_id)).one()
        job.status = "failed" if other_failure else "success"
        job.stage_name = "translation" if other_failure else "report"
        run = session.exec(select(PipelineRun).where(PipelineRun.task_id == task_id)).one()
        run.status = job.status
        run.started_at = run.finished_at = utc_now()
        for stage in session.exec(select(TaskStage).where(TaskStage.task_id == task_id)).all():
            stage.status = "success"
            if stage.name == "export":
                stage.status = "skipped"
                stage.summary = "Awaiting user-confirmed export"
            if other_failure and stage.name == "translation":
                stage.status = "failed"
                stage.failure_code = "translation_failed"
            sync_stage_run(session, run.id, stage)
        finish_queue_entry(session, task_id)
        return run.id


@pytest.mark.parametrize("other_failure", [False, True])
def test_manual_failure_retry_keeps_current_projections_and_history_consistent(
    client, backend_env, monkeypatch, other_failure
) -> None:
    from app.db import session_scope
    from app.models import PipelineRun, QueueEntry, StageRun, TaskJob, WorkstationEvent

    task_id, candidate_id = _seed_task_with_candidate(Path(backend_env["data_dir"]))
    original_run_id = _finish_seeded_pipeline(task_id, other_failure=other_failure)
    for succeeds in (False, True):
        def fake_run(args, **kwargs):
            if succeeds:
                Path(args[-1]).write_bytes(b"complete manual clip")
            return subprocess.CompletedProcess(args, 0 if succeeds else 1, "", "encode failed")

        monkeypatch.setattr("subprocess.run", fake_run)
        response = client.post(f"/api/tasks/{task_id}/clips", json={"candidate_id": candidate_id})
        assert response.status_code == (201 if succeeds else 400)
        expected_task = "failed" if other_failure or not succeeds else "success"
        expected_stage = "success" if succeeds else "failed"
        legacy = client.get(f"/api/tasks/{task_id}").json()
        overview = client.get(f"/api/v2/tasks/{task_id}").json()
        assert legacy["status"] == overview["status"] == expected_task
        assert next(stage for stage in legacy["stages"] if stage["name"] == "export")["status"] == expected_stage
        assert next(stage for stage in overview["stages"] if stage["name"] == "export")["status"] == expected_stage
        assert overview["pipeline_run_id"] == original_run_id
        assert len(overview["stages"]) == 7
        with session_scope() as session:
            job = session.exec(select(TaskJob).where(TaskJob.task_id == task_id)).one()
            assert job.status == expected_task
            assert job.stage_name == ("translation" if other_failure else "report" if succeeds else "export")
            assert session.get(QueueEntry, task_id).state == "finished"
            historical = session.get(PipelineRun, original_run_id)
            assert historical.status == ("failed" if other_failure else "success")
            assert session.exec(select(StageRun).where(StageRun.run_id == original_run_id).where(StageRun.name == "export")).one().status == "skipped"
            manual_runs = session.exec(select(PipelineRun).where(PipelineRun.trigger == "manual_export").order_by(PipelineRun.created_at)).all()
            assert [run.status for run in manual_runs] == (["failed", "success"] if succeeds else ["failed"])
            for run in manual_runs:
                assert [stage.name for stage in session.exec(select(StageRun).where(StageRun.run_id == run.id)).all()] == ["export"]
            events = session.exec(select(WorkstationEvent).where(WorkstationEvent.entity_id == task_id)).all()
            assert any(event.event_type == "stage.updated" and json.loads(event.payload_json)["status"] == expected_stage for event in events)


@pytest.mark.parametrize("state", ["cancelled", "running", "control", "queue", "job", "stage", "run", "cancel_request"])
def test_manual_export_rejects_cancelled_or_owned_execution(client, backend_env, monkeypatch, state) -> None:
    from app.db import session_scope
    from app.models import Task, TaskExecutionControl, TaskJob, TaskStage, QueueEntry, PipelineRun

    task_id, candidate_id = _seed_task_with_candidate(Path(backend_env["data_dir"]))
    with session_scope() as session:
        if state in {"cancelled", "running"}:
            session.get(Task, task_id).status = state
        if state == "control":
            session.add(TaskExecutionControl(task_id=task_id, execution_token="worker-owner"))
        if state == "cancel_request":
            session.add(TaskExecutionControl(task_id=task_id, cancel_requested=True))
        if state == "run":
            session.exec(select(PipelineRun).where(PipelineRun.task_id == task_id)).one().status = "running"
        if state == "queue":
            session.get(QueueEntry, task_id).state = "running"
        if state == "job":
            session.exec(select(TaskJob).where(TaskJob.task_id == task_id)).one().status = "running"
        if state == "stage":
            session.exec(select(TaskStage).where(TaskStage.task_id == task_id).where(TaskStage.name == "asr")).one().status = "running"
    def must_not_encode(*args, **kwargs):
        raise AssertionError("active/cancelled task must not encode")
    monkeypatch.setattr("subprocess.run", must_not_encode)
    assert client.post(f"/api/tasks/{task_id}/clips", json={"candidate_id": candidate_id}).status_code == 400


def test_new_retry_hides_previous_manual_result(client, backend_env, monkeypatch) -> None:
    from app.db import session_scope
    from app.repositories.tasks import retry_task_from_stage

    task_id, candidate_id = _seed_task_with_candidate(Path(backend_env["data_dir"]))
    _finish_seeded_pipeline(task_id)
    monkeypatch.setattr("subprocess.run", lambda args, **kwargs: subprocess.CompletedProcess(args, 1, "", "failed"))
    assert client.post(f"/api/tasks/{task_id}/clips", json={"candidate_id": candidate_id}).status_code == 400
    with session_scope() as session:
        retry_task_from_stage(session, task_id, "export")
    overview = client.get(f"/api/v2/tasks/{task_id}").json()
    assert overview["status"] == "pending"
    assert next(stage for stage in overview["stages"] if stage["name"] == "export")["status"] == "pending"


@pytest.mark.parametrize("mutation", ["requeue", "cancel", "worker", "other_queue"])
def test_publication_rechecks_task_ownership_without_locking_encoder(client, backend_env, monkeypatch, mutation) -> None:
    from app.db import session_scope
    from app.models import PipelineRun, QueueEntry, Task, TaskJob, TaskStage
    from app.repositories.tasks import create_task, retry_task_from_stage
    from app.services.workstation_queue import begin_queue_mutation

    task_id, candidate_id = _seed_task_with_candidate(Path(backend_env["data_dir"]))
    _finish_seeded_pipeline(task_id)
    output = Path(backend_env["data_dir"]) / "tasks" / task_id / "exports" / "clip-00011000-00018000.mp4"
    output.write_bytes(b"previous output")
    def racing_encoder(args, **kwargs):
        with session_scope() as session:
            begin_queue_mutation(session)
            if mutation == "requeue":
                retry_task_from_stage(session, task_id, "export")
            if mutation == "cancel":
                session.get(Task, task_id).status = "cancelled"
            if mutation == "worker":
                session.get(Task, task_id).status = "running"
                session.get(QueueEntry, task_id).state = "running"
                session.exec(select(TaskJob).where(TaskJob.task_id == task_id)).one().status = "running"
            if mutation == "other_queue":
                create_task(session, "https://www.bilibili.com/video/BV1otherqueue")
        Path(args[-1]).write_bytes(b"replacement output")
        return subprocess.CompletedProcess(args, 0, "", "")
    monkeypatch.setattr("subprocess.run", racing_encoder)
    response = client.post(f"/api/tasks/{task_id}/clips", json={"candidate_id": candidate_id})
    allowed = mutation == "other_queue"
    assert response.status_code == (201 if allowed else 400)
    assert output.read_bytes() == (b"replacement output" if allowed else b"previous output")
    with session_scope() as session:
        assert len(session.exec(select(PipelineRun).where(PipelineRun.task_id == task_id).where(PipelineRun.trigger == "manual_export")).all()) == int(allowed)
        stage = session.exec(select(TaskStage).where(TaskStage.task_id == task_id).where(TaskStage.name == "export")).one()
        assert stage.status == ("success" if allowed else "pending" if mutation == "requeue" else "skipped")


def test_commit_failure_rolls_back_manual_state_events_and_bytes(client, backend_env, monkeypatch) -> None:
    from sqlmodel import Session
    from app.db import session_scope
    from app.models import Artifact, PipelineRun, StageRun, Task, TaskJob, TaskStage, WorkstationEvent

    task_id, candidate_id = _seed_task_with_candidate(Path(backend_env["data_dir"]))
    _finish_seeded_pipeline(task_id)
    output = Path(backend_env["data_dir"]) / "tasks" / task_id / "exports" / "clip-00011000-00018000.mp4"
    output.write_bytes(b"previous output")
    def snapshot():
        with session_scope() as session:
            return tuple(tuple(json.dumps(row.model_dump(mode="json"), sort_keys=True) for row in session.exec(select(model)).all()) for model in (Artifact, PipelineRun, StageRun, Task, TaskJob, TaskStage, WorkstationEvent))
    before = snapshot()
    def encode(args, **kwargs):
        Path(args[-1]).write_bytes(b"replacement output")
        return subprocess.CompletedProcess(args, 0, "", "")
    original_commit = Session.commit
    def fail_commit(session):
        if session.exec(select(PipelineRun).where(PipelineRun.trigger == "manual_export")).first():
            raise OSError("injected commit failure")
        original_commit(session)
    monkeypatch.setattr("subprocess.run", encode)
    with monkeypatch.context() as patch:
        patch.setattr(Session, "commit", fail_commit)
        with pytest.raises(OSError, match="injected commit failure"):
            client.post(f"/api/tasks/{task_id}/clips", json={"candidate_id": candidate_id})
    assert snapshot() == before
    assert output.read_bytes() == b"previous output"


@pytest.mark.parametrize("incomplete", ["report", "unexplained_task_failure"])
def test_manual_success_does_not_invent_global_success(client, backend_env, monkeypatch, incomplete) -> None:
    from app.db import session_scope
    from app.models import Task, TaskJob, TaskStage

    task_id, candidate_id = _seed_task_with_candidate(Path(backend_env["data_dir"]))
    _finish_seeded_pipeline(task_id)
    with session_scope() as session:
        session.get(Task, task_id).status = "failed"
        if incomplete == "report":
            stage = session.exec(select(TaskStage).where(TaskStage.task_id == task_id).where(TaskStage.name == "report")).one()
            stage.status = "pending"
            job = session.exec(select(TaskJob).where(TaskJob.task_id == task_id)).one()
            job.status, job.stage_name = "failed", "export"
    def encode(args, **kwargs):
        Path(args[-1]).write_bytes(b"clip")
        return subprocess.CompletedProcess(args, 0, "", "")
    monkeypatch.setattr("subprocess.run", encode)
    assert client.post(f"/api/tasks/{task_id}/clips", json={"candidate_id": candidate_id}).status_code == 201
    assert client.get(f"/api/tasks/{task_id}").json()["status"] == "failed"


def test_starting_pending_pipeline_hides_older_manual_result(client, backend_env, monkeypatch) -> None:
    from app.db import session_scope
    from app.models import PipelineRun, StageRun, utc_now

    task_id, candidate_id = _seed_task_with_candidate(Path(backend_env["data_dir"]))
    monkeypatch.setattr("subprocess.run", lambda args, **kwargs: subprocess.CompletedProcess(args, 1, "", "failed"))
    assert client.post(f"/api/tasks/{task_id}/clips", json={"candidate_id": candidate_id}).status_code == 400
    with session_scope() as session:
        run = session.exec(select(PipelineRun).where(PipelineRun.task_id == task_id).where(PipelineRun.trigger == "create")).one()
        run.status = "running"
        run.started_at = utc_now()
        session.add(StageRun(run_id=run.id, name="export", status="pending"))
        run_id = run.id
    overview = client.get(f"/api/v2/tasks/{task_id}").json()
    assert overview["pipeline_run_id"] == run_id
    assert next(stage for stage in overview["stages"] if stage["name"] == "export")["status"] == "pending"


@pytest.mark.parametrize("job_failure", [False, True])
def test_manual_failure_retry_cannot_acquire_preexisting_global_failure(client, backend_env, monkeypatch, job_failure) -> None:
    from app.db import session_scope
    from app.models import Task, TaskJob, utc_now

    task_id, candidate_id = _seed_task_with_candidate(Path(backend_env["data_dir"]))
    _finish_seeded_pipeline(task_id)
    with session_scope() as session:
        task = session.get(Task, task_id)
        task.status = "failed"
        task.updated_at = utc_now()
        job = session.exec(select(TaskJob).where(TaskJob.task_id == task_id)).one()
        if job_failure:
            job.status, job.stage_name = "failed", "export"
            job.updated_at = job.finished_at = utc_now()
    with session_scope() as session:
        before_job = session.exec(select(TaskJob).where(TaskJob.task_id == task_id)).one().model_dump(mode="json")

    for succeeds in (False, False, True):
        def encode(args, **kwargs):
            if succeeds:
                Path(args[-1]).write_bytes(b"manual output")
            return subprocess.CompletedProcess(args, 0 if succeeds else 1, "", "encode failed")
        monkeypatch.setattr("subprocess.run", encode)
        response = client.post(f"/api/tasks/{task_id}/clips", json={"candidate_id": candidate_id})
        assert response.status_code == (201 if succeeds else 400)
        assert client.get(f"/api/tasks/{task_id}").json()["status"] == "failed"
        assert client.get(f"/api/v2/tasks/{task_id}").json()["status"] == "failed"
        with session_scope() as session:
            job = session.exec(select(TaskJob).where(TaskJob.task_id == task_id)).one()
            assert job.model_dump(mode="json") == before_job


def test_owned_manual_failure_recovers_after_metadata_edit_and_repeated_failure(client, backend_env, monkeypatch) -> None:
    task_id, candidate_id = _seed_task_with_candidate(Path(backend_env["data_dir"]))
    _finish_seeded_pipeline(task_id)
    for succeeds in (False, False, True):
        def encode(args, **kwargs):
            if succeeds:
                Path(args[-1]).write_bytes(b"manual output")
            return subprocess.CompletedProcess(args, 0 if succeeds else 1, "", "encode failed")
        monkeypatch.setattr("subprocess.run", encode)
        response = client.post(f"/api/tasks/{task_id}/clips", json={"candidate_id": candidate_id})
        assert response.status_code == (201 if succeeds else 400)
        assert client.get(f"/api/v2/tasks/{task_id}").json()["status"] == ("success" if succeeds else "failed")
        assert client.patch(f"/api/v2/tasks/{task_id}", json={"title": "Edited during manual recovery", "tags": ["manual-recovery"]}).status_code == 200


@pytest.mark.parametrize("changed_field", ["updated_at", "finished_at"])
def test_changed_job_timestamp_revokes_manual_failure_ownership(client, backend_env, monkeypatch, changed_field) -> None:
    from app.db import session_scope
    from app.models import TaskJob, utc_now

    task_id, candidate_id = _seed_task_with_candidate(Path(backend_env["data_dir"]))
    _finish_seeded_pipeline(task_id)
    monkeypatch.setattr("subprocess.run", lambda args, **kwargs: subprocess.CompletedProcess(args, 1, "", "failed"))
    assert client.post(f"/api/tasks/{task_id}/clips", json={"candidate_id": candidate_id}).status_code == 400
    with session_scope() as session:
        job = session.exec(select(TaskJob).where(TaskJob.task_id == task_id)).one()
        setattr(job, changed_field, utc_now())
    def encode(args, **kwargs):
        Path(args[-1]).write_bytes(b"manual output")
        return subprocess.CompletedProcess(args, 0, "", "")
    monkeypatch.setattr("subprocess.run", encode)
    assert client.post(f"/api/tasks/{task_id}/clips", json={"candidate_id": candidate_id}).status_code == 201
    assert client.get(f"/api/v2/tasks/{task_id}").json()["status"] == "failed"
