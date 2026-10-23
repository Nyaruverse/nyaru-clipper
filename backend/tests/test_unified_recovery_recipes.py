from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from app.arctime.migration_cli import GuardRecipe
from app.services.recovery_recipes import export_recipes
from app.services.source_seal import Supervisor
from app.services.task_migration import Migrator
from app.services.unified_files import file_sha256
from app.services.unified_runtime import RuntimeManifest, initialize, open_runtime
from test_unified_migration import source_fixture


@pytest.mark.skipif(sys.platform != 'darwin', reason='Actual multi-root immutable protection')
def test_exported_operator_recipes_support_a_sealed_snapshot_and_independent_thaw(tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch) -> None:
    source, old, roots, context, document, metadata = source_fixture(tmp_path, monkeypatch)
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2] / 'scripts'))
    from build_unified_recovery import freeze
    from recovery_storage import snapshot
    bundle = freeze(tmp_path / 'reader', legacy_helper=True)
    credentials = tmp_path / 'private'
    credentials.mkdir()
    manifest_path = initialize(tmp_path / 'candidate', credentials, tmp_path / 'model.bin')
    host = open_runtime(manifest_path)
    manifest = RuntimeManifest.model_validate_json(manifest_path.read_bytes()).model_copy(update={
        'recovery_bundle': bundle, 'recovery_bundle_sha256': file_sha256(bundle)})
    migration = Migrator(host.engine, host.root, host.settings_root, recovery_bundle=bundle,
        recovery_bundle_sha256=file_sha256(bundle))
    group = migration.register(source, roots, origin='companion')
    batch = migration.prepare(source, context, document, metadata=metadata)
    migration.verify(batch)
    guard = GuardRecipe(group_id=group, domains=(old,), locks=(old / '.gui.lock', context.source.root / '.lock'),
        guard_root=host.guard_root / 'source-epoch')
    guard_path = tmp_path / 'guard.json'
    guard_path.write_text(guard.model_dump_json())
    try:
        with Supervisor(guard.domains, guard.guard_root, credentials, group, guard.locks) as supervisor:
            supervisor.seal()
            migration.activate(batch, supervisor)
            export_recipes(host, manifest, guard_path, tmp_path / 'recipes')
        host.engine.dispose()
        recipe = json.loads((tmp_path / 'recipes/snapshot.json').read_bytes())
        assert len(recipe['roots']) == 6 and len(recipe['locks']) == 3
        frozen = snapshot(recipe, tmp_path / 'snapshot', install_seal=True)
        thaw = json.loads((tmp_path / 'recipes/thaw.json').read_bytes())
        thaw['sealed_snapshot'] = {'path': str(frozen), 'sha256': file_sha256(frozen)}
        thaw_path = tmp_path / 'thaw-sealed.json'
        thaw_path.write_text(json.dumps(thaw))
        result = subprocess.run([str(bundle.parent / 'runtime/bin/python3.11'), '-I', '-S', '-B',
            str(bundle.parent / 'reader.py'), '--mode', 'thaw', '--manifest', str(thaw_path), '--bundle', str(bundle),
            '--output-root', str(tmp_path / 'receipt')], capture_output=True, text=True, timeout=60)
        assert result.returncode == 0, result.stderr + result.stdout
        assert (guard.guard_root / 'thawed.json').is_file()
        assert (tmp_path / 'receipt/controls-resealed.json').is_file()
    finally:
        for path in [tmp_path, *tmp_path.rglob('*')]:
            os.chflags(path, 0)
            path.chmod(0o700 if path.is_dir() else 0o600)
