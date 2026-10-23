from __future__ import annotations

import json
from collections.abc import Callable
from contextvars import ContextVar
from typing import TypeVar

import httpx
from pydantic import JsonValue
from sqlmodel import Session, select

from app.models_unified import OperationAttempt, OperationStep, UnifiedOperation, UnifiedPublication
from app.services.publication_reuse import reuse_publication
from app.services.task_execution import Execution, ExecutionCancelled, ExternalOutcomeUnknown, WorkflowFailure
from app.services.task_operations import begin_step, canonical, digest
from app.services.task_publication import Publisher
from app.services.unified_database import begin_unified_mutation
from app.services.unified_files import checked_path

Result = TypeVar('Result')
inside_external_call: ContextVar[bool] = ContextVar('inside_external_call', default=False)


class ProviderRejected(ValueError):
    pass


def external_value(execution: Execution, identity: JsonValue, action: Callable[[], Result],
                   encode: Callable[[Result], JsonValue], decode: Callable[[JsonValue], Result]) -> Result:
    checksum = digest(canonical(identity))
    key = 'external:' + checksum
    metadata: dict[str, JsonValue] = {'external_request': True, 'request_sha256': checksum}
    reused = reuse_publication(execution, key, metadata=metadata)
    if reused is not None:
        member = next(member for member in reused.outputs if member.role == 'response')
        content = checked_path(execution.root, member.target).read_bytes()
        if digest(content) != member.sha256:
            raise ExternalOutcomeUnknown()
        return decode(json.loads(content))
    with Session(execution.engine) as session:
        prior = session.exec(select(UnifiedPublication).join(OperationStep, UnifiedPublication.step_id == OperationStep.id)
            .join(UnifiedOperation, UnifiedPublication.operation_id == UnifiedOperation.id).where(
                OperationStep.step_key == key, UnifiedOperation.task_id == execution.task_id,
                UnifiedPublication.state == 'committed')).first()
        attempt = session.get(OperationAttempt, execution.token)
        if prior is not None and (attempt is None or not attempt.external_retry_acknowledged):
            raise ExternalOutcomeUnknown()
    execution.check()
    with Session(execution.engine) as session:
        step = begin_step(session, execution.operation_id, execution.token, key, ('response',), metadata=metadata)
        step_id = step.id
        session.commit()
    context = inside_external_call.set(True)
    action_started = False
    try:
        execution.check()
        action_started = True
        value = action()
        output = execution.staging(key) / 'response.json'
        output.write_text(canonical(encode(value)), encoding='utf-8')
        execution.publish(key, {'response': output}, metadata=metadata)
        return value
    except ExecutionCancelled:
        _failed(execution, step_id, 'external_outcome_unknown_possible_repeat_charge' if action_started else 'cancelled_before_request')
        if action_started:
            raise ExternalOutcomeUnknown() from None
        raise
    except ProviderRejected:
        _failed(execution, step_id, 'provider_rejected')
        raise WorkflowFailure('provider_rejected') from None
    except (OSError, ValueError, RuntimeError, httpx.HTTPError):
        registered = _failed(execution, step_id, 'external_outcome_unknown_possible_repeat_charge')
        raise ExternalOutcomeUnknown(response_registered=registered) from None
    finally:
        inside_external_call.reset(context)


def _failed(execution: Execution, step_id: str, code: str) -> bool:
    with Session(execution.engine) as session:
        records = session.exec(select(UnifiedPublication).where(UnifiedPublication.step_id == step_id,
            UnifiedPublication.state == 'committed')).all()
        identifiers = [record.id for record in records]
    if identifiers:
        for identifier in identifiers:
            try:
                Publisher(execution.engine, execution.root).registered(identifier)
                return True
            except (OSError, ValueError):
                continue
        return False
    with Session(execution.engine) as session:
        begin_unified_mutation(session)
        step = session.get(OperationStep, step_id)
        if step is not None:
            step.state, step.failure_code = 'interrupted', code
            session.add(step)
            session.commit()
    return False
