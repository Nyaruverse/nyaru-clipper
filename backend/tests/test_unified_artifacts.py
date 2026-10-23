from __future__ import annotations

import json
from pathlib import Path
from uuid import UUID

import pytest

from app.arctime import media
from app.arctime.subtitle_inputs import ExportRequest, load_inputs
from app.arctime.subtitle_style import SubtitleStyle
from app.arctime.subtitle_document import DocumentStore
from app.services.task_artifacts import ArtifactFile, WorkstationArtifacts, resolve_workstation
from app.services.workstation_artifacts import snapshot_workstation
from unification_fixtures import build_state


def frozen_source(tmp_path: Path) -> WorkstationArtifacts:
    bundle = build_state(tmp_path / 'source')
    root = bundle.root / 'workstation/same-legacy-id'
    reference = lambda name: ArtifactFile(path=name, sha256=media.fingerprint(root / name))
    return WorkstationArtifacts(source_instance_id=UUID('00000000-0000-4000-8000-000000000001'),
        legacy_id='same-legacy-id', root=root, duration=4501 / 30,
        video=reference('raw/source.mp4'), transcript=reference('work/asr-segments.json'),
        subtitles=reference('work/subtitles.zh.srt'), translation=reference('work/subtitles.zh-ja.json'),
        source_language='zh', target_language='ja')


def test_workstation_inputs_do_not_need_a_companion_manifest(tmp_path: Path) -> None:
    source = frozen_source(tmp_path)
    resolved = resolve_workstation(source)
    output = tmp_path / 'new-editor-root'
    output.mkdir()
    inputs = load_inputs(output, ExportRequest(kind='ass', video='source.mp4', style=SubtitleStyle(), bilingual=True),
                         artifacts=resolved)
    assert inputs.source == source.root / 'raw/source.mp4'
    assert inputs.original[0].text == '这是统一架构的测试录像。'
    assert inputs.original[0].words[0].confidence == .95
    assert inputs.translated[0].text == 'これは統一アーキテクチャのテスト映像です。'
    assert inputs.time_origin == 0
    assert not (output / 'job.json').exists()
    assert not (source.root / 'job.json').exists()


@pytest.mark.parametrize('damage', ['missing', 'hash', 'escape', 'symlink', 'translation'])
def test_workstation_source_rejects_invalid_inputs(tmp_path: Path, damage: str) -> None:
    source = frozen_source(tmp_path)
    if damage == 'missing':
        (source.root / source.video.path).unlink()
    elif damage == 'hash':
        (source.root / source.video.path).write_bytes(b'changed')
    elif damage == 'escape':
        source = source.model_copy(update={'video': ArtifactFile(path='../outside.mp4', sha256='0' * 64)})
    elif damage == 'symlink':
        (source.root / source.video.path).unlink()
        (source.root / source.video.path).symlink_to(source.root / source.transcript.path)
    else:
        path = source.root / source.translation.path
        data = json.loads(path.read_bytes())
        data['segments'][0]['text'] = 'not the same source'
        media.write_json(path, data)
        source = source.model_copy(update={'translation': ArtifactFile(path=source.translation.path, sha256=media.fingerprint(path))})
    with pytest.raises(ValueError):
        resolve_workstation(source)


def test_source_without_translation_does_not_invent_one(tmp_path: Path) -> None:
    source = frozen_source(tmp_path).model_copy(update={'translation': None, 'target_language': None})
    resolved = resolve_workstation(source)
    request = ExportRequest(kind='ass', video='source.mp4', style=SubtitleStyle())
    assert load_inputs(tmp_path, request, artifacts=resolved).translated is None
    with pytest.raises(ValueError):
        load_inputs(tmp_path, request.model_copy(update={'bilingual': True}), artifacts=resolved)


def test_explicit_reference_media_stays_in_its_separate_trusted_root(tmp_path: Path) -> None:
    source = frozen_source(tmp_path)
    external = tmp_path / 'trusted-media'
    external.mkdir()
    (source.root / source.video.path).rename(external / 'reference.mp4')
    source = source.model_copy(update={'media_root': external,
        'video': ArtifactFile(storage='media', path='reference.mp4', sha256=source.video.sha256)})
    resolved = resolve_workstation(source)
    request = ExportRequest(kind='ass', video='source.mp4', style=SubtitleStyle())
    assert load_inputs(tmp_path, request, artifacts=resolved).source == external / 'reference.mp4'
    (external / 'reference.mp4').write_bytes(b'changed reference')
    with pytest.raises(ValueError):
        resolved.verify()


