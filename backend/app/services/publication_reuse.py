from __future__ import annotations

import json

from pydantic import JsonValue
from sqlmodel import Session, select

from app.models_unified import OperationStep, UnifiedOperation, UnifiedPublication
from app.services.publication_receipts import PreparedReceipt
from app.services.task_execution import Execution
from app.services.task_operations import begin_step, canonical, require_token
from app.services.task_publication import Publisher
from app.services.unified_database import begin_unified_mutation
from app.services.workstation_events import publish_event


def reuse_publication(execution: Execution, key: str, *, metadata: dict[str, JsonValue] | None = None) -> PreparedReceipt | None:
    with Session(execution.engine) as session:
        rows = session.exec(select(UnifiedPublication).join(OperationStep, UnifiedPublication.step_id == OperationStep.id)
            .join(UnifiedOperation, UnifiedPublication.operation_id == UnifiedOperation.id)
            .where(OperationStep.step_key == key, UnifiedOperation.task_id == execution.task_id,
                   UnifiedPublication.state == 'committed')).all()
        identifiers = [row.id for row in rows]
    for identifier in identifiers:
        try:
            receipt = Publisher(execution.engine, execution.root).registered(identifier)
        except (OSError, ValueError):
            continue
        with Session(execution.engine) as session:
            begin_unified_mutation(session)
            require_token(session, execution.operation_id, execution.token)
            prior = session.get(OperationStep, receipt.step_id)
            if prior is None or (metadata is not None and prior.metadata_json != canonical(metadata)):
                continue
            step = begin_step(session, execution.operation_id, execution.token, key,
                tuple(sorted(member.role for member in receipt.outputs)), metadata=json.loads(prior.metadata_json))
            if step.id == receipt.step_id:
                return receipt
            step.state, step.reused_publication_id = 'succeeded', identifier
            session.add(step)
            publish_event(session, 'publication.reused', identifier, {'publication_id': identifier, 'operation_id': execution.operation_id})
            session.commit()
            return receipt
    return None
