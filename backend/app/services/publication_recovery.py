from __future__ import annotations

import os
import re
import json
from collections.abc import Callable
from typing import TYPE_CHECKING, Literal

from pydantic import ValidationError
from sqlmodel import Session, select

from app.arctime.workflow import exclusive_lock
from app.models_unified import OperationProcess, OperationStep, UnifiedOperation, UnifiedPublication
from app.services.publication_receipts import PreparedReceipt, ReceiptState, recovery_decision
from app.services.task_operations import OperationConflict, canonical, complete_operation, digest, runtime
from app.services.unified_files import checked_path, immutable_bytes
from app.services.unified_database import begin_unified_mutation

if TYPE_CHECKING:
    from app.services.task_publication import Publisher


class Reconciler:
    def __init__(self, publisher: Publisher) -> None:
        self.publisher = publisher
        self.engine, self.root = publisher.engine, publisher.root

    def run(self, *, processes_released: Callable[[UnifiedOperation], bool]) -> list[str]:
        with exclusive_lock(self.publisher.lock):
            self._exclude_claims(processes_released)
            with Session(self.engine) as session:
                unsupported = session.exec(select(UnifiedPublication).where(UnifiedPublication.state.not_in(
                    ['preparing', 'ready', 'committed', 'interrupted', 'blocked']))).first()
                if unsupported is not None:
                    raise OperationConflict('unsupported publication state; preserve the original attempt')
            orphan_decisions = self._discover()
            with Session(self.engine) as session:
                records = session.exec(select(UnifiedPublication).where(UnifiedPublication.state.in_(['preparing', 'ready', 'committed']))).all()
            decisions = orphan_decisions + [self._one(record) for record in records]
            with Session(self.engine) as session:
                begin_unified_mutation(session)
                for operation in session.exec(select(UnifiedOperation).where(UnifiedOperation.state == 'running')).all():
                    if operation.execution_token is None:
                        raise OperationConflict('running operation has no execution token')
                    terminal = 'cancelled' if operation.cancel_requested else 'interrupted'
                    steps = session.exec(select(OperationStep).where(OperationStep.operation_id == operation.id,
                        OperationStep.attempt == operation.attempt)).all()
                    uncertain = any(json.loads(step.metadata_json).get('external_request') is True
                        and step.state != 'succeeded' and step.failure_code not in {'provider_rejected', 'cancelled_before_request'} for step in steps)
                    complete_operation(session, operation.id, operation.execution_token, terminal,
                        failure_code='external_outcome_unknown_possible_repeat_charge' if uncertain else
                        'cancelled' if operation.cancel_requested else 'recovered_unknown_workflow_outcome')
                state = runtime(session)
                state.recovering = ('J00' in orphan_decisions or session.exec(select(UnifiedPublication).where(UnifiedPublication.state == 'blocked')).first() is not None)
                session.add(state)
                session.commit()
            return decisions

    def _exclude_claims(self, processes_released: Callable[[UnifiedOperation], bool]) -> None:
        with Session(self.engine) as session:
            begin_unified_mutation(session)
            state = runtime(session)
            state.recovering = True
            session.add(state)
            session.commit()
        with Session(self.engine) as session:
            begin_unified_mutation(session)
            operations = session.exec(select(UnifiedOperation).where(UnifiedOperation.state == 'running')).all()
            if any(not processes_released(operation) for operation in operations):
                raise OperationConflict('original worker/process groups still own execution')
            for process in session.exec(select(OperationProcess).where(OperationProcess.released == False)).all():
                try:
                    os.killpg(process.process_group_id, 0)
                except ProcessLookupError:
                    process.released = True
                    session.add(process)
                else:
                    raise OperationConflict('original process group still owns execution')
            session.commit()

    def _discover(self) -> list[str]:
        with Session(self.engine) as session:
            known = set(session.exec(select(UnifiedPublication.id)).all())
        issues = []
        receipts = checked_path(self.root, '.unified/receipts')
        for path in sorted(receipts.glob('*.json')) if receipts.is_dir() else []:
            identifier = path.stem
            if identifier in known:
                continue
            try:
                content = checked_path(self.root, path.relative_to(self.root).as_posix()).read_bytes()
                receipt = PreparedReceipt.model_validate_json(content)
                if receipt.publication_id != identifier or canonical(receipt.model_dump(mode='json')).encode() != content:
                    issues.append({'publication_id': identifier if re.fullmatch('[0-9a-f]{64}', identifier) else 'invalid', 'decision': 'J00'})
                    continue
            except (ValueError, OSError):
                issues.append({'publication_id': identifier if re.fullmatch('[0-9a-f]{64}', identifier) else 'invalid', 'decision': 'J00'})
                continue
            with Session(self.engine) as session:
                begin_unified_mutation(session)
                operation = session.get(UnifiedOperation, receipt.operation_id)
                step = session.get(OperationStep, receipt.step_id)
                if operation is None or step is None:
                    issues.append({'publication_id': identifier, 'decision': 'J01'})
                    continue
                session.add(UnifiedPublication(id=identifier, operation_id=receipt.operation_id, step_id=receipt.step_id,
                    attempt=receipt.attempt, execution_token=receipt.execution_token,
                    receipt_json=content.decode(), receipt_sha256=digest(content)))
                session.commit()
                known.add(identifier)
        results = checked_path(self.root, '.unified/results')
        for path in sorted(results.iterdir()) if results.is_dir() else []:
            if path.name not in known and not any(issue['publication_id'] == path.name for issue in issues):
                issues.append({'publication_id': path.name if re.fullmatch('[0-9a-f]{64}', path.name) else 'invalid', 'decision': 'J01'})
        if issues:
            body = canonical({'version': 1, 'issues': issues}).encode()
            immutable_bytes(checked_path(self.root, f'.unified/recovery/orphans-{digest(body)}.json'), body)
        return [issue['decision'] for issue in issues]

    def _one(self, record: UnifiedPublication) -> str:
        try:
            receipt = PreparedReceipt.model_validate_json(record.receipt_json)
        except ValidationError:
            self._failure(record.id, 'J00')
            return 'J00'
        path = self.publisher._receipt_path(record.id)
        status: ReceiptState = 'missing' if not path.exists() else 'valid'
        if digest(record.receipt_json) != record.receipt_sha256 or (status == 'valid' and digest(path.read_bytes()) != record.receipt_sha256):
            status = 'corrupt'
        try:
            outputs, staging = self.publisher._files(receipt)
        except (ValueError, OSError):
            outputs, staging = 'bad', False
        with Session(self.engine) as session:
            operation = session.get(UnifiedOperation, record.operation_id)
            eligible = self.publisher._proof(session, record, receipt)
            if record.state != 'committed':
                eligible = eligible and (operation is not None and operation.state == 'running' and not operation.cancel_requested
                    and operation.attempt == receipt.attempt and operation.execution_token == receipt.execution_token)
        database: Literal['N', 'R', 'C'] = {'preparing': 'N', 'ready': 'R', 'committed': 'C'}[record.state]
        decision = recovery_decision(database, status, outputs, eligible, staging)
        if decision == 'J05':
            self.publisher._ready(receipt)
        if decision in {'J05', 'J08', 'J10'}:
            self.publisher._finish(receipt)
        elif decision != 'J12':
            self._failure(record.id, decision)
        return decision

    def _failure(self, publication_id: str, decision: str) -> None:
        with Session(self.engine) as session:
            begin_unified_mutation(session)
            current = session.get(UnifiedPublication, publication_id)
            if current is None:
                raise OperationConflict('publication disappeared')
            if decision != 'J13':
                current.state = 'interrupted' if decision in {'J01', 'J02', 'J03', 'J06', 'J09'} else 'blocked'
            current.failure_code = decision
            session.add(current)
            session.commit()
