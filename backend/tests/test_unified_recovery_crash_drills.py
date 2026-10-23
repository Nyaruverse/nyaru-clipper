from __future__ import annotations

import fcntl
import json
import os
import sqlite3
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from app.services.unified_files import file_sha256

from unified_crash_fixture import prepare_case
from unified_crash_harness import BOUNDARIES, command, kill_at, observe


@pytest.fixture(scope='module')
def evidence_root() -> Path:
    root = Path(tempfile.mkdtemp(prefix='m24-sigkill-', dir=Path.home() / '.cache/nyaru-clipper'))
    print(f'CRASH_EVIDENCE={root}', flush=True)
    return root


@pytest.fixture(scope='module')
def frozen_reader(evidence_root: Path) -> Path:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
    from build_unified_recovery import freeze
    return freeze(evidence_root / 'reader', legacy_helper=True)


@pytest.mark.skipif(sys.platform != 'darwin', reason='Real macOS immutable protection and SIGKILL')
@pytest.mark.parametrize(('boundary', 'category'), [(name, 'R1') for name in BOUNDARIES] + [('old-partial', 'R0')])
def test_independent_thaw_survives_sigkill(boundary: str, category: str, evidence_root: Path,
        frozen_reader: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = evidence_root / f'{boundary}-{category}'
    root.mkdir()
    case = prepare_case(root, monkeypatch, frozen_reader, category=category)
    before = observe(case, 'before')
    kill_at(case, boundary)
    killed = observe(case, 'killed')
    prior, current = json.loads(before.read_text()), json.loads(killed.read_text())
    assert all(current['paths'][str(lock)]['inode'] == prior['paths'][str(lock)]['inode'] for lock in case.locks)
    if boundary in {'controls-before', 'controls-after', 'withdraw-before-commit', 'withdraw-after-commit'}:
        assert current['old_create_denied']
    if current['group'][0] in {'withdrawing', 'thawed'}:
        assert all(row == ['withdrawn'] for row in current['bindings'])
    retry = subprocess.run(command(case, 'retry'), capture_output=True, text=True, timeout=60)
    (root / 'retry.json').write_text(json.dumps({'returncode': retry.returncode, 'stdout': retry.stdout, 'stderr': retry.stderr}))
    observe(case, 'after-direct-retry')
    intent = root / 'interrupted/thaw-intent.json'
    recipe = json.loads(case.recipe.read_text())
    recipe['interrupted_thaw'] = {'path': str(intent), 'sha256': file_sha256(intent)}
    case.recipe.write_text(json.dumps(recipe))
    retry = subprocess.run(command(case, 'resumed'), capture_output=True, text=True, timeout=60)
    (root / 'resumed.json').write_text(json.dumps({'returncode': retry.returncode, 'stdout': retry.stdout, 'stderr': retry.stderr}))
    observe(case, 'after-retry')
    assert retry.returncode == 0, f'{boundary}: {retry.stderr}; evidence: {root}'
    final = json.loads((root / 'after-retry.json').read_text())
    assert final['group'] == ['thawed', 0]
    assert final['old_modes'] == json.loads((root / 'original-modes.json').read_text())
    assert not any(final['old_file_write_denied'].values())
    assert case.database.stat().st_flags & stat.UF_IMMUTABLE
    for lock in case.locks:
        with lock.open('rb') as stream:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)


