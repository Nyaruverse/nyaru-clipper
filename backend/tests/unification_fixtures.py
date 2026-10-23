from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from app.arctime import media
from app.arctime.subtitle_document import Cue, SubtitleDocument, base_document
from app.arctime.subtitle_style import SubtitleStyle, TextStyle
from app.arctime.subtitle_templates import StudioSettings, TemplateStore
from app.services.subtitles import (
    SubtitleSegment, SubtitleWord, build_internal_subtitle_json, render_bilingual_srt,
    render_srt, write_bilingual_subtitle_outputs,
)


class MediaContract(BaseModel):
    model_config = ConfigDict(frozen=True)
    width: int
    height: int
    fps: int
    frame_count: int


class ProductContract(BaseModel):
    model_config = ConfigDict(frozen=True)
    sample_frames: tuple[int, ...]
    visible_frames: tuple[int, ...]
    roi: tuple[int, int, int, int]
    cpu: dict[str, str | int]
    tolerance: dict[str, float]


class FixtureContract(BaseModel):
    model_config = ConfigDict(frozen=True)
    media: MediaContract
    product: ProductContract


@dataclass(frozen=True, slots=True)
class StateFixture:
    root: Path
    sources: tuple[Path, Path]


def fixture_contract() -> FixtureContract:
    return FixtureContract.model_validate_json((Path(__file__).parent / 'fixtures/unification/contract.json').read_bytes())


def edit_cues() -> list[Cue]:
    return [Cue(id=f'cue-{i + 1:06d}', start_seconds=i * .03, end_seconds=i * .03 + .02,
                text=f'原文 {i + 1}', translation=f'翻訳 {i + 1}',
                original_style=TextStyle(color='#00FF00') if i == 42 else None)
            for i in range(5000)]


def _run(directory: Path, video: Path | None) -> None:
    directory.mkdir(parents=True)
    source = directory / 'source.mp4'
    if video is None:
        source.write_bytes(b'synthetic fixture; not decodable media')
    else:
        shutil.copyfile(video, source)
    cues = [SubtitleSegment('1', 2., 4., '今日はいい天気です。',
                            [SubtitleWord('今日はいい天気です。', 2., 4., .95)]),
            SubtitleSegment('2', 4., 5., '字幕の位置と時間を確認します。')]
    (directory / 'subtitles.srt').write_text(render_srt(cues), encoding='utf-8')
    media.write_json(directory / 'transcript.json', {'asr': {'engine': 'whisper.cpp', 'language': 'ja'},
                                                   'segments': [asdict(cue) for cue in cues]})
    bilingual = directory / 'subtitles.ja-zh.srt'
    bilingual.write_text(render_bilingual_srt(cues, ['今天天气很好。', '我们检查字幕的位置和时间。']), encoding='utf-8')
    media.write_json(directory / 'translation.json', {'state': 'completed', 'source_language': 'ja',
        'target_language': 'zh', 'artifacts': {bilingual.name: media.fingerprint(bilingual)}})
    media.write_json(directory / 'job.json', {
        'version': 2, 'state': 'completed', 'duration': 4501 / 30,
        'video': 'source.mp4', 'video_sha256': media.fingerprint(source),
        'subtitles': 'subtitles.srt', 'artifacts': {name: media.fingerprint(directory / name)
                                                  for name in ['subtitles.srt', 'transcript.json']},
        'completed_clips': [], 'selection': [], 'ranges': [],
        'asr': {'engine': 'whisper.cpp', 'language': 'ja', 'model_sha256': '0' * 64},
    })
    media.write_json(directory / 'gui.json', {'state': 'completed', 'title': 'Fixture', 'tags': ['fixture'], 'archived': True})


