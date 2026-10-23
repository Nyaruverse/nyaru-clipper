from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from sqlmodel import Session, SQLModel, create_engine, select

from app.models import Task, TaskJob, WorkstationEvent
from app.models_unified import OperationAttempt, TaskBinding, UnifiedOperation
from app.services.task_operations import (
    OperationConflict, bind_task, claim_operation, complete_operation, enqueue_operation,
    retry_operation, set_admissions, request_cancel,
)


def database(tmp_path: Path):
    engine = create_engine(f"sqlite:///{tmp_path / 'state.sqlite3'}")
    SQLModel.metadata.create_all(engine)
    return engine


def test_identity_idempotence_and_activated_conflict(tmp_path: Path) -> None:
    engine = database(tmp_path)
    instance = uuid4()
    with Session(engine) as session:
        first = bind_task(session, instance, "equal", "generation-a", origin="native")
        same = bind_task(session, instance, "equal", "generation-a", origin="native")
        other = bind_task(session, uuid4(), "equal", "generation-a", origin="native")
        assert first.task_id == same.task_id != other.task_id
        session.commit()
    with Session(engine) as session:
        with pytest.raises(OperationConflict, match="generation"):
            bind_task(session, instance, "equal", "generation-b", origin="native")
        session.rollback()
        assert len(session.exec(select(TaskBinding)).all()) == 2
        assert len(session.exec(select(Task)).all()) == 2


def test_paused_queue_attempts_tokens_and_child_publication_boundary(tmp_path: Path) -> None:
    engine = database(tmp_path)
    with Session(engine) as session:
        binding = bind_task(session, uuid4(), "new", "g", origin="native")
        operation = enqueue_operation(session, binding.task_id, "process_recording", {"language": "ja"})
        operation_id = operation.id
        session.commit()
    with Session(engine) as session:
        assert claim_operation(session) is None
        set_admissions(session, paused=False)
        session.commit()
    with Session(engine) as session:
        claim = claim_operation(session)
        assert claim is not None and claim.id == operation_id and claim.attempt == 1
        first_token = claim.execution_token
        session.commit()
    with Session(engine) as session:
        complete_operation(session, operation_id, first_token, "failed", failure_code="translation_failed")
        session.commit()
    with Session(engine) as session:
        retry_operation(session, operation_id)
        session.commit()
    with Session(engine) as session:
        claim = claim_operation(session)
        assert claim is not None and claim.attempt == 2 and claim.execution_token != first_token
        second_token = claim.execution_token
        session.commit()
    with Session(engine) as session:
        with pytest.raises(OperationConflict, match="token"):
            complete_operation(session, operation_id, first_token, "succeeded")
        session.rollback()
        request_cancel(session, operation_id)
        session.commit()
    with Session(engine) as session:
        assert claim_operation(session) is None
        complete_operation(session, operation_id, second_token, "cancelled")
        session.commit()
        attempts = session.exec(select(OperationAttempt).order_by(OperationAttempt.attempt)).all()
        assert [(row.attempt, row.state) for row in attempts] == [(1, "failed"), (2, "cancelled")]
        assert len({row.execution_token for row in attempts}) == 2
        assert len(session.exec(select(WorkstationEvent)).all()) >= 6


def test_legacy_gpu_work_blocks_shared_claim(tmp_path: Path) -> None:
    engine = database(tmp_path)
    with Session(engine) as session:
        binding = bind_task(session, uuid4(), "new", "g", origin="native")
        enqueue_operation(session, binding.task_id, "translate", {})
        session.add(TaskJob(task_id=binding.task_id, stage_name="asr", status="running"))
        set_admissions(session, paused=False)
        session.commit()
    with Session(engine) as session:
        assert claim_operation(session) is None


def test_imported_binding_is_never_implicitly_activated(tmp_path: Path) -> None:
    engine = database(tmp_path)
    with Session(engine) as session:
        binding = bind_task(session, uuid4(), "old", "g", origin="companion")
        assert binding.state == "prepared"
        with pytest.raises(OperationConflict, match="activated"):
            enqueue_operation(session, binding.task_id, "export", {})
        session.rollback()
        assert session.exec(select(UnifiedOperation)).all() == []
