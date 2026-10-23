from __future__ import annotations

import hashlib
import json
import os
from typing import Literal
from uuid import UUID, uuid4, uuid5

from pydantic import JsonValue
from sqlmodel import Session, select

from app.models import Task, TaskExecutionControl, TaskJob, utc_now
from app.models_unified import (
    OperationAttempt, OperationProcess, OperationStep, TaskBinding, UnifiedOperation, UnifiedPublication, UnifiedRuntime,
)
from app.services.workstation_events import publish_event, publish_task_updated
from app.services.unified_database import begin_unified_mutation

OperationKind = Literal["process_recording", "process_live", "translate", "export"]
TerminalState = Literal["succeeded", "failed", "interrupted", "cancelled"]


class OperationConflict(ValueError):
    pass


def canonical(value: JsonValue) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value: str | bytes) -> str:
    return hashlib.sha256(value.encode() if isinstance(value, str) else value).hexdigest()


def runtime(session: Session) -> UnifiedRuntime:
    state = session.get(UnifiedRuntime, 1)
    if state is None:
        state = UnifiedRuntime(instance_id=str(uuid4()))
        session.add(state)
        session.flush()
    return state


def bind_task(
    session: Session, source_instance_id: UUID, legacy_id: str, generation: str, *,
    origin: Literal["native", "companion", "workstation"], context_json: str = "{}",
) -> TaskBinding:
    begin_unified_mutation(session)
    task_id = uuid5(source_instance_id, legacy_id).hex
    binding = session.get(TaskBinding, task_id)
    if binding is not None:
        if binding.source_generation != generation:
            raise OperationConflict("source generation conflict; existing task preserved")
        return binding
    if session.get(Task, task_id) is not None:
        raise OperationConflict("task identity already exists without a binding")
    session.add(Task(id=task_id, source_url="unified:local", normalized_source_url=f"unified:{task_id}"))
    session.flush()
    binding = TaskBinding(
        task_id=task_id, source_instance_id=str(source_instance_id), legacy_id=legacy_id,
        source_generation=generation, origin=origin, context_json=context_json,
        state="activated" if origin == "native" else "prepared",
    )
    session.add(binding)
    session.flush()
    return binding


def _changed(session: Session, operation: UnifiedOperation) -> None:
    from app.services.migration_groups import record_new_write
    record_new_write(session)
    operation.updated_at = utc_now()
    state = runtime(session)
    state.revision += 1
    session.add_all([operation, state])
    if operation.kind in {'process_recording', 'process_live'}:
        task = session.get(Task, operation.task_id)
        if task is not None:
            task.status = {'queued': 'pending', 'paused': 'pending', 'running': 'running', 'succeeded': 'success',
                'failed': 'failed', 'interrupted': 'failed', 'cancelled': 'cancelled'}[operation.state]
            task.updated_at = operation.updated_at
            session.add(task)
            publish_task_updated(session, task)
    publish_event(session, "operation.updated", operation.id, {
        "operation_id": operation.id, "task_id": operation.task_id,
        "kind": operation.kind, "state": operation.state, "attempt": operation.attempt,
        "queue_revision": state.revision,
    })


def enqueue_operation(
    session: Session, task_id: str, kind: OperationKind, snapshot: dict[str, JsonValue], *, priority: int = 0,
) -> UnifiedOperation:
    begin_unified_mutation(session)
    binding = session.get(TaskBinding, task_id)
    if binding is None or binding.state != "activated":
        raise OperationConflict("task is not activated")
    if kind not in {"process_recording", "process_live", "translate", "export"}:
        raise OperationConflict("unsupported operation kind")
    body = canonical(snapshot)
    operations = session.exec(select(UnifiedOperation)).all()
    operation = UnifiedOperation(
        id=uuid4().hex, task_id=task_id, kind=kind, priority=priority,
        position=max((row.position for row in operations), default=0) + 1,
        snapshot_json=body, snapshot_sha256=digest(body),
    )
    session.add(operation)
    _changed(session, operation)
    return operation