def _workstation(root: Path, video: Path | None) -> None:
    work = root / 'work'
    raw = root / 'raw'
    work.mkdir(parents=True)
    raw.mkdir()
    if video is None:
        (raw / 'source.mp4').write_bytes(b'synthetic fixture; not decodable media')
    else:
        shutil.copyfile(video, raw / 'source.mp4')
    segments = [SubtitleSegment('ws-1', 21., 24., '这是统一架构的测试录像。',
                               [SubtitleWord('这是统一架构的测试录像。', 21., 24., .95)])]
    media.write_json(work / 'asr-segments.json', build_internal_subtitle_json(
        segments, model_metadata={'engine': 'whisperx', 'language': 'zh', 'fixture_only': True}, elapsed_seconds=1.))
    (work / 'subtitles.zh.srt').write_text(render_srt(segments), encoding='utf-8')
    write_bilingual_subtitle_outputs(work, segments, ['これは統一アーキテクチャのテスト映像です。'],
        model_metadata={'engine': 'frozen-format', 'source_language': 'zh', 'target_language': 'ja', 'fixture_only': True},
        elapsed_seconds=1.)
    media.write_json(root / 'frozen-artifact-index.json', {
        'format': 'workstation', 'status': 'frozen_format_fixture', 'source_language': 'zh',
        'target_language': 'ja', 'artifacts': {
            str(path.relative_to(root)): media.fingerprint(path) for path in root.rglob('*') if path.is_file()},
    })


def build_state(root: Path, video: Path | None = None) -> StateFixture:
    root.mkdir(mode=0o700)
    sources = (root / 'instance-a' / 'runs', root / 'instance-b' / 'runs')
    for source in sources:
        _run(source / 'abcdef123456', video)
        for identity in ['111111111111', '222222222222', '333333333333', '444444444444', '555555555555']:
            shutil.copytree(source / 'abcdef123456', source / identity)
        (source / '111111111111' / 'job.json').write_text('{broken')
        (source / '222222222222' / 'source.mp4').unlink()
        (source / '333333333333' / 'orphan.ass').write_text('unregistered fixture output')
        for identity, state in [('444444444444', 'queued'), ('555555555555', 'failed')]:
            path = source / identity / 'job.json'
            job = json.loads(path.read_bytes())
            job['state'] = state
            media.write_json(path, job)
    _workstation(root / 'workstation' / 'same-legacy-id', video)
    settings = root / 'settings'
    settings.mkdir()
    store = TemplateStore(settings)
    project = store.save_project('Fixture project', 'fixture.atpj', b'fixture ArcTime project')
    style = store.save_style('Fixture', SubtitleStyle(), arctime_template_id=project.id)
    store.save_defaults(SubtitleStyle())
    store.save_studio_settings(StudioSettings(default_template_id=style.id, language='ja', mode='saozi'))
    for name in ['global_package_root', 'migration_registry', 'guard_root']:
        directory = root / name
        directory.mkdir()
        media.write_json(directory / 'fixture.json', {'generation': 1, 'status': 'fixture_only'})
    credentials = root / 'credentials'
    credentials.mkdir(mode=0o700)
    (credentials / 'config.json').write_text('{"deepseek_api_key":"SECRET_CANARY_NOT_REAL"}')
    (credentials / 'config.json').chmod(0o600)
    for level in ['R0', 'R1', 'R2']:
        directory = root / 'rollback' / level / 'tasks' / 'abcdef123456'
        shutil.copytree(sources[0] / 'abcdef123456', directory)
        media.write_json(directory.parent.parent / 'fixture-state.json', {
            'status': 'fixture_only', 'level': level, 'activated': level != 'R0', 'new_writes': level == 'R2'})
        if level == 'R2':
            style = SubtitleStyle()
            document = (base_document(directory, style) if video else SubtitleDocument(
                source_fingerprint='0' * 64, revision=0, style=style, cues=[],
                width=1280, height=720, duration=4501 / 30, fps=30))
            edited = document.model_copy(update={'revision': 1, 'cues': edit_cues()})
            media.write_json(directory / 'subtitle-document.json', edited.model_dump())
            if document._legacy_fingerprint is not None:
                media.write_json(directory / 'subtitle-source-proof.json', {
                    'legacy': document._legacy_fingerprint, 'content': document.source_fingerprint})
    files = {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
             for path in sorted(root.rglob('*')) if path.is_file() and credentials not in path.parents}
    media.write_json(root / 'fixture-receipt.json', {'status': 'fixture_only', 'files': files,
        'protected_credential_reference': True, 'decodable_media': video is not None})
    return StateFixture(root, sources)
