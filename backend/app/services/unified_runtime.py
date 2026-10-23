from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import event, inspect, text
from sqlmodel import SQLModel, create_engine

from app.arctime.unified_host import NativeHost
from app.db import _register_sqlite_functions
from app.db_migrations import upgrade_database
from app.services.source_seal import Supervisor
from app.services.task_operations import OperationConflict
from app.services.unified_database import UNIFIED_SCHEMA_VERSION
from app.services.unified_files import checked_path, immutable_bytes


class RuntimeManifest(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    version: int = Field(default=1, ge=1, le=1)
    schema_version: str = UNIFIED_SCHEMA_VERSION
    data: Path
    credential_root: Path
    model: Path
    threads: int = Field(default=4, ge=1, le=64)
    recovery_bundle: Path | None = None
    recovery_bundle_sha256: str | None = None


def initialize(data: Path, credential_root: Path, model: Path, *, threads: int = 4) -> Path:
    data, credential_root, model = data.absolute(), credential_root.absolute(), model.absolute()
    if data.is_relative_to(credential_root) or credential_root.is_relative_to(data):
        raise OperationConflict('new runtime and existing credential domains must be independent')
    checked_path(data, '.probe')
    data.mkdir(parents=True, exist_ok=False, mode=0o700)
    for role in ('db', 'tasks', 'settings', 'guard', 'registry', 'packages'):
        (data / role).mkdir(mode=0o700)
    immutable_bytes(data / 'tasks/.gui.lock', b'')
    immutable_bytes(data / 'guard/.heavy.lock', b'')
    manifest = RuntimeManifest(data=data, credential_root=credential_root, model=model, threads=threads)
    path = data / 'runtime.json'
    upgrade_database(f'sqlite:///{data / "db/unified.sqlite3"}', tasks_root=data / 'tasks')
    engine = create_engine(f'sqlite:///{data / "db/unified.sqlite3"}')
    try:
        SQLModel.metadata.create_all(engine)
    finally:
        engine.dispose()
    immutable_bytes(path, manifest.model_dump_json().encode())
    return path


def open_runtime(manifest_path: Path, *, supervisor: Supervisor | None = None) -> NativeHost:
    checked_path(manifest_path.absolute().parent, manifest_path.name)
    manifest = RuntimeManifest.model_validate_json(manifest_path.read_bytes())
    if manifest.schema_version != UNIFIED_SCHEMA_VERSION or manifest.data != manifest_path.absolute().parent:
        raise OperationConflict('runtime manifest schema/location mismatch; use verified recovery or relocation')
    database = checked_path(manifest.data, 'db/unified.sqlite3')
    if not database.is_file():
        raise OperationConflict('registered unified database is missing; refusing automatic recreation')
    engine = create_engine(f'sqlite:///{database}', connect_args={'check_same_thread': False})
    event.listen(engine, 'connect', _register_sqlite_functions)
    if not set(SQLModel.metadata.tables).issubset(inspect(engine).get_table_names()):
        raise OperationConflict('registered runtime tables missing; refusing automatic schema repair')
    with engine.connect() as connection:
        versions = connection.execute(text('SELECT version_num FROM alembic_version')).scalars().all()
        if versions != [UNIFIED_SCHEMA_VERSION] or connection.execute(text('PRAGMA integrity_check')).scalar_one() != 'ok':
            raise OperationConflict('unsupported or corrupt unified database; preserve for independent recovery')
    return NativeHost(engine, task_root=manifest.data / 'tasks', settings_root=manifest.data / 'settings',
        guard_root=manifest.data / 'guard', credential_root=manifest.credential_root,
        model=manifest.model, threads=manifest.threads, supervisor=supervisor)
