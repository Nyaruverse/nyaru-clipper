from __future__ import annotations

from collections.abc import Callable, Iterator
from pathlib import Path

from fastapi import APIRouter, Body, Depends, HTTPException
from sqlmodel import Session, select
from pydantic import JsonValue

from app.api.schemas.operations import (
    OperationInput, OperationsSnapshot, OperationView, QueueAdmissions, ReorderOperations, RetryOperation, WaitingOperation,
)
from app.db import get_session
from app.models_unified import TaskBinding, UnifiedOperation
from app.services.task_operations import (
    OperationConflict, enqueue_operation, reorder_operations, request_cancel, retry_operation,
    runtime, set_admissions, set_operation_waiting,
)
from app.services.unified_database import begin_unified_mutation
from app.settings import Settings, get_settings
from app.services.task_requests import freeze_request


def configuration_snapshot(payload: OperationInput, *, model: Path | None = None, threads: int = 4,
                           settings: Settings | None = None) -> dict[str, JsonValue]:
    from app.services.public_runtime_settings import PUBLIC_FIELDS
    settings = settings or get_settings()
    configuration = settings.model_dump(mode="json", include=PUBLIC_FIELDS)
    if payload.kind == 'process_live' or (payload.kind == "process_recording" and payload.engine == "whisper.cpp"):
        from app.arctime.local_asr import DEFAULT_MODEL
        from app.services.unified_files import file_sha256
        selected = model or DEFAULT_MODEL
        configuration.update(model_path=str(selected), model_sha256=(
            file_sha256(selected) if selected.is_file() and not selected.is_symlink() else None), threads=threads)
    return configuration


def snapshot(session: Session) -> OperationsSnapshot:
    begin_unified_mutation(session)
    state = runtime(session)
    rows = session.exec(select(UnifiedOperation).order_by(
        UnifiedOperation.priority.desc(), UnifiedOperation.position, UnifiedOperation.created_at,
    )).all()
    result = OperationsSnapshot(revision=state.revision, paused=state.paused, recovering=state.recovering,
        operations=tuple(OperationView.model_validate(row) for row in rows))
    session.commit()
    return result


def operations_router(session_dependency: Callable[[], Iterator[Session]], *,
                      configuration: Callable[[OperationInput], dict[str, JsonValue]] = configuration_snapshot,
                      input_root: Path | None = None) -> APIRouter:
    router = APIRouter(prefix="/v2/operations", tags=["operations"])

    @router.get("", response_model=OperationsSnapshot)
    def list_operations(session: Session = Depends(session_dependency)) -> OperationsSnapshot:
        return snapshot(session)

    @router.post("", status_code=202, response_model=OperationView)
    def create_operation(payload: OperationInput, session: Session = Depends(session_dependency)) -> OperationView:
        body = payload.model_dump(mode="json", exclude={"task_id", "kind"})
        try:
            begin_unified_mutation(session)
            binding = session.get(TaskBinding, payload.task_id)
            if binding is None or binding.state != 'activated':
                raise OperationConflict('task is not activated')
            session.commit()
            from app.services.storage import get_tasks_root
            body = freeze_request(input_root or get_tasks_root(), payload.task_id, body)
            operation = enqueue_operation(session, payload.task_id, payload.kind, {"input": body, "config": configuration(payload)})
            result = OperationView.model_validate(operation)
            session.commit()
            return result
        except OperationConflict as error:
            raise HTTPException(409, str(error)) from None

    @router.post("/queue", response_model=OperationsSnapshot)
    def admissions(payload: QueueAdmissions, session: Session = Depends(session_dependency)) -> OperationsSnapshot:
        begin_unified_mutation(session)
        if runtime(session).revision != payload.expected_revision:
            raise HTTPException(409, "Queue revision is stale")
        set_admissions(session, paused=payload.paused)
        return snapshot(session)

    @router.post("/reorder", response_model=OperationsSnapshot)
    def reorder(payload: ReorderOperations, session: Session = Depends(session_dependency)) -> OperationsSnapshot:
        try:
            reorder_operations(session, payload.ordered_ids, payload.expected_revision)
            return snapshot(session)
        except OperationConflict as error:
            raise HTTPException(409, str(error)) from None

    @router.post("/{operation_id}/cancel", response_model=OperationsSnapshot)
    def cancel(operation_id: str, session: Session = Depends(session_dependency)) -> OperationsSnapshot:
        try:
            request_cancel(session, operation_id)
            return snapshot(session)
        except KeyError:
            raise HTTPException(404, "Operation not found") from None

    @router.post("/{operation_id}/retry", response_model=OperationsSnapshot)
    def retry(operation_id: str, payload: RetryOperation = Body(default=RetryOperation()),
              session: Session = Depends(session_dependency)) -> OperationsSnapshot:
        try:
            retry_operation(session, operation_id, acknowledge_external_outcome=payload.acknowledge_external_outcome)
            return snapshot(session)
        except KeyError:
            raise HTTPException(404, "Operation not found") from None
        except OperationConflict as error:
            raise HTTPException(409, str(error)) from None

    @router.post("/{operation_id}/waiting", response_model=OperationsSnapshot)
    def waiting(operation_id: str, payload: WaitingOperation, session: Session = Depends(session_dependency)) -> OperationsSnapshot:
        try:
            set_operation_waiting(session, operation_id, payload.state, priority=payload.priority)
            return snapshot(session)
        except KeyError:
            raise HTTPException(404, "Operation not found") from None
        except OperationConflict as error:
            raise HTTPException(409, str(error)) from None

    return router


router = operations_router(get_session)
