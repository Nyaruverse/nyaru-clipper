from __future__ import annotations

import json
from pathlib import Path

import pytest
from sqlmodel import Session

from app.services.migration_groups import record_new_write
from app.services.source_seal import Supervisor
from app.services.task_migration import Migrator
from app.services.task_operations import runtime
from app.services.unified_files import file_sha256
from test_unified_migration import source_fixture
from test_unified_operations import database


from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CrashCase:
    root: Path
    old: Path
    guard: Path
    database: Path
    group: str
    bundle: Path
    recipe: Path
    locks: tuple[Path, ...]


def prepare_case(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, frozen_reader: Path, *, category: str = "R1") -> CrashCase:
    source_id, old, roots, context, document, metadata = source_fixture(tmp_path, monkeypatch)
    (tmp_path / 'db').mkdir()
    engine = database(tmp_path / 'db')
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2] / 'scripts'))
    bundle = frozen_reader
    credentials, host_guard = tmp_path / 'private', tmp_path / 'host-guard'
    credentials.mkdir()
    host_guard.mkdir()
    (host_guard / '.heavy.lock').touch()
    database_path = Path(engine.url.database)
    with engine.begin() as connection:
        from sqlalchemy import text
        connection.execute(text('CREATE TABLE alembic_version (version_num TEXT NOT NULL)'))
        connection.execute(text("INSERT INTO alembic_version VALUES ('20261022_01')"))
    with Session(engine) as session:
        state = runtime(session)
        state.root_roles_json = json.dumps({'task': str(tmp_path / 'new-tasks'), 'settings': str(tmp_path / 'new-settings'),
            'guard': str(host_guard), 'credential': str(credentials)})
        session.add(state)
        session.commit()
    migration = Migrator(engine, tmp_path / 'new-tasks', tmp_path / 'new-settings',
        recovery_bundle=bundle, recovery_bundle_sha256=file_sha256(bundle))
    group = migration.register(source_id, roots, origin='companion')
    batch = migration.prepare(source_id, context, document, metadata=metadata)
    migration.verify(batch)
    guard = host_guard / 'source-epoch'
    locks = (old / '.gui.lock', context.source.root / '.lock')
    original_modes = {str(path): (path.stat().st_mode & 0o777, path.stat().st_flags) for path in [old, *old.rglob('*')]}
    with Supervisor((old,), guard, credentials, group, locks) as supervisor:
        supervisor.seal()
        if category != 'R0':
            migration.activate(batch, supervisor)
        if category == 'R2':
            with Session(engine) as session:
                record_new_write(session)
                session.commit()
    recipe = tmp_path / 'thaw.json'
    value = {'version': 1, 'database': str(database_path), 'credential_root': str(credentials),
        'bundle_sha256': file_sha256(bundle), 'guard': {'group_id': group, 'guard_root': str(guard),
            'domains': [str(old)], 'locks': list(map(str, locks))}}
    from recovery_storage import snapshot
    roles = {'unified_db': database_path.parent, 'task_root': migration.root, 'settings_root': migration.settings_root,
        'guard_root': host_guard, 'global_package_root': tmp_path / 'packages', 'migration_registry': tmp_path / 'registry'}
    for path in roles.values():
        path.mkdir(exist_ok=True)
    engine.dispose()
    snapshot_recipe = {'version': 1, 'root_group_id': group, 'roots': {name: str(path) for name, path in roles.items()},
        'credential_root': str(credentials), 'locks': [str(host_guard / '.heavy.lock')], 'database': database_path.name,
        'reader_bundle': {'path': str(bundle), 'sha256': file_sha256(bundle)}}
    frozen = snapshot(snapshot_recipe, tmp_path / 'snapshot', install_seal=True)
    value['sealed_snapshot'] = {'path': str(frozen), 'sha256': file_sha256(frozen)}
    recipe.write_text(json.dumps(value))
    (tmp_path / 'snapshot-recipe.json').write_text(json.dumps(snapshot_recipe))
    (tmp_path / 'original-modes.json').write_text(json.dumps(original_modes))
    return CrashCase(tmp_path, old, guard, database_path, group, bundle, recipe, locks)
