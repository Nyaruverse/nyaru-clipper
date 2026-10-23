import pytest
from sqlmodel import Session, select

from test_terminal_retry_atomicity import database, seed, snapshot


def subtitle(engine, task_id):
    from app.models import Artifact
    from app.services.storage import ensure_task_dirs
    path = ensure_task_dirs(task_id)["work"] / "subtitles.zh-ja.srt"
    path.write_bytes(b"previous translation")
    with Session(engine) as session:
        session.add(Artifact(task_id=task_id, stage_name="translation", kind="srt", path=str(path)))
        session.commit()
    return path


def test_rollback_preserves_accepted_retry_files_and_rows(database):
    from app.repositories.tasks import retry_task_from_stage
    seed(database, "retry", status="success", queue="finished")
    path = subtitle(database, "retry")
    before = snapshot(database, "retry")
    with Session(database) as session:
        retry_task_from_stage(session, "retry", "translation")
        assert path.exists()
        session.rollback()
        session.commit()
    assert snapshot(database, "retry") == before
    assert path.read_bytes() == b"previous translation"


def test_cleanup_io_failure_is_retried_before_worker_claim(database, monkeypatch):
    from pathlib import Path
    from app.models import Artifact, Task
    from app.repositories.tasks import retry_task_from_stage
    from app.worker import claim_next_job
    seed(database, "retry", status="success", queue="finished")
    path = subtitle(database, "retry")
    original_unlink = Path.unlink

    def fail_unlink(self, *args, **kwargs):
        if self == path:
            raise OSError("injected cleanup failure")
        return original_unlink(self, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", fail_unlink)
    with Session(database) as session:
        retry_task_from_stage(session, "retry", "translation")
        session.commit()
    with Session(database) as session:
        assert session.get(Task, "retry").status == "pending"
        assert session.exec(select(Artifact).where(Artifact.task_id == "retry")).all()
    with pytest.raises(OSError, match="injected"):
        claim_next_job()
    assert path.read_bytes() == b"previous translation"
    monkeypatch.setattr(Path, "unlink", original_unlink)
    assert claim_next_job().task_id == "retry"
    assert not path.exists()
    with Session(database) as session:
        assert not session.exec(select(Artifact).where(Artifact.task_id == "retry")).all()


def test_delayed_postcommit_cleanup_cannot_remove_new_worker_output(database, monkeypatch):
    from app.models import PipelineRun
    from app.repositories.tasks import retry_task_from_stage
    from app.services import storage
    from app.worker import claim_next_job
    seed(database, "retry", status="success", queue="finished")
    path = subtitle(database, "retry")
    cleanup = storage._cleanup_committed_retries
    monkeypatch.setattr(storage, "_cleanup_committed_retries", lambda session: None)
    with Session(database) as session:
        retry_task_from_stage(session, "retry", "translation")
        session.commit()
        assert path.exists()
        assert claim_next_job().task_id == "retry"
        path.write_bytes(b"new worker translation")
        cleanup(session)
        assert path.read_bytes() == b"new worker translation"
    with Session(database) as session:
        assert len(session.exec(select(PipelineRun).where(PipelineRun.task_id == "retry")).all()) == 2


def test_legacy_http_rejection_preserves_snapshot(database):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.api.routes.tasks import router
    seed(database, "rejected", status="success", queue="running")
    path = subtitle(database, "rejected")
    before = snapshot(database, "rejected")
    app = FastAPI()
    app.include_router(router)
    with TestClient(app) as client:
        response = client.post("/tasks/rejected/retry", json={"stage_name": "translation"})
    assert response.status_code == 409
    assert snapshot(database, "rejected") == before
    assert path.read_bytes() == b"previous translation"


def test_injected_late_conflict_rolls_back_only_one_batch_item(database, monkeypatch):
    from app.api.routes.workstation_tasks import BulkTaskMutationRequest, bulk_task_mutation_endpoint
    from app.services import workstation_queue
    seed(database, "accepted", status="success", queue="finished")
    seed(database, "rejected", status="success", queue="finished")
    path = subtitle(database, "rejected")
    before = snapshot(database, "rejected")
    requeue = workstation_queue.requeue_task

    def late_conflict(session, task_id):
        if task_id == "rejected":
            raise workstation_queue.QueueConflict(workstation_queue.get_queue_snapshot(session), "injected late conflict")
        return requeue(session, task_id)

    monkeypatch.setattr(workstation_queue, "requeue_task", late_conflict)
    with Session(database) as session:
        result = bulk_task_mutation_endpoint(BulkTaskMutationRequest(operation="requeue", task_ids=["accepted", "rejected"]), session)
    assert [item.status for item in result.results] == ["success", "rejected"]
    assert snapshot(database, "rejected") == before
    assert path.read_bytes() == b"previous translation"
