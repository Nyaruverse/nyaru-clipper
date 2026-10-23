from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, ValidationError
from sqlalchemy import text
from sqlmodel import Session

from app.services.workstation_queue import begin_queue_mutation

UNIFIED_SCHEMA_VERSION = '20261022_01'


class DatabaseSafetyError(ValueError):
    pass


class SqliteDurability(BaseModel):
    model_config = ConfigDict(frozen=True, extra='forbid')
    journal_mode: Literal['delete', 'truncate', 'persist', 'wal']
    synchronous: Literal[2, 3]


def begin_unified_mutation(session: Session) -> SqliteDurability:
    if session.get_bind().dialect.name != 'sqlite':
        raise DatabaseSafetyError('Unified persistence requires SQLite')
    begin_queue_mutation(session)
    versioned = session.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='alembic_version'")).first()
    if versioned is not None:
        versions = session.execute(text('SELECT version_num FROM alembic_version')).scalars().all()
        if versions != [UNIFIED_SCHEMA_VERSION]:
            raise DatabaseSafetyError('Unsupported unified SQLite schema; preserve this database for recovery')
    try:
        return SqliteDurability(journal_mode=session.execute(text('PRAGMA journal_mode')).scalar_one(),
            synchronous=session.execute(text('PRAGMA synchronous')).scalar_one())
    except ValidationError:
        raise DatabaseSafetyError('SQLite requires a durable journal and FULL/EXTRA synchronous writes') from None
