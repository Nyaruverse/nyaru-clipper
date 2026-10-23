from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Literal, assert_never
from uuid import UUID

import pytest

from app.services.task_import import discover_companion


INSTANCE_A = UUID('00000000-0000-4000-8000-000000000001')
INSTANCE_B = UUID('00000000-0000-4000-8000-000000000002')
LEGACY_ID = 'abcdef123456'


def legacy_run(root: Path, *, state: str = 'completed') -> Path:
    directory = root / LEGACY_ID
    directory.mkdir(parents=True)
    (directory / 'source.mp4').write_bytes(b'synthetic-media-only')
    (directory / 'subtitles.srt').write_text('1\n00:00:01,000 --> 00:00:03,000\nfixture\n')
    digest = lambda name: hashlib.sha256((directory / name).read_bytes()).hexdigest()
    (directory / 'job.json').write_text(json.dumps({
        'version': 2, 'state': state, 'duration': 6,
        'video': 'source.mp4', 'video_sha256': digest('source.mp4'),
        'subtitles': 'subtitles.srt', 'artifacts': {'subtitles.srt': digest('subtitles.srt')},
        'completed_clips': [], 'asr': {'language': 'ja'},
    }))
    return directory


def tree_hashes(root: Path) -> dict[str, str]:
    return {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in root.rglob('*') if path.is_file() and not path.is_symlink()}


def test_discovery_is_read_only_idempotent_and_instance_scoped(tmp_path: Path) -> None:
    legacy_run(tmp_path)
    before = tree_hashes(tmp_path)
    first = discover_companion(tmp_path, INSTANCE_A)
    assert first == discover_companion(tmp_path, INSTANCE_A)
    other = discover_companion(tmp_path, INSTANCE_B)
    assert len(first) == len(other) == 1
    assert first[0].identity.legacy_id == other[0].identity.legacy_id == LEGACY_ID
    assert first[0].identity != other[0].identity
    assert first[0].eligibility == 'terminal'
    assert first[0].task_generation == other[0].task_generation
    assert tree_hashes(tmp_path) == before
    assert not (tmp_path / '.source-instance-id').exists()


def test_root_rename_keeps_external_instance_identity(tmp_path: Path) -> None:
    root = tmp_path / 'old-name'
    legacy_run(root)
    before = discover_companion(root, INSTANCE_A)
    renamed = tmp_path / 'renamed'
    root.rename(renamed)
    assert discover_companion(renamed, INSTANCE_A) == before


@pytest.mark.parametrize('filename', ['subtitle-document.json', 'translation.json', 'gui.json',
                                     'subtitle-exports.json', 'subtitle-source-proof.json', 'extra.txt'])
def test_all_task_files_participate_in_generation(tmp_path: Path, filename: str) -> None:
    directory = legacy_run(tmp_path)
    first = discover_companion(tmp_path, INSTANCE_A)[0]
    (directory / filename).write_text('{}' if filename.endswith('.json') else 'new bytes')
    changed = discover_companion(tmp_path, INSTANCE_A)[0]
    assert changed.task_generation != first.task_generation
    assert changed.identity == first.identity


@pytest.mark.parametrize(('state', 'eligibility'), [
    ('completed', 'terminal'), ('failed', 'terminal'), ('interrupted', 'terminal'),
    ('queued', 'requires_withdrawal'), ('recording', 'active'), ('transcribing', 'active'),
])
def test_discovery_does_not_grant_execution_or_takeover(tmp_path: Path, state: str, eligibility: str) -> None:
    legacy_run(tmp_path, state=state)
    item = discover_companion(tmp_path, INSTANCE_A)[0]
    assert item.eligibility == eligibility
    assert 'activated' not in item.model_dump_json()