def set_admissions(session: Session, *, paused: bool) -> None:
    begin_unified_mutation(session)
    from app.services.migration_groups import record_new_write
    record_new_write(session)
    state = runtime(session)
    state.paused = paused
    state.revision += 1
    session.add(state)
    publish_event(session, "operation.queue", "queue", {"paused": paused, "revision": state.revision})


def claim_operation(session: Session) -> UnifiedOperation | None:
    begin_unified_mutation(session)
    state = runtime(session)
    if state.paused or state.recovering:
        return None
    if session.exec(select(OperationProcess).where(OperationProcess.released == False)).first():
        return None
    if session.exec(select(UnifiedOperation).where(UnifiedOperation.state == "running")).first():
        return None
    if session.exec(select(TaskJob).where(TaskJob.status == "running", TaskJob.gpu_bound == True)).first():
        return None
    if session.exec(select(TaskExecutionControl).where(TaskExecutionControl.active_process_group_id != None)).first():
        return None
    operation = session.exec(select(UnifiedOperation).where(UnifiedOperation.state == "queued").order_by(
        UnifiedOperation.priority.desc(), UnifiedOperation.position, UnifiedOperation.created_at,
    )).first()
    if operation is None:
        return None
    binding = session.get(TaskBinding, operation.task_id)
    if binding is None or binding.state != "activated":
        raise OperationConflict("queued task is not activated")
    operation.state = "running"
    operation.attempt += 1
    operation.execution_token = uuid4().hex
    operation.cancel_requested = False
    session.add(OperationAttempt(
        operation_id=operation.id, attempt=operation.attempt, execution_token=operation.execution_token,
        snapshot_sha256=operation.snapshot_sha256,
        owner_pid=os.getpid(),
        external_retry_acknowledged=operation.external_retry_acknowledged,
    ))
    operation.external_retry_acknowledged = False
    _changed(session, operation)
    return operation


def require_token(session: Session, operation_id: str, token: str, *, cancelling: bool = False) -> UnifiedOperation:
    operation = session.get(UnifiedOperation, operation_id)
    if operation is None or operation.state != "running" or operation.execution_token != token:
        raise OperationConflict("execution token is stale")
    if operation.cancel_requested and not cancelling:
        raise OperationConflict("execution token has been cancelled")
    return operation


def request_cancel(session: Session, operation_id: str) -> None:
    begin_unified_mutation(session)
    operation = session.get(UnifiedOperation, operation_id)
    if operation is None:
        raise KeyError(operation_id)
    if operation.state == "running":
        operation.cancel_requested = True
    elif operation.state in {"queued", "paused"}:
        operation.state = "cancelled"
    else:
        return
    _changed(session, operation)


def complete_operation(
    session: Session, operation_id: str, token: str, state: TerminalState, *, failure_code: str | None = None,
) -> None:
    begin_unified_mutation(session)
    operation = require_token(session, operation_id, token, cancelling=state in {"cancelled", "interrupted", "failed"})
    if operation.active_process_group_id is not None:
        raise OperationConflict("process group must be released before completion")
    if session.exec(select(OperationProcess).where(OperationProcess.operation_id == operation_id, OperationProcess.released == False)).first():
        raise OperationConflict("owned process groups must be released before completion")
    if state == "succeeded":
        steps = session.exec(select(OperationStep).where(
            OperationStep.operation_id == operation_id, OperationStep.attempt == operation.attempt,
        )).all()
        if not steps or any(step.state != "succeeded" for step in steps):
            raise OperationConflict("workflow has unfinished or failed child steps")
        if session.exec(select(UnifiedPublication).where(
            UnifiedPublication.operation_id == operation_id,
            UnifiedPublication.attempt == operation.attempt, UnifiedPublication.state != "committed",
        )).first():
            raise OperationConflict("workflow has uncommitted publications")
    attempt = session.get(OperationAttempt, token)
    if attempt is None:
        raise OperationConflict("attempt registration missing")
    attempt.state, attempt.finished_at = state, utc_now()
    operation.state, operation.failure_code = state, failure_code
    session.add(attempt)
    _changed(session, operation)


