from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from pydantic import BaseModel, ConfigDict, JsonValue

from app.arctime import media
from app.services.asr_whisperx import _alignment_model_target_dir, _main_model_target_dir, merge_asr_chunk_segments
from app.services.cache_identity import content_sha256
from app.services.media_chunks import build_media_chunk_manifest, media_chunk_manifest_path, write_media_chunk_manifest_atomically
from app.services.subtitles import SubtitleSegment
from app.services.task_artifacts import ArtifactCue
from app.services.task_execution import Execution, WorkflowFailure
from app.services.task_operations import canonical, digest
from app.services.unified_files import checked_path, file_sha256
from app.settings import Settings


class WhisperXConfiguration(BaseModel):
    model_config = ConfigDict(frozen=True, extra='forbid')
    settings: dict[str, JsonValue]
    model_ref: Path | None
    model_sha256: str | None
    alignment_ref: Path | None
    alignment_sha256: str | None


def snapshot_whisperx(settings: Settings, language: str) -> WhisperXConfiguration:
    values = settings.model_dump(mode='json', include={name for name in Settings.model_fields if name.startswith('whisperx_')})
    if language != 'auto':
        values['whisperx_language'] = language
    effective = Settings.model_validate(values)
    model = Path(effective.whisperx_model_name or '')
    if not model.is_dir():
        model = _main_model_target_dir(effective)
    alignment = Path(effective.whisperx_alignment_model_name or '')
    if not effective.whisperx_alignment_model_name or not alignment.is_dir():
        alignment = _alignment_model_target_dir(effective)
    model = model if model.is_dir() and (model / 'model.bin').is_file() else None
    alignment = alignment if alignment.is_dir() and (alignment / 'config.json').is_file() else None
    return WhisperXConfiguration(settings=values, model_ref=model, model_sha256=content_sha256(model) if model else None,
        alignment_ref=alignment, alignment_sha256=content_sha256(alignment) if alignment else None)


class _Transcript(BaseModel):
    model_config = ConfigDict(frozen=True)
    segments: tuple[ArtifactCue, ...]


class WhisperXAdapter:
    def __init__(self, execution: Execution, configuration: WhisperXConfiguration) -> None:
        self.execution, self.configuration = execution, configuration

    def identity(self) -> dict[str, JsonValue]:
        configuration = self.configuration
        for path, expected in ((configuration.model_ref, configuration.model_sha256), (configuration.alignment_ref, configuration.alignment_sha256)):
            if path is None or expected is None:
                raise WorkflowFailure('asr_model_unavailable_offline')
            if content_sha256(path) != expected:
                raise WorkflowFailure('asr_model_changed')
        return {'engine': 'whisperx', 'language': configuration.settings['whisperx_language'],
            'configuration': configuration.model_dump(mode='json')}

    def transcribe(self, video: Path, directory: Path, duration: float) -> list[SubtitleSegment]:
        identity = {'asr': self.identity(), 'source_sha256': file_sha256(video)}
        work = directory / 'whisperx'
        work.mkdir(exist_ok=True)
        manifest = build_media_chunk_manifest(duration, work_dir=work)
        write_media_chunk_manifest_atomically(media_chunk_manifest_path(work), manifest)
        merged = []
        for chunk in manifest.chunks:
            self.execution.check()
            folder = work / chunk.id
            folder.mkdir(exist_ok=True)
            cache = folder / 'cache.json'
            expected = {**identity, 'start': chunk.start_seconds, 'end': chunk.end_seconds}
            if cache.exists():
                stored = json.loads(cache.read_bytes())
                if (stored['identity'] != expected or file_sha256(chunk.audio_path) != stored.get('audio_sha256')
                        or any(file_sha256(checked_path(folder, name)) != checksum for name, checksum in stored['files'].items())):
                    raise WorkflowFailure('invalid_asr_checkpoint')
            else:
                chunk.audio_path.parent.mkdir(exist_ok=True)
                command = [media.tool_path('ffmpeg'), '-nostdin', '-v', 'error', '-y', '-ss', str(chunk.start_seconds),
                    '-i', str(video), '-t', str(chunk.end_seconds - chunk.start_seconds), '-vn', '-ac', '1', '-ar', '16000',
                    '-c:a', 'pcm_s16le', str(chunk.audio_path)]
                if self.execution.run_command(command, timeout=max(60, duration * 2)).returncode:
                    raise WorkflowFailure('asr_audio_extraction_failed')
                configuration = dict(self.configuration.settings)
                configuration.update(whisperx_model_name=str(self.configuration.model_ref),
                    whisperx_alignment_model_name=str(self.configuration.alignment_ref))
                request = canonical({'audio': str(chunk.audio_path), 'work': str(folder), 'settings': configuration})
                request_path = folder / 'request.json'
                request_path.write_text(request)
                environment = {**os.environ, 'HF_HUB_OFFLINE': '1', 'TRANSFORMERS_OFFLINE': '1'}
                with (folder / 'events.log').open('w') as log:
                    result = self.execution.run_command([sys.executable, '-m', 'app.services.unified_asr_child', str(request_path),
                        '--sha256', digest(request)], timeout=max(600, duration * 20), env=environment, log=log)
                if result.returncode:
                    raise WorkflowFailure('whisperx_child_failed')
                files = {name: file_sha256(checked_path(folder, name)) for name in
                    ('asr-segments.json', 'subtitles.zh.srt', 'asr-alignment-raw.json')}
                media.write_json(cache, {'identity': expected, 'files': files, 'audio_sha256': file_sha256(chunk.audio_path)})
            transcript = _Transcript.model_validate_json((folder / 'asr-segments.json').read_bytes())
            merged.append((chunk, [cue.segment() for cue in transcript.segments]))
        return merge_asr_chunk_segments(merged)
