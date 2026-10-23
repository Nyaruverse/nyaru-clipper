from __future__ import annotations

import inspect
import json
import os
import select as io_select
import signal
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest
from sqlmodel import Session, create_engine, select

from app.arctime.subtitle_document import save_document
from app.services.task_artifacts import ArtifactFile, resolve_workstation
from app.models import WorkstationEvent
from app.models_migration import MigrationBatch
from app.models_unified import DocumentHead, DocumentVersion, GlobalHead, TaskBinding
from app.services.source_seal import GuardError, Supervisor
from app.services.task_migration import Migrator
from app.services.task_operations import OperationConflict, claim_operation, runtime
from app.services.unified_files import file_sha256
from test_unified_migration import source_fixture
from test_unified_operations import database


BOUNDARIES = {
    'before-lock': (Supervisor.__enter__, 'control ='),
    'before-seal': (Supervisor.seal, 'if len(self.descriptors)'),
    'before-sealed-record': (Supervisor.seal, 'immutable_bytes(checked_path(self.guard_root, "sealed.json")'),
    'after-seal': (Migrator.activate, 'if self.recovery_bundle is None'),
    'before-transaction': (Migrator.activate, 'begin_unified_mutation(session)'),
    'after-generation-recheck': (Migrator.activate, 'from app.services.migration_globals import activate_package'),
    'before-commit': (Migrator.activate, 'session.commit()'),
    'after-commit-before-worker': (Migrator.activate, None),
}


def crash_child(root: Path, boundary: str) -> None:
    spec = json.loads((root / 'child.json').read_text())
    engine = create_engine(f'sqlite:///{root / "state.sqlite3"}')
    migrator = Migrator(engine, root / 'new-tasks', root / 'new-settings',
        recovery_bundle=Path(spec['bundle']), recovery_bundle_sha256=spec['bundle_sha256'])
    supervisor = Supervisor((root / 'old',), root / 'guard', root / 'credentials', spec['group'],
        tuple(Path(path) for path in spec['locks']))
    function, snippet = BOUNDARIES[boundary]
    lines, start = inspect.getsourcelines(function)
    target = start + next(i for i, line in enumerate(lines) if snippet in line) if snippet else None

    def trace(frame, event, arg):
        if frame.f_code is function.__code__ and ((event == 'line' and frame.f_lineno == target)
                or (snippet is None and event == 'return')):
            print(json.dumps({'boundary': boundary, 'pid': os.getpid(), 'line': frame.f_lineno,
                'held_inodes': [os.fstat(fd).st_ino for fd in supervisor.descriptors]}), flush=True)
            sys.stdin.readline()
        return trace

    sys.settrace(trace)
    with supervisor:
        supervisor.seal()
        migrator.activate(spec['batch'], supervisor)
    raise AssertionError('parent failed to kill child at boundary')


@pytest.fixture
def takeover(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv('APP_EXECUTION_GUARD_ROOT', str(tmp_path / 'execution-guard'))
    source_id, old, roots, context, document, metadata = source_fixture(tmp_path, monkeypatch)
    video = context.source.root / 'source.mp4'
    subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'color=c=black:s=1280x720:r=30',
        '-t', '5', '-c:v', 'libx264', '-preset', 'ultrafast', '-y', str(video)], check=True, timeout=30)
    context = resolve_workstation(context.source.model_copy(update={'video': ArtifactFile(path='source.mp4', sha256=file_sha256(video))}))
    document = document.model_copy(update={'revision': 0, 'source_fingerprint': context.source.fingerprint})
    document = save_document(context.source.root, document, base=context.document(document.style), artifacts=context)
    with sqlite3.connect(old / 'legacy.sqlite3') as connection:
        connection.execute('CREATE TABLE probe (value TEXT)')
    engine = database(tmp_path)
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2] / 'scripts'))
    from build_unified_recovery import freeze
    bundle = freeze(tmp_path / 'reader', legacy_helper=True)
    migration = Migrator(engine, tmp_path / 'new-tasks', tmp_path / 'new-settings',
        recovery_bundle=bundle, recovery_bundle_sha256=file_sha256(bundle))
    group = migration.register(source_id, roots, origin='companion')
    batch = migration.prepare(source_id, context, document, metadata=metadata)
    migration.verify(batch)
    (tmp_path / 'credentials').mkdir()
    locks = (old / '.gui.lock', context.source.root / '.lock')
    spec = {'bundle': str(bundle), 'group': group, 'batch': batch, 'bundle_sha256': file_sha256(bundle), 'locks': list(map(str, locks))}
    (tmp_path / 'child.json').write_text(json.dumps(spec))
    try:
        yield migration, spec, (source_id, old, roots, context, document, metadata)
    finally:
        for path in [old, *old.rglob('*')]:
            os.chflags(path, 0)
            path.chmod(0o700 if path.is_dir() else 0o600)
        engine.dispose()


