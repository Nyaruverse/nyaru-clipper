from __future__ import annotations

import os
import sys
from pathlib import Path
from uuid import uuid4

import pytest
from sqlmodel import Session, select

from app.models_migration import MigrationBatch, MigrationGroup
from app.models_unified import DocumentHead, GlobalHead, TaskBinding
from app.services.source_seal import Supervisor
from app.services.migration_snapshot import Candidate
from app.services.task_migration import Migrator
from app.services.task_operations import OperationConflict
from app.services.unified_files import file_sha256
from test_unified_migration import source_fixture
from test_unified_operations import database


@pytest.mark.skipif(sys.platform != 'darwin', reason='Actual immutable protection')
@pytest.mark.parametrize('failure', ['generation', 'transaction', 'wrong-group'])
def test_failed_activation_never_exposes_partial_heads_or_releases_old_source(tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch, failure: str) -> None:
    source_id, old, roots, context, document, metadata = source_fixture(tmp_path, monkeypatch)
    engine = database(tmp_path)
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2] / 'scripts'))
    from build_unified_recovery import freeze
    bundle = freeze(tmp_path / 'reader', legacy_helper=True)
    migration = Migrator(engine, tmp_path / 'tasks', tmp_path / 'settings',
        recovery_bundle=bundle, recovery_bundle_sha256=file_sha256(bundle))
    group = migration.register(source_id, roots, origin='companion')
    batch = migration.prepare(source_id, context, document, metadata=metadata)
    migration.verify(batch)
    if failure == 'generation':
        (roots.settings / 'after-verify.txt').write_text('changed before takeover')
    if failure == 'transaction':
        from app.services import migration_activation
        original = migration_activation.activate_candidate
        def fail_after_heads(session: Session, root: Path, candidate: Candidate, batch: MigrationBatch) -> None:
            original(session, root, candidate, batch)
            raise OperationConflict('injected after document and metadata heads')
        monkeypatch.setattr(migration_activation, 'activate_candidate', fail_after_heads)
    credentials = tmp_path / 'private'
    credentials.mkdir()
    try:
        with Supervisor((old,), tmp_path / 'guard', credentials, str(uuid4()) if failure == 'wrong-group' else group,
                (old / '.gui.lock', context.source.root / '.lock')) as supervisor:
            supervisor.seal()
            with pytest.raises(OperationConflict):
                migration.activate(batch, supervisor)
            assert supervisor.verify().entries
            with pytest.raises(PermissionError):
                (context.source.root / 'subtitles.srt').write_text('forbidden')
            with Session(engine) as session:
                assert session.get(MigrationBatch, batch).state == 'verified'
                assert session.get(MigrationGroup, group).ownership_json == '{}'
                assert session.get(TaskBinding, context.source.task_id).state == 'prepared'
                assert session.exec(select(DocumentHead)).first() is None
                assert session.exec(select(GlobalHead)).first() is None
    finally:
        for path in [old, *old.rglob('*')]:
            os.chflags(path, 0)
            path.chmod(0o700 if path.is_dir() else 0o600)
