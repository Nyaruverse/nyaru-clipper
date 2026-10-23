from __future__ import annotations

from sqlalchemy import Engine
from sqlmodel import Session, select

from app.models_migration import MigrationDependency, MigrationGroup
from app.models_unified import TaskBinding
from app.services.migration_groups import withdraw_group
from app.services.migration_ownership import verify_ownership
from app.services.source_seal import SealRecord, Supervisor
from app.services.task_operations import OperationConflict, canonical, digest
from app.services.unified_database import begin_unified_mutation


def thaw(engine: Engine, group_id: str, supervisor: Supervisor) -> None:
    sealed = supervisor.guard_root / 'sealed.json'
    seal = SealRecord.model_validate_json(sealed.read_bytes())
    if seal.root_group_id != group_id or supervisor.root_group_id != group_id:
        raise OperationConflict('thaw Supervisor group mismatch')
    with Session(engine) as session:
        group = session.get(MigrationGroup, group_id)
        has_ownership = bool(group and group.ownership_json != '{}')
    if has_ownership:
        verify_ownership(engine, supervisor, thaw_resume=(supervisor.guard_root / 'thaw-allowed.json').exists())
    if not (supervisor.guard_root / 'thaw-allowed.json').exists():
        supervisor.verify()
    with Session(engine) as session:
        begin_unified_mutation(session)
        receipt = withdraw_group(session, group_id)
        receipt.update(permission_profile=seal.profile, seal_sha256=digest(sealed.read_bytes()))
        group = session.get(MigrationGroup, group_id)
        group.thaw_receipt_json = canonical(receipt)
        session.add(group)
        session.commit()

    def committed(identifier: str) -> bool:
        with Session(engine) as session:
            group = session.get(MigrationGroup, identifier)
            edges = session.exec(select(MigrationDependency).where(MigrationDependency.group_id == identifier,
                MigrationDependency.active == True)).all()
            bindings = session.exec(select(TaskBinding).where(TaskBinding.root_group_id == identifier,
                TaskBinding.state == 'activated')).all()
            return bool(group and group.state == 'withdrawing' and not group.new_writes and not edges and not bindings
                and group.thaw_receipt_json == canonical(receipt))

    supervisor.thaw(dependencies_released=committed, receipt=receipt)
    with Session(engine) as session:
        begin_unified_mutation(session)
        group = session.get(MigrationGroup, group_id)
        if group is None or not committed(group_id):
            raise OperationConflict('thaw database proof changed')
        group.state = 'thawed'
        session.add(group)
        session.commit()