@pytest.mark.skipif(sys.platform != 'darwin', reason='Real macOS immutable protection and SIGKILL')
@pytest.mark.parametrize('damage', ['intent-pin', 'task-bytes', 'old-bytes', 'new-write', 'lock-inode'])
def test_interrupted_thaw_rejects_changed_evidence(damage: str, evidence_root: Path,
        frozen_reader: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = evidence_root / f'reject-{damage}'
    root.mkdir()
    case = prepare_case(root, monkeypatch, frozen_reader)
    observe(case, 'before')
    kill_at(case, 'controls-after')
    intent = root / 'interrupted/thaw-intent.json'
    recipe = json.loads(case.recipe.read_text())
    recipe['interrupted_thaw'] = {'path': str(intent), 'sha256': file_sha256(intent)}
    if damage == 'intent-pin':
        recipe['interrupted_thaw']['sha256'] = '0' * 64
    if damage in {'task-bytes', 'old-bytes'}:
        directory = case.old if damage == 'old-bytes' else root / 'new-tasks'
        target = next(directory.rglob('subtitles.srt'))
        (root / 'damaged-path.json').write_text(json.dumps({'path': str(target), 'original_sha256': file_sha256(target)}))
        info = target.stat()
        os.chflags(target, 0)
        target.chmod(0o600)
        with target.open('ab') as stream:
            stream.write(b'changed-for-refusal-test')
        target.chmod(stat.S_IMODE(info.st_mode))
        os.chflags(target, info.st_flags)
    if damage == 'new-write':
        with sqlite3.connect(case.database) as connection:
            connection.execute('UPDATE migrationgroup SET new_writes=1 WHERE id=?', (case.group,))
    if damage == 'lock-inode':
        lock = root / 'host-guard/.heavy.lock'
        lock.rename(lock.with_suffix('.original'))
        lock.touch()
    case.recipe.write_text(json.dumps(recipe))
    result = subprocess.run(command(case, 'refused'), capture_output=True, text=True, timeout=60)
    (root / 'refusal.json').write_text(json.dumps({'returncode': result.returncode, 'stderr': result.stderr, 'stdout': result.stdout}))
    state = json.loads(observe(case, 'after-refusal').read_text())
    assert result.returncode == 2, result.stderr
    assert state['old_create_denied'] and not state['thaw_allowed']
    assert all(state['old_file_write_denied'].values())


@pytest.mark.skipif(sys.platform != 'darwin', reason='Real macOS immutable protection')
def test_r2_never_reaches_control_restoration(evidence_root: Path, frozen_reader: Path,
        monkeypatch: pytest.MonkeyPatch) -> None:
    root = evidence_root / 'r2-refused'
    root.mkdir()
    case = prepare_case(root, monkeypatch, frozen_reader, category='R2')
    invocation = command(case, 'refused')
    invocation[6] = json.dumps(BOUNDARIES['controls-before'])
    result = subprocess.run(invocation, capture_output=True, text=True, timeout=60)
    (root / 'refusal.json').write_text(json.dumps({'returncode': result.returncode, 'stderr': result.stderr, 'stdout': result.stdout}))
    state = json.loads(observe(case, 'after-refusal').read_text())
    assert result.returncode == 2 and not result.stdout and 'R2' in result.stderr
    assert state['old_create_denied'] and not state['thaw_allowed']
    assert all(state['old_file_write_denied'].values())


@pytest.mark.skipif(sys.platform != 'darwin', reason='Real macOS immutable protection and SIGKILL')
@pytest.mark.parametrize('damage', ['missing', 'changed', 'receipt-null', 'binding-active', 'member-active'])
def test_completed_thaw_requires_guard_proof(damage: str, evidence_root: Path,
        frozen_reader: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = evidence_root / f'terminal-proof-{damage}'
    root.mkdir()
    case = prepare_case(root, monkeypatch, frozen_reader)
    hashes = {str(path): file_sha256(path) for path in case.old.rglob('*') if path.is_file()}
    kill_at(case, 'thawed-before-receipt')
    observe(case, 'killed')
    proof = case.guard / 'thawed.json'
    if damage == 'missing':
        proof.unlink()
    if damage == 'changed':
        proof.write_text(json.dumps({'version': 1, 'root_group_id': 'different'}))
    statements = {'receipt-null': 'UPDATE migrationgroup SET thaw_receipt_json=NULL',
        'binding-active': "UPDATE taskbinding SET state='activated'", 'member-active': "UPDATE migrationmember SET state='activated'"}
    with sqlite3.connect(case.database) as connection:
        if damage in statements:
            connection.execute(statements[damage])
        bindings = connection.execute('SELECT state FROM taskbinding').fetchall()
        members = connection.execute('SELECT state FROM migrationmember').fetchall()
    intent = root / 'interrupted/thaw-intent.json'
    recipe = json.loads(case.recipe.read_text())
    recipe['interrupted_thaw'] = {'path': str(intent), 'sha256': file_sha256(intent)}
    case.recipe.write_text(json.dumps(recipe))
    result = subprocess.run(command(case, 'refused'), capture_output=True, text=True, timeout=60)
    (root / 'refusal.json').write_text(json.dumps({'returncode': result.returncode, 'stderr': result.stderr, 'stdout': result.stdout}))
    state = json.loads(observe(case, 'after-refusal').read_text())
    assert result.returncode == 2 and not (root / 'refused/result/thaw-receipt.json').exists()
    assert state['group'] == ['thawed', 0]
    with sqlite3.connect(case.database.as_uri() + '?mode=ro&immutable=1', uri=True) as connection:
        assert connection.execute('SELECT state FROM taskbinding').fetchall() == bindings
        assert connection.execute('SELECT state FROM migrationmember').fetchall() == members
    assert state['old_modes'] == json.loads((root / 'original-modes.json').read_text())
    assert {str(path): file_sha256(path) for path in case.old.rglob('*') if path.is_file()} == hashes
    assert case.database.stat().st_flags & stat.UF_IMMUTABLE
