from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict
from sqlalchemy import Engine
from sqlmodel import Session, select

from app.models_migration import MigrationGroup, MigrationSource
from app.services.migration_snapshot import SourceRoots
from app.services.recovery_bundle import verify_bundle
from app.services.source_seal import Supervisor
from app.services.task_operations import OperationConflict
from app.services.unified_files import file_sha256


class Ownership(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    sealed_record: Path
    sealed_sha256: str
    recovery_bundle: Path
    recovery_bundle_sha256: str


def verify_ownership(engine: Engine, supervisor: Supervisor, *, thaw_resume: bool = False) -> Ownership:
    with Session(engine) as session:
        group = session.get(MigrationGroup, supervisor.root_group_id)
        if group is None or group.ownership_json == '{}' or group.state not in ({'withdrawing'} if thaw_resume else {'open'}):
            raise OperationConflict('registered migration ownership is missing or no longer active')
        ownership = Ownership.model_validate_json(group.ownership_json)
        if (ownership.sealed_record != (supervisor.guard_root / 'sealed.json').absolute()
                or file_sha256(ownership.sealed_record) != ownership.sealed_sha256):
            raise OperationConflict('Supervisor guard identity differs from committed migration ownership')
        sources = session.exec(select(MigrationSource).where(MigrationSource.group_id == group.id)).all()
        if any(not any(root.is_relative_to(domain) for domain in supervisor.sources)
                for source in sources for root in SourceRoots.model_validate_json(source.roots_json).roots):
            raise OperationConflict('Supervisor does not cover all registered root-group domains')
    verify_bundle(ownership.recovery_bundle, ownership.recovery_bundle_sha256)
    if not thaw_resume:
        supervisor.verify()
    return ownership