def test_existing_document_store_saves_and_reopens_workstation_draft(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.arctime import subtitle_encoding
    source = frozen_source(tmp_path)
    resolved = resolve_workstation(source)
    monkeypatch.setattr(subtitle_encoding, 'video_metadata', lambda path: (1280, 720, 30.))
    output = tmp_path / 'editor'
    output.mkdir()
    store = DocumentStore(artifacts=lambda directory: resolved)
    document = store.load(output, SubtitleStyle())
    assert document.cues[0].translation == 'これは統一アーキテクチャのテスト映像です。'
    edited = document.model_copy(update={'cues': [document.cues[0].model_copy(update={'text': '改稿'})]})
    saved = store.save(output, edited)
    assert saved.revision == 1
    assert DocumentStore(artifacts=lambda directory: resolved).load(output, SubtitleStyle()).model_dump() == saved.model_dump()
    with pytest.raises(ValueError, match='冲突'):
        store.save(output, edited)
    assert not (output / 'job.json').exists()


def test_snapshot_reads_real_registered_workstation_records(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from sqlmodel import SQLModel, Session, create_engine, select
    from app.models import Artifact, Task
    source = frozen_source(tmp_path)
    monkeypatch.setattr(media, 'probe_video', lambda path: source.duration)
    engine = create_engine('sqlite:///' + str(tmp_path / 'old.sqlite3'))
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(Task(id='same-legacy-id', source_url='https://fixture.invalid', normalized_source_url='https://fixture.invalid', status='success'))
        for kind, reference, metadata in [
            ('source_video', source.video, {}), ('transcript_json', source.transcript, {}),
            ('subtitle_srt', source.subtitles, {'language': 'zh'}),
            ('bilingual_transcript_json', source.translation, {'model_metadata': {'source_language': 'zh', 'target_language': 'ja'}}),
        ]:
            session.add(Artifact(task_id='same-legacy-id', stage_name='fixture', kind=kind,
                                 path=str(source.root / reference.path), metadata_json=json.dumps(metadata)))
        session.commit()
        snapshot = snapshot_workstation(session, task_id='same-legacy-id', root=source.root,
                                        source_instance_id=source.source_instance_id)
        assert snapshot.source.task_id == source.task_id
        assert snapshot.cues[0].words[0].confidence == .95
        assert snapshot.source.target_language == 'ja'
        assert session.exec(select(Task)).one().status == 'success'


def test_registered_reference_mode_resolves_configured_root_without_copy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from sqlmodel import SQLModel, Session, create_engine
    from app.models import Artifact, Task
    from app.services.source_catalog import configured_local_roots
    source = frozen_source(tmp_path)
    external = tmp_path / 'local-media'
    external.mkdir()
    (source.root / source.video.path).rename(external / 'original.mp4')
    monkeypatch.setenv('APP_LOCAL_IMPORT_ROOTS', str(external))
    metadata = {'import_mode': 'reference', 'root_id': configured_local_roots()[0].id, 'relative_path': 'original.mp4'}
    reference_path = source.root / 'raw/local-reference.json'
    reference_path.write_text(json.dumps(metadata))
    monkeypatch.setattr(media, 'probe_video', lambda path: source.duration)
    engine = create_engine('sqlite:///' + str(tmp_path / 'reference.sqlite3'))
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(Task(id=source.legacy_id, source_url='local:reference', normalized_source_url='local:reference', status='success'))
        for kind, path, details in [('source_video', reference_path, metadata),
            ('transcript_json', source.root / source.transcript.path, {}),
            ('subtitle_srt', source.root / source.subtitles.path, {'language': 'zh'})]:
            session.add(Artifact(task_id=source.legacy_id, stage_name='fixture', kind=kind,
                path=str(path), metadata_json=json.dumps(details)))
        session.commit()
        context = snapshot_workstation(session, task_id=source.legacy_id, root=source.root, source_instance_id=source.source_instance_id)
    assert context.source.checked(context.source.video) == external / 'original.mp4'
    assert context.source.supporting[0].path == 'raw/local-reference.json'
    assert not (source.root / 'raw/source.mp4').exists()


@pytest.mark.parametrize('languages', [('ja', 'zh'), ('zh', 'ja')])
def test_direction_and_short_tail_keep_global_and_clip_time_distinct(tmp_path: Path, languages: tuple[str, str]) -> None:
    from app.services.task_artifacts import ArtifactClip
    from app.services.subtitles import SubtitleSegment, render_srt
    source = frozen_source(tmp_path)
    source_language, target_language = languages
    texts = {'ja': '最後の短い字幕です。', 'zh': '这是最后一条短字幕。'}
    row = {'id': 'tail', 'start_seconds': source.duration - 1., 'end_seconds': source.duration,
        'text': texts[source_language]}
    original = source.root / source.transcript.path
    original.write_text(json.dumps({'segments': [row]}))
    subtitles = source.root / source.subtitles.path
    subtitles.write_text(render_srt([SubtitleSegment(**row)]))
    translated = source.root / source.translation.path
    translated.write_text(json.dumps({'segments': [{**row, 'translated_text': texts[target_language]}]}))
    clip = source.root / 'exports/tail.mp4'
    clip.parent.mkdir(exist_ok=True)
    clip.write_bytes(b'frozen short-tail media placeholder')
    source = source.model_copy(update={'transcript': ArtifactFile(path=source.transcript.path, sha256=media.fingerprint(original)),
        'subtitles': ArtifactFile(path=source.subtitles.path, sha256=media.fingerprint(subtitles)),
        'translation': ArtifactFile(path=source.translation.path, sha256=media.fingerprint(translated)),
        'source_language': source_language, 'target_language': target_language,
        'clips': (ArtifactClip(video=ArtifactFile(path='exports/tail.mp4', sha256=media.fingerprint(clip)), start=140., end=source.duration),)})
    resolved = resolve_workstation(source)
    inputs = load_inputs(tmp_path, ExportRequest(kind='ass', video='clip-001.mp4', style=SubtitleStyle(), bilingual=True), artifacts=resolved)
    assert inputs.time_origin == 140.
    assert inputs.original[0].start_seconds == pytest.approx(source.duration - 141.)
    assert inputs.original[0].end_seconds == pytest.approx(source.duration - 140.)
    assert inputs.original[0].text == texts[source_language] and inputs.translated[0].text == texts[target_language]


def test_symlink_in_source_root_ancestry_is_rejected(tmp_path: Path) -> None:
    source = frozen_source(tmp_path)
    link = tmp_path / 'link'
    link.symlink_to(source.root.parent, target_is_directory=True)
    with pytest.raises(ValueError):
        resolve_workstation(source.model_copy(update={'root': link / source.root.name}))
