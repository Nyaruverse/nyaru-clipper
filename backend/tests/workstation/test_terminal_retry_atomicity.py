import pytest
from sqlalchemy import event
from sqlmodel import Session, SQLModel, select


@pytest.fixture()
def database(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("APP_DATABASE_URL", f"sqlite:///{tmp_path / 'db.sqlite'}")
    import app.models
    from app.db import get_engine, reset_db_runtime
    reset_db_runtime()
    engine = get_engine()
    SQLModel.metadata.create_all(engine)
    yield engine
    engine.dispose()
    reset_db_runtime()


def seed(engine, task_id, *, status="pending", queue="queued"):
    from app.models import CANONICAL_STAGES, PipelineRun, QueueEntry, Task, TaskJob, TaskStage
    with Session(engine) as session:
        session.add(Task(id=task_id, source_url="local://fixture", normalized_source_url=f"local://{task_id}", status=status))
        session.add(TaskJob(task_id=task_id, stage_name="report", status=status))
        session.add(QueueEntry(task_id=task_id, position=1, state=queue))
        session.add(PipelineRun(id=f"run-{task_id}", task_id=task_id, status="pending"))
        session.add_all(TaskStage(task_id=task_id, name=name, status="success" if name != "report" else "pending") for name in CANONICAL_STAGES)
        session.commit()


def assert_terminal(engine, task_id, status):
    from app.models import PipelineRun, QueueEntry, Task, TaskJob
    with Session(engine) as check:
        assert check.get(Task, task_id).status == status
        assert check.exec(select(TaskJob).where(TaskJob.task_id == task_id)).one().status == status
        assert check.get(QueueEntry, task_id).state == "finished"
        assert check.get(PipelineRun, f"run-{task_id}").status == status


@pytest.mark.parametrize("status", ["success", "failed", "cancelled"])
def test_terminal_commit_is_atomic_and_fresh_worker_claims_next(database, monkeypatch, status):
    from app.models import Task
    from app.services import task_runner
    from app.services.task_control import activate_execution, finalize_cancelled, StaleExecutionTokenError
    from app.worker import claim_next_job
    seed(database, "first")
    seed(database, "next")
    assert claim_next_job().task_id == "first"

    def executor(session, task_id):
        session.commit()  # Real stage executors publish intermediate progress.
        if status == "failed":
            from app.services.pipeline_support import set_stage_status
            set_stage_status(session, task_id=task_id, stage_name="report", status="failed", summary="injected stage failure")
            session.commit()
            raise ValueError("injected stage failure")
        if status == "cancelled":
            finalize_cancelled(session, task_id=task_id, execution_token="fixture")
            session.commit()  # Subprocess cancellation owns this commit.
            raise StaleExecutionTokenError(task_id=task_id, execution_token="fixture", current_execution_token=None)

    monkeypatch.setattr(task_runner, "STAGE_EXECUTORS", {name: executor for name in task_runner.CANONICAL_STAGE_ORDER})
    observations = []
    with Session(database) as session:
        activate_execution(session, task_id="first", execution_token="fixture")

        def observe(_session):
            with Session(database) as check:
                current = check.get(Task, "first").status
            if current in {"success", "failed", "cancelled"}:
                assert_terminal(database, "first", current)
                observations.append(current)

        event.listen(session, "after_commit", observe)
        if status == "failed":
            with pytest.raises(ValueError, match="injected"):
                task_runner.run_task_pipeline(session, "first", start_stage_name="report", claimed_stage_running=True, execution_token="fixture")
        else:
            task_runner.run_task_pipeline(session, "first", start_stage_name="report", claimed_stage_running=True, execution_token="fixture")
    assert observations
    assert_terminal(database, "first", status)
    assert claim_next_job().task_id == "next"


@pytest.mark.parametrize("status", ["success", "failed", "cancelled"])
def test_legacy_terminal_queue_repair_is_idempotent(database, status):
    from app.models import PipelineRun, QueueState
    from app.worker import claim_next_job
    seed(database, "old", status=status, queue="running")
    with Session(database) as session:
        run = session.get(PipelineRun, "run-old")
        run.status = "running"
        session.add(run)
        session.commit()
    assert claim_next_job() is None
    assert_terminal(database, "old", status)
    with Session(database) as session:
        revision = session.get(QueueState, 1).revision
    assert claim_next_job() is None
    with Session(database) as session:
        assert session.get(QueueState, 1).revision == revision
    seed(database, "next")
    assert claim_next_job().task_id == "next"


@pytest.mark.parametrize("status", ["success", "failed", "cancelled"])
@pytest.mark.parametrize("history", ["absent", "terminal"])
@pytest.mark.parametrize("stage_status", ["pending", "running", "success", "failed", "cancelled", "skipped"])
def test_legacy_stage_repair_without_active_run(database, status, history, stage_status):
    from app.models import PipelineRun, QueueEntry, QueueState, Task, TaskStage
    from app.worker import claim_next_job
    seed(database, "old", status=status, queue="running")
    seed(database, "next")
    with Session(database) as session:
        run = session.get(PipelineRun, "run-old")
        run.status = status
        if history == "absent":
            session.delete(run)
        else:
            session.add(run)
        stage = session.exec(select(TaskStage).where(TaskStage.task_id == "old").where(TaskStage.name == "report")).one()
        stage.status = stage_status
        session.add(stage)
        session.commit()
        session.refresh(stage)
        if history == "terminal":
            session.refresh(run)
        original_stage = stage.model_dump()
        original_run = run.model_dump() if history == "terminal" else None
    assert claim_next_job().task_id == "next"
    with Session(database) as session:
        assert session.get(Task, "old").status == status
        assert session.get(QueueEntry, "old").state == "finished"
        stage = session.exec(select(TaskStage).where(TaskStage.task_id == "old").where(TaskStage.name == "report")).one()
        if stage_status in {"pending", "running"}:
            assert stage.status == status
            assert stage.finished_at is not None
        else:
            assert stage.model_dump() == original_stage
        run = session.get(PipelineRun, "run-old")
        assert (run.model_dump() if run is not None else None) == original_run
        repaired_stage = stage.model_dump()
        revision = session.get(QueueState, 1).revision
    assert claim_next_job() is None
    with Session(database) as session:
        stage = session.exec(select(TaskStage).where(TaskStage.task_id == "old").where(TaskStage.name == "report")).one()
        assert stage.model_dump() == repaired_stage
        assert session.get(QueueState, 1).revision == revision


def snapshot(engine, task_id):
    from app.models import Artifact, PipelineRun, Task, TaskExecutionControl, TaskExecutionProgress, TaskJob, TaskStage, WorkstationEvent
    with Session(engine) as session:
        rows = {}
        for model in (Artifact, PipelineRun, TaskExecutionControl, TaskExecutionProgress, TaskJob, TaskStage):
            rows[model.__name__] = [row.model_dump(mode="json") for row in session.exec(select(model).where(model.task_id == task_id)).all()]
        rows["task"] = session.get(Task, task_id).model_dump(mode="json")
        rows["events"] = [row.model_dump(mode="json") for row in session.exec(select(WorkstationEvent).where(WorkstationEvent.entity_id == task_id)).all()]
        return rows


def test_rejected_mixed_requeue_preserves_all_task_rows_and_files(database):
    from app.api.routes.workstation_tasks import BulkTaskMutationRequest, bulk_task_mutation_endpoint
    from app.models import Artifact
    from app.services.storage import ensure_task_dirs
    seed(database, "rejected", status="success", queue="running")
    seed(database, "accepted", status="success", queue="finished")
    path = ensure_task_dirs("rejected")["work"] / "subtitles.zh-ja.srt"
    path.write_bytes(b"original subtitle")
    with Session(database) as session:
        session.add(Artifact(task_id="rejected", stage_name="translation", kind="srt", path=str(path)))
        session.commit()
    before = snapshot(database, "rejected")
    with Session(database) as session:
        response = bulk_task_mutation_endpoint(BulkTaskMutationRequest(operation="requeue", task_ids=["accepted", "rejected"]), session)
    assert [item.status for item in response.results] == ["success", "rejected"]
    assert snapshot(database, "rejected") == before
    assert path.read_bytes() == b"original subtitle"