def snapshot(root: Path):
    return {str(path.relative_to(root)): {'inode': path.stat().st_ino, 'sha256': file_sha256(path)}
        for path in sorted(root.rglob('*')) if path.is_file()}


def old_write_probes(old: Path):
    code = '''
import json, sqlite3, sys
from pathlib import Path
from app.arctime.subtitle_document import save_document, SubtitleDocument
from app.arctime import workflow, cli
from app.arctime.gui import create_app
from fastapi.testclient import TestClient
old = Path(sys.argv[1])
receipts = []
for name in ('gui-start', 'gui-save', 'cli-resume', 'cli-lock', 'sqlite-write'):
    try:
        if name == 'gui-start':
            with TestClient(create_app(old, credential_root=old.parent / 'probe-credentials')):
                raise AssertionError('sealed GUI started')
        elif name == 'cli-resume':
            assert cli.main(['resume', str(old / 'tasks/abcdef123456')]) == 1
            receipts.append({'entry': name, 'denied': True, 'observable': 'exit 1; stderr captured'})
            continue
        elif name == 'gui-save':
            document = SubtitleDocument.model_validate_json(Path(sys.argv[2]).read_bytes())
            save_document(old / 'tasks/abcdef123456', document)
        elif name == 'cli-lock':
            with workflow.exclusive_lock(old / 'tasks/abcdef123456/.lock'):
                (old / 'tasks/abcdef123456/subtitles.srt').write_text('forbidden')
        else:
            with sqlite3.connect(old / 'legacy.sqlite3') as connection:
                connection.execute("INSERT INTO probe VALUES ('forbidden')")
        receipts.append({'entry': name, 'denied': False})
    except (PermissionError, sqlite3.OperationalError) as error:
        receipts.append({'entry': name, 'denied': True, 'error': str(error), 'type': type(error).__name__})
print(json.dumps(receipts))
'''
    result = subprocess.run([sys.executable, '-c', code, str(old), str(old.parent / 'document.json')],
        capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stderr
    (old.parent / 'old-entry.stderr').write_text(result.stderr)
    receipts = json.loads(result.stdout)
    assert all(item['denied'] for item in receipts), receipts
    return receipts


@pytest.mark.skipif(sys.platform != 'darwin', reason='Requires actual macOS immutable protection')
@pytest.mark.parametrize('boundary', BOUNDARIES)
def test_sigkill_takeover_boundary(takeover, tmp_path: Path, boundary: str) -> None:
    migration, spec, (_, old, _, context, document, _) = takeover
    (tmp_path / 'document.json').write_text(document.model_dump_json())
    before = snapshot(old)
    locks = tuple(Path(path) for path in spec['locks'])
    with (tmp_path / 'child.stderr').open('w') as stderr:
        child = subprocess.Popen([sys.executable, __file__, '--child', str(tmp_path), boundary],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=stderr, text=True)
        try:
            assert io_select.select([child.stdout], [], [], 45)[0], 'child did not reach boundary'
            receipt = json.loads(child.stdout.readline())
            child.send_signal(signal.SIGKILL)
            assert child.wait(timeout=10) == -signal.SIGKILL
        finally:
            if child.poll() is None:
                child.kill()
                child.wait(timeout=10)
    sealed = (tmp_path / 'guard/sealed.json').exists()
    activated = boundary == 'after-commit-before-worker'
    with Session(migration.engine) as session:
        assert session.get(MigrationBatch, spec['batch']).state == ('activated' if activated else 'verified')
        assert session.get(TaskBinding, context.source.task_id).state == ('activated' if activated else 'prepared')
        assert len(session.exec(select(DocumentHead)).all()) == int(activated)
        heads = session.exec(select(GlobalHead)).all()
        assert len(heads) == (8 if activated else 0)
        receipt['global_heads_at_crash'] = [head.model_dump(mode='json') for head in heads]
        assert runtime(session).paused and claim_operation(session) is None
    receipt.update({'returncode': child.returncode, 'sealed': sealed, 'activated': activated, 'queue_paused': True})
    if sealed or boundary == 'before-sealed-record':
        receipt['old_write_probes'] = old_write_probes(old)
    assert snapshot(old) == before
    with Supervisor((old,), tmp_path / 'guard', tmp_path / 'credentials', spec['group'], locks) as supervisor:
        receipt['reacquired_inodes'] = [os.fstat(fd).st_ino for fd in supervisor.descriptors[1:]]
        assert receipt['reacquired_inodes'] == [path.stat().st_ino for path in sorted(locks)]
        if not sealed:
            with pytest.raises(FileNotFoundError):
                migration.activate(spec['batch'], supervisor)
        supervisor.seal()
        migration.activate(spec['batch'], supervisor)
        migration.activate(spec['batch'], supervisor)
    with Session(migration.engine) as session:
        assert len(session.exec(select(DocumentVersion)).all()) == 1
        assert len(session.exec(select(WorkstationEvent).where(WorkstationEvent.event_type == 'task.created')).all()) == 1
        assert runtime(session).paused and claim_operation(session) is None
    assert snapshot(old) == before
    receipt.update({'source_files': before, 'recovered_activation_count': 1, 'worker_started': False})
    (tmp_path / 'receipt.json').write_text(json.dumps(receipt, indent=2))


@pytest.mark.skipif(sys.platform != 'darwin', reason='Requires actual macOS immutable protection')
def test_changed_draft_requires_fresh_generation_then_single_activation(takeover, tmp_path: Path) -> None:
    migration, spec, (source_id, old, roots, context, document, metadata) = takeover
    initial = document.model_copy(update={'cues': [document.cues[0].model_copy(update={'text': 'verified后旧入口的新编辑'})]})
    updated = save_document(context.source.root, initial, base=context.document(initial.style), artifacts=context)
    assert updated.revision == document.revision + 1 == 2
    document = updated
    locks = tuple(Path(path) for path in spec['locks'])
    with Supervisor((old,), tmp_path / 'guard', tmp_path / 'credentials', spec['group'], locks) as supervisor:
        supervisor.seal()
        with pytest.raises(OperationConflict, match='generation') as rejected:
            migration.activate(spec['batch'], supervisor)
        fresh = migration.prepare(source_id, context, document, metadata=metadata)
        assert fresh != spec['batch']
        migration.verify(fresh)
        migration.activate(fresh, supervisor)
        migration.activate(fresh, supervisor)
    with Session(migration.engine) as session:
        assert len(session.exec(select(DocumentVersion)).all()) == 1
        assert runtime(session).paused and claim_operation(session) is None
        head = session.get(DocumentHead, context.source.task_id)
        migrated = json.loads((migration.root / head.body_path).read_text())
        assert migrated['revision'] == 2 and migrated['cues'][0]['text'] == updated.cues[0].text
    (tmp_path / 'receipt.json').write_text(json.dumps({'rejection': str(rejected.value),
        'saved_revision': updated.revision, 'saved_document_sha256': file_sha256(context.source.root / 'subtitle-document.json'),
        'stale_batch': spec['batch'], 'fresh_batch': fresh, 'activation_count': 1, 'queue_paused': True,
        'source_files': snapshot(old)}, indent=2))


@pytest.mark.skipif(sys.platform != 'darwin', reason='Requires actual macOS immutable protection')
def test_replaced_original_lock_inode_is_rejected(takeover, tmp_path: Path) -> None:
    import stat
    _, spec, (_, old, _, _, _, _) = takeover
    locks = tuple(Path(path) for path in spec['locks'])
    with Supervisor((old,), tmp_path / 'guard', tmp_path / 'credentials', spec['group'], locks) as supervisor:
        supervisor.seal()
        lock = old / '.gui.lock'
        original = lock.stat().st_ino
        sealed_mode = stat.S_IMODE(old.stat().st_mode)
        os.chflags(old, 0)
        old.chmod(0o700)
        os.chflags(lock, 0)
        lock.rename(tmp_path / 'original-lock')
        lock.touch(mode=0o400)
        os.chflags(lock, stat.UF_IMMUTABLE)
        old.chmod(sealed_mode)
        os.chflags(old, stat.UF_IMMUTABLE)
        replacement = lock.stat().st_ino
        assert original != replacement
        with pytest.raises(GuardError, match='inode') as rejected:
            supervisor.verify()
    with pytest.raises(GuardError, match='inode'):
        with Supervisor((old,), tmp_path / 'guard', tmp_path / 'credentials', spec['group'], locks):
            raise AssertionError('replaced lock was accepted')
    (tmp_path / 'receipt.json').write_text(json.dumps({'original_inode': original,
        'replacement_inode': replacement, 'rejection': str(rejected.value)}, indent=2))


if __name__ == '__main__':
    assert sys.argv[1] == '--child'
    crash_child(Path(sys.argv[2]), sys.argv[3])
