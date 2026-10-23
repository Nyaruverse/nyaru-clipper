from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from sqlmodel import Session

from app.models_migration import MigrationGroup
from app.services.migration_groups import record_new_write
from app.services.source_seal import Supervisor
from app.services.task_migration import Migrator
from app.services.task_operations import runtime
from app.services.unified_files import file_sha256
from test_unified_migration import source_fixture
from test_unified_operations import database


@pytest.mark.skipif(sys.platform != 'darwin', reason='Real immutable protection and restoration')
@pytest.mark.parametrize(('category', 'sealed_snapshot', 'partial_restore'),
    [(category, sealed, False) for category in ('R0', 'R1', 'R2') for sealed in (False, True)] + [('R1', True, True)])
def test_frozen_entry_can_thaw_without_candidate_but_never_thaws_r2(tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch, category: str, sealed_snapshot: bool, partial_restore: bool) -> None:
    source_id, old, roots, context, document, metadata = source_fixture(tmp_path, monkeypatch)
    (tmp_path / 'db').mkdir()
    engine = database(tmp_path / 'db')
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2] / 'scripts'))
    from build_unified_recovery import freeze
    bundle = freeze(tmp_path / 'reader', legacy_helper=True)
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
    try:
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
        if sealed_snapshot:
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
        program = "import runpy,sys\ndef guard(event,args):\n    if event == 'import' and (args[0] == 'app' or args[0].startswith('app.') or args[0] in ('torch','whisperx')): raise RuntimeError('candidate import prohibited')\n    if event in ('socket.connect','subprocess.Popen'): raise RuntimeError('network or child prohibited')\nsys.addaudithook(guard)\nsys.argv=sys.argv[1:]\nrunpy.run_path(sys.argv[0],run_name='__main__')\n"
        if partial_restore:
            failing = program.replace('sys.addaudithook(guard)',
                f"def fail_restore(event,args):\n    if event == 'os.chflags' and str(args[0]) == {str(context.source.root / 'subtitles.srt')!r} and args[1] == 0:\n        open({str(tmp_path / 'injected-restoration-failure')!r}, 'w').write('reached')\n        raise PermissionError('injected partial old-root restoration')\nsys.addaudithook(fail_restore)\nsys.addaudithook(guard)")
            failed = subprocess.run([str(bundle.parent / 'runtime/bin/python3.11'), '-I', '-S', '-B', '-c', failing,
                str(bundle.parent / 'reader.py'), '--mode', 'thaw', '--manifest', str(recipe), '--bundle', str(bundle),
                '--output-root', str(tmp_path / 'failed-receipt')], capture_output=True, text=True, timeout=60)
            assert failed.returncode == 2, failed.stderr
            assert (tmp_path / 'injected-restoration-failure').read_text() == 'reached'
            import sqlite3
            import stat
            with sqlite3.connect(database_path.as_uri() + '?mode=ro&immutable=1', uri=True) as connection:
                assert connection.execute('SELECT state,new_writes FROM migrationgroup WHERE id=?', (group,)).fetchone() == ('withdrawing', 0)
                assert connection.execute("SELECT 1 FROM taskbinding WHERE state='activated'").fetchone() is None
            assert database_path.stat().st_flags & stat.UF_IMMUTABLE
            controls = tmp_path / 'failed-receipt/controls-resealed.json'
            assert controls.is_file()
            frozen = snapshot(snapshot_recipe, tmp_path / 'snapshot-resume', install_seal=False)
            value['sealed_snapshot'] = {'path': str(frozen), 'sha256': file_sha256(frozen)}
            value['controls_protection'] = {'path': str(controls), 'sha256': file_sha256(controls)}
            recipe.write_text(json.dumps(value))
        result = subprocess.run([str(bundle.parent / 'runtime/bin/python3.11'), '-I', '-S', '-B', '-c', program,
            str(bundle.parent / 'reader.py'), '--mode', 'thaw', '--manifest', str(recipe), '--bundle', str(bundle),
            '--output-root', str(tmp_path / 'receipt')], capture_output=True, text=True, timeout=60)
        if category == 'R2':
            assert result.returncode == 2, result.stderr + result.stdout
            assert 'R2' in result.stderr
            assert not (guard / 'thaw-allowed.json').exists()
            with pytest.raises(PermissionError):
                (old / 'forbidden').write_text('blocked')
        else:
            assert result.returncode == 0, result.stderr + result.stdout
            receipt_path = Path(json.loads(result.stdout)['receipt'])
            assert receipt_path.is_relative_to(tmp_path / 'receipt')
            receipt = json.loads(receipt_path.read_bytes())
            assert receipt['category'] == category and receipt['batches'] == [batch]
            assert {str(path): (path.stat().st_mode & 0o777, path.stat().st_flags) for path in [old, *old.rglob('*')]} == original_modes
            import sqlite3
            with sqlite3.connect(database_path.as_uri() + '?mode=ro&immutable=1', uri=True) as connection:
                assert connection.execute('SELECT state FROM migrationgroup WHERE id=?', (group,)).fetchone() == ('thawed',)
            if sealed_snapshot:
                import stat
                assert database_path.stat().st_flags & stat.UF_IMMUTABLE
                assert (tmp_path / 'receipt/controls-resealed.json').is_file()
    finally:
        for path in [tmp_path, *tmp_path.rglob('*')]:
            os.chflags(path, 0)
            path.chmod(0o700 if path.is_dir() else 0o600)
