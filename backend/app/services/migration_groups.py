from __future__ import annotations

import json
from typing import Literal
from uuid import uuid4

from pydantic import JsonValue
from sqlmodel import Session, select

from app.models import TaskExecutionControl, TaskJob
from app.models_migration import MigrationBatch, MigrationDependency, MigrationGroup, MigrationMember, MigrationSource
from app.models_unified import OperationProcess, TaskBinding, UnifiedOperation
from app.services.task_operations import OperationConflict, canonical, runtime
from app.services.unified_database import begin_unified_mutation


def create_group(session: Session) -> MigrationGroup:
    begin_unified_mutation(session)
    group = session.exec(select(MigrationGroup).where(MigrationGroup.state != 'thawed')).first()
    if group is not None:
        if group.state != 'open':
            raise OperationConflict('previous migration epoch has an unfinished thaw')
        return group
    group = MigrationGroup(id=str(uuid4()))
    session.add(group)
    session.flush()
    return group


def record_new_write(session: Session) -> None:
    for group in session.exec(select(MigrationGroup).where(MigrationGroup.state != 'thawed')).all():
        if group.state != 'open':
            raise OperationConflict('migration thaw is in progress; writes are prohibited')
        group.new_writes = True
        session.add(group)


def rollback_category(session: Session, group_id: str) -> Literal['R0', 'R1', 'R2']:
    group = session.get(MigrationGroup, group_id)
    if group is None:
        raise OperationConflict('migration root group missing')
    return 'R2' if group.new_writes else 'R1' if group.ever_activated else 'R0'


def cancel_batch(session: Session, batch_id: str) -> MigrationBatch:
    begin_unified_mutation(session)
    batch = session.get(MigrationBatch, batch_id)
    if batch is None or batch.state in {'activated', 'withdrawn'}:
        raise OperationConflict('activated batch requires whole-group rollback')
    batch.state = 'cancelled'
    for member in session.exec(select(MigrationMember).where(MigrationMember.batch_id == batch_id)).all():
        member.state = 'cancelled'
        session.add(member)
    for edge in session.exec(select(MigrationDependency).where(MigrationDependency.batch_id == batch_id)).all():
        edge.active = False
        session.add(edge)
    session.add(batch)
    return batch


def require_quiescent(session: Session) -> None:
    if not runtime(session).paused or runtime(session).recovering:
        raise OperationConflict('queue must be paused and recovery completed')
    if (session.exec(select(UnifiedOperation).where(UnifiedOperation.state == 'running')).first()
            or session.exec(select(OperationProcess).where(OperationProcess.released == False)).first()
            or session.exec(select(TaskJob).where(TaskJob.status.in_(['pending', 'running']))).first()
            or session.exec(select(TaskExecutionControl).where(TaskExecutionControl.active_process_group_id != None)).first()):
        raise OperationConflict('unreleased operation or old execution eligibility remains')


def withdraw_group(session: Session, group_id: str) -> dict[str, JsonValue]:
    begin_unified_mutation(session)
    group = session.get(MigrationGroup, group_id)
    if group is None or group.state == 'thawed':
        raise OperationConflict('migration group is closed or missing')
    if rollback_category(session, group_id) == 'R2':
        raise OperationConflict('R2 requires independent snapshot recovery; originals stay sealed')
    require_quiescent(session)
    if group.thaw_receipt_json is not None:
        return json.loads(group.thaw_receipt_json)
    batches = session.exec(select(MigrationBatch).where(MigrationBatch.group_id == group_id).order_by(MigrationBatch.id)).all()
    bindings = session.exec(select(TaskBinding).where(TaskBinding.root_group_id == group_id).order_by(TaskBinding.task_id)).all()
    members = session.exec(select(MigrationMember).where(MigrationMember.batch_id.in_([batch.id for batch in batches]))).all()
    if {binding.task_id for binding in bindings} - {member.task_id for member in members}:
        raise OperationConflict('unregistered outside dependency prevents thaw')
    for binding in bindings:
        binding.state = 'withdrawn'
        session.add(binding)
    for member in members:
        member.state = 'withdrawn'
        session.add(member)
    for batch in batches:
        batch.state = 'withdrawn'
        session.add(batch)
    edges = session.exec(select(MigrationDependency).where(MigrationDependency.group_id == group_id)).all()
    for edge in edges:
        edge.active = False
        session.add(edge)
    sources = session.exec(select(MigrationSource).where(MigrationSource.group_id == group_id).order_by(MigrationSource.id)).all()
    receipt: dict[str, JsonValue] = {'version': 1, 'group_id': group_id, 'category': rollback_category(session, group_id),
        'batches': [batch.id for batch in batches], 'members': [{'task_id': member.task_id, 'generation': member.generation} for member in members],
        'sources': [{'id': source.id, 'roots': json.loads(source.roots_json)} for source in sources],
        'withdrawn_references': [edge.id for edge in edges]}
    group.state, group.thaw_receipt_json = 'withdrawing', canonical(receipt)
    session.add(group)
    return receipt