def retry_operation(session: Session, operation_id: str, *, acknowledge_external_outcome: bool = False) -> UnifiedOperation:
    begin_unified_mutation(session)
    operation = session.get(UnifiedOperation, operation_id)
    if operation is None:
        raise KeyError(operation_id)
    if operation.state not in {"failed", "interrupted", "cancelled"} or operation.active_process_group_id is not None:
        raise OperationConflict("operation is not released for retry")
    if json.loads(operation.snapshot_json).get('config', {}).get('upload_pending'):
        raise OperationConflict('incomplete upload requires selecting the file again as a new task')
    if operation.failure_code == 'external_outcome_unknown_possible_repeat_charge' and not acknowledge_external_outcome:
        raise OperationConflict('acknowledge the uncertain external outcome and possible repeat charge before retrying')
    operation.external_retry_acknowledged = acknowledge_external_outcome
    operation.state, operation.execution_token, operation.failure_code = "queued", None, None
    operation.cancel_requested = False
    _changed(session, operation)
    return operation


def begin_step(session: Session, operation_id: str, token: str, key: str, required_roles: tuple[str, ...], *,
               metadata: dict[str, JsonValue] | None = None) -> OperationStep:
    begin_unified_mutation(session)
    operation = require_token(session, operation_id, token)
    if len(set(required_roles)) != len(required_roles) or any(not role for role in required_roles):
        raise OperationConflict("required output roles must be unique and nonempty")
    step_id = uuid5(UUID(operation_id), f"{operation.attempt}:{key}").hex
    step = session.get(OperationStep, step_id)
    roles = canonical(list(required_roles))
    metadata_json = canonical(metadata or {})
    if step is not None:
        if step.required_roles_json != roles or step.metadata_json != metadata_json:
            raise OperationConflict("child output contract changed")
        return step
    step = OperationStep(id=step_id, operation_id=operation_id, attempt=operation.attempt,
        execution_token=token, step_key=key, required_roles_json=roles, metadata_json=metadata_json)
    session.add(step)
    session.flush()
    return step


def reorder_operations(session: Session, ordered_ids: list[str], expected_revision: int) -> None:
    begin_unified_mutation(session)
    from app.services.migration_groups import record_new_write
    record_new_write(session)
    state = runtime(session)
    rows = session.exec(select(UnifiedOperation).where(UnifiedOperation.state == "queued")).all()
    by_id = {row.id: row for row in rows}
    if state.revision != expected_revision or len(set(ordered_ids)) != len(ordered_ids) or set(ordered_ids) != set(by_id):
        raise OperationConflict("queue revision or waiting operation set changed")
    priorities = [by_id[identifier].priority for identifier in ordered_ids]
    if priorities != sorted(priorities, reverse=True):
        raise OperationConflict("reorder within priority groups; change priority separately")
    for position, identifier in enumerate(ordered_ids, start=1):
        by_id[identifier].position = position
        session.add(by_id[identifier])
    state.revision += 1
    session.add(state)
    publish_event(session, "operation.queue", "queue", {"revision": state.revision})


def set_operation_waiting(session: Session, operation_id: str, state: Literal["queued", "paused"], *, priority: int | None = None) -> None:
    begin_unified_mutation(session)
    operation = session.get(UnifiedOperation, operation_id)
    if operation is None:
        raise KeyError(operation_id)
    if operation.state not in {"queued", "paused"}:
        raise OperationConflict("running or terminal operation cannot be reordered or paused")
    if state == 'queued' and json.loads(operation.snapshot_json).get('config', {}).get('upload_pending'):
        raise OperationConflict('upload has not completed; waiting operation cannot run')
    operation.state = state
    if priority is not None:
        operation.priority = priority
    _changed(session, operation)