@pytest.mark.parametrize(('damage', 'code'), [
    ('json', 'invalid_manifest'), ('missing', 'missing_artifact'),
    ('digest', 'artifact_mismatch'), ('traversal', 'unsafe_path'),
    ('symlink', 'unsafe_path'), ('directory_symlink', 'unsafe_path'),
])
def test_bad_task_is_rejected_individually_without_source_writes(
    tmp_path: Path,
    damage: Literal['json', 'missing', 'digest', 'traversal', 'symlink', 'directory_symlink'],
    code: str,
) -> None:
    directory = legacy_run(tmp_path)
    job_path = directory / 'job.json'
    job = json.loads(job_path.read_bytes())
    match damage:
        case 'json':
            job_path.write_text('{broken')
        case 'missing':
            (directory / 'source.mp4').unlink()
        case 'digest':
            (directory / 'source.mp4').write_bytes(b'changed')
        case 'traversal':
            job['video'] = '../outside.mp4'
            job_path.write_text(json.dumps(job))
        case 'symlink':
            (directory / 'source.mp4').unlink()
            (directory / 'source.mp4').symlink_to(job_path)
        case 'directory_symlink':
            moved = tmp_path.parent / (tmp_path.name + '-external')
            directory.rename(moved)
            directory.symlink_to(moved, target_is_directory=True)
        case unreachable:
            assert_never(unreachable)
    healthy = tmp_path / '123456abcdef'
    healthy.mkdir()
    (healthy / 'job.json').write_text('{broken')
    before = tree_hashes(tmp_path)
    result = discover_companion(tmp_path, INSTANCE_A)
    assert len(result) == 2
    item = next(item for item in result if item.identity.legacy_id == LEGACY_ID)
    assert item.eligibility == 'rejected' and item.issue == code
    assert tree_hashes(tmp_path) == before


def test_report_never_exposes_source_paths_urls_or_secret_fields(tmp_path: Path) -> None:
    directory = legacy_run(tmp_path)
    path = directory / 'job.json'
    job = json.loads(path.read_bytes())
    job.update(api_key='SECRET_CANARY_NOT_REAL', url='https://fixture.invalid/private')
    path.write_text(json.dumps(job))
    (tmp_path / 'config.json').write_text('{"api_key":"SECRET_CANARY_NOT_REAL"}')
    report = discover_companion(tmp_path, INSTANCE_A)[0].model_dump_json()
    assert 'SECRET_CANARY_NOT_REAL' not in report
    assert 'fixture.invalid' not in report
    assert str(tmp_path) not in report


def test_discovery_requires_explicit_instance_and_existing_plain_root(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        discover_companion(tmp_path / 'absent', INSTANCE_A)
    linked = tmp_path / 'link'
    linked.symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(ValueError, match='root'):
        discover_companion(linked, INSTANCE_A)


@pytest.mark.parametrize('filename', ['gui.json', 'translation.json', 'subtitle-exports.json', 'subtitle-export-activity.json'])
def test_completed_video_does_not_hide_a_pending_secondary_writer(tmp_path: Path, filename: str) -> None:
    directory = legacy_run(tmp_path)
    payload = {'active': {'state': 'exporting'}} if filename == 'subtitle-exports.json' else {'state': 'translating'}
    (directory / filename).write_text(json.dumps(payload))
    assert discover_companion(tmp_path, INSTANCE_A)[0].eligibility == 'active'


def test_discovery_detects_mutation_during_hashing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import app.services.task_import as module
    directory = legacy_run(tmp_path)
    real_hash = module._hash

    def changed(path: Path) -> str:
        digest = real_hash(path)
        if path.name == 'subtitles.srt':
            path.write_bytes(path.read_bytes() + b'changed')
        return digest

    monkeypatch.setattr(module, '_hash', changed)
    assert discover_companion(tmp_path, INSTANCE_A)[0].issue == 'source_changed'


def test_lock_is_not_acquired_created_or_used_as_content_identity(tmp_path: Path) -> None:
    directory = legacy_run(tmp_path)
    first = discover_companion(tmp_path, INSTANCE_A)
    (directory / '.lock').write_text('old process diagnostics')
    assert discover_companion(tmp_path, INSTANCE_A) == first


def test_manifest_must_register_the_primary_subtitle(tmp_path: Path) -> None:
    directory = legacy_run(tmp_path)
    path = directory / 'job.json'
    job = json.loads(path.read_bytes())
    job['artifacts'] = {}
    path.write_text(json.dumps(job))
    assert discover_companion(tmp_path, INSTANCE_A)[0].issue == 'missing_artifact'


@pytest.mark.parametrize('filename', ['translation.json', 'subtitle-exports.json'])
def test_registered_secondary_files_are_verified(tmp_path: Path, filename: str) -> None:
    directory = legacy_run(tmp_path)
    index = {'artifacts': {'missing.srt': '0' * 64}} if filename == 'translation.json' else {
        'outputs': [{'filename': 'missing.ass', 'sha256': '0' * 64}]}
    (directory / filename).write_text(json.dumps(index))
    assert discover_companion(tmp_path, INSTANCE_A)[0].issue == 'missing_artifact'
