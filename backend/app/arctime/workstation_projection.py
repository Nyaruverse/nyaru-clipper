from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.arctime import media
from app.services.subtitles import render_bilingual_srt, render_srt
from app.services.task_artifacts import ResolvedArtifacts


class SegmentView(BaseModel):
    model_config = ConfigDict(frozen=True)
    id: str
    start_seconds: float
    end_seconds: float
    text: str


class ClipView(BaseModel):
    model_config = ConfigDict(frozen=True)
    video: str
    subtitles: str
    bilingual_subtitles: str | None = None
    start: float
    end: float
    score: float | None = None
    reasons: tuple[str, ...] = ()


class TranslationView(BaseModel):
    model_config = ConfigDict(frozen=True)
    state: Literal['completed', 'not_started']
    error: str | None = None
    message: str | None = None
    done: int
    total: int
    model: str = 'existing-result'


class WorkstationEditorJob(BaseModel):
    model_config = ConfigDict(frozen=True)
    id: str
    state: Literal['completed'] = 'completed'
    phase: str = 'existing_result'
    message: str = '已有视频和字幕已载入，可以编辑'
    error: str | None = None
    started_at: float
    duration: float
    mode: Literal['ranges'] = 'ranges'
    live: bool = False
    can_stop: bool = False
    can_resume: bool = False
    has_source: bool = True
    language: str
    bilingual_suffix: str
    clips: list[ClipView]
    segments: list[SegmentView] = Field(default_factory=list)
    bilingual_segments: list[SegmentView] = Field(default_factory=list)
    bilingual_files: list[str] = Field(default_factory=list)
    translation: TranslationView


def project_artifacts(artifacts: ResolvedArtifacts, *, include_segments: bool) -> WorkstationEditorJob:
    source = artifacts.source
    artifacts.verify()
    suffix = f'.{source.source_language}-{source.target_language}' if source.target_language else ''
    clips = [ClipView(video=f'clip-{i + 1:03d}.mp4', subtitles=f'clip-{i + 1:03d}.srt',
             bilingual_subtitles=f'clip-{i + 1:03d}{suffix}.srt' if source.translation else None,
             start=clip.start, end=clip.end) for i, clip in enumerate(source.clips)]
    return WorkstationEditorJob(id=source.task_id, started_at=source.checked(source.video).stat().st_mtime,
        duration=source.duration, language=source.source_language, bilingual_suffix=suffix, clips=clips,
        segments=[SegmentView(id=cue.id, start_seconds=cue.start_seconds, end_seconds=cue.end_seconds, text=cue.text)
                  for cue in artifacts.cues] if include_segments else [],
        bilingual_segments=[SegmentView(id=cue.id, start_seconds=cue.start_seconds, end_seconds=cue.end_seconds,
                            text=cue.text + '\n' + (cue.translated_text or '')) for cue in artifacts.cues]
                            if include_segments and source.translation else [],
        bilingual_files=['subtitles' + suffix + '.srt', *(clip.bilingual_subtitles for clip in clips if clip.bilingual_subtitles)]
                        if source.translation else [],
        translation=TranslationView(state='completed' if source.translation else 'not_started',
                        done=len(artifacts.cues) if source.translation else 0, total=len(artifacts.cues)))


@dataclass(frozen=True, slots=True)
class TextArtifact:
    content: str
    media_type: str


def text_artifact(artifacts: ResolvedArtifacts, name: str) -> TextArtifact | None:
    artifacts.verify()
    if name == 'transcript.txt':
        return TextArtifact('\n'.join(cue.text for cue in artifacts.cues) + '\n', 'text/plain')
    suffix = f'.{artifacts.source.source_language}-{artifacts.source.target_language}'
    bilingual = suffix in name
    basename = name.replace(suffix, '') if bilingual else name
    if not re.fullmatch(r'(subtitles|clip-\d{3,})\.(srt|vtt)', basename):
        return None
    if bilingual and artifacts.source.translation is None:
        return None
    original = [cue.segment() for cue in artifacts.cues]
    translated = [cue.segment(translated=True) for cue in artifacts.cues]
    if basename.startswith('clip-'):
        index = int(basename.partition('.')[0].removeprefix('clip-')) - 1
        if not 0 <= index < len(artifacts.source.clips):
            return None
        clip = artifacts.source.clips[index]
        original = media.clip_subtitles(original, clip.start, clip.end)
        translated = media.clip_subtitles(translated, clip.start, clip.end)
    content = render_bilingual_srt(original, [cue.text for cue in translated]) if bilingual else render_srt(original)
    if name.endswith('.vtt'):
        content = 'WEBVTT\n\n' + re.sub(r'(?<=\d{2}:\d{2}:\d{2}),', '.', content)
    return TextArtifact(content, 'text/vtt' if name.endswith('.vtt') else 'application/x-subrip')
