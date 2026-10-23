from pathlib import Path
import json

import pytest
from sqlmodel import Session, select

from app.arctime.native_projection import job_view
from app.arctime.subtitle_style import SubtitleStyle
from app.arctime.unified_host import NativeHost
from app.models_migration import MigrationMember
from app.services.migration_activation import activate_candidate
from app.models_migration import MigrationBatch
from app.services.migration_companion import prepare_companion
from app.services.migration_snapshot import SourceRoots, copy_context, read_candidate
from app.services.task_artifacts import resolve_workstation
from app.services.task_migration import Migrator
from app.services.task_operations import bind_task
from test_unified_artifacts import frozen_source
from test_unified_operations import database


@pytest.fixture
def host(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> NativeHost:
    monkeypatch.setattr('app.arctime.subtitle_encoding.video_metadata', lambda path: (1280, 720, 30.))
    return NativeHost(database(tmp_path), task_root=tmp_path / 'tasks', settings_root=tmp_path / 'settings',
        credential_root=tmp_path / 'credentials', guard_root=tmp_path / 'guard', model=tmp_path / 'unused.bin')


@pytest.mark.parametrize('translated', [0, 1, 2])
@pytest.mark.parametrize('include_segments', [False, True])
def test_saved_translation_counts_nonempty_cues_and_clearing_overrides_source(
    tmp_path: Path, host: NativeHost, translated: int, include_segments: bool,
) -> None:
    source = copy_context(host.root, frozen_source(tmp_path), '.unified/results/fixture')
    with Session(host.engine) as session:
        binding = bind_task(session, source.source_instance_id, source.legacy_id, source.fingerprint, origin='native')
        binding.context_json, binding.state = source.model_dump_json(), 'activated'
        session.add(binding)
        session.commit()
    base = resolve_workstation(source).document(SubtitleStyle())
    cues = [base.cues[0], base.cues[0].model_copy(update={'id': 'cue-000002', 'start_seconds': 30., 'end_seconds': 32.})]
    count = min(translated, len(cues))
    changed = base.model_copy(update={'cues': [cue.model_copy(update={'translation': ' QA ' if i < count else '  '})
        for i, cue in enumerate(cues)]})
    saved = host.documents.save(source.task_id, changed, base=base)
    assert host.documents.load(source.task_id, base).model_dump() == saved.model_dump()
    view = job_view(host, source.task_id, include_segments=include_segments)
    assert view['error'] is None
    expected = 'completed' if count == len(cues) else 'partial' if count else 'not_started'
    assert view['translation']['done'] == count
    assert view['translation']['total'] == len(cues)
    assert view['translation']['state'] == expected
    assert view['translation']['model'] == 'saved-document'
    assert bool(view['bilingual_files']) == bool(count)


@pytest.mark.parametrize('highlights', [False, True])
def test_migrated_selection_uses_registered_archive_without_changing_fingerprint(
    tmp_path: Path, host: NativeHost, highlights: bool,
) -> None:
    from uuid import uuid4
    from app.services.unified_files import file_sha256
    from unification_fixtures import _run
    tasks, settings = tmp_path / 'old-tasks', tmp_path / 'old-settings'
    directory = tasks / 'abcdef123456'
    _run(directory, None)
    settings.mkdir()
    checkpoint = json.loads((directory / 'job.json').read_bytes())
    checkpoint.update(highlight_count=2 if highlights else None, selection=[
        {'start': 0., 'end': 10., 'score': .77 if highlights else None,
         'reasons': ['density', 'laughter'] if highlights else ['manual']}])
    (directory / 'clip-001.mp4').write_bytes((directory / 'source.mp4').read_bytes())
    (directory / 'clip-001.srt').write_bytes((directory / 'subtitles.srt').read_bytes())
    checkpoint['completed_clips'] = [dict(video='clip-001.mp4', subtitles='clip-001.srt',
        video_sha256=file_sha256(directory / 'clip-001.mp4'), subtitles_sha256=file_sha256(directory / 'clip-001.srt'))]
    (directory / 'job.json').write_text(json.dumps(checkpoint))
    migration = Migrator(host.engine, host.root, host.settings_root)
    source_id = uuid4()
    roots = SourceRoots(tasks=tasks, settings=settings)
    migration.register(source_id, roots, origin='companion')
    batch_id = prepare_companion(migration, source_id, roots, legacy_id=directory.name)
    migration.verify(batch_id)
    with Session(host.engine) as session:
        member = session.exec(select(MigrationMember)).one()
        candidate = read_candidate(host.root, member.candidate_path, member.candidate_sha256)
        batch = session.get(MigrationBatch, batch_id)
        activate_candidate(session, host.root, candidate, batch)
        member.state = 'activated'
        session.add(member)
        duplicate = MigrationBatch(id='duplicate-batch', group_id=batch.group_id, source_id=batch.source_id, state='activated')
        session.add(duplicate)
        session.flush()
        session.add(MigrationMember(id='duplicate-member', batch_id=duplicate.id, task_id=member.task_id,
            generation=member.generation, candidate_path=member.candidate_path,
            candidate_sha256=member.candidate_sha256, state='activated'))
        session.commit()
    fingerprint = candidate.context.fingerprint
    view = job_view(host, candidate.context.task_id, include_segments=True)
    assert view['mode'] == ('highlights' if highlights else 'ranges')
    assert view['clips'][0]['score'] == checkpoint['selection'][0]['score']
    assert view['clips'][0]['reasons'] == checkpoint['selection'][0]['reasons']
    assert view['clips'][0]['start'] == 0 and view['clips'][0]['end'] == 10
    assert host.context(candidate.context.task_id).source.fingerprint == fingerprint
    assert host.documents.load(candidate.context.task_id, candidate.document).model_dump() == candidate.document.model_dump()
    archive = host.root / f'.unified/imports/{source_id}/{candidate.generation}/archive/tasks/{directory.name}/job.json'
    original = archive.read_bytes()
    try:
        archive.write_bytes(original + b' ')
        damaged = job_view(host, candidate.context.task_id, include_segments=False)
        assert damaged['state'] == 'failed' and damaged['error'] == 'artifact_source_unavailable'
    finally:
        archive.write_bytes(original)
