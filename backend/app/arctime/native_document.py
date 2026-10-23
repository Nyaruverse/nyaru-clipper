from __future__ import annotations

import re
from typing import TYPE_CHECKING

from app.arctime import media
from app.arctime.workstation_projection import TextArtifact
from app.services.subtitles import SubtitleSegment, render_bilingual_srt
from app.services.task_artifacts import ResolvedArtifacts

if TYPE_CHECKING:
    from app.arctime.unified_host import NativeHost


def saved_bilingual(host: NativeHost, context: ResolvedArtifacts, name: str) -> TextArtifact | None:
    language = context.source.source_language
    if language not in {'zh', 'ja'}:
        return None
    suffix = f'.saved.{language}-' + ('zh' if language == 'ja' else 'ja')
    if suffix not in name:
        return None
    basename = name.replace(suffix, '')
    if not re.fullmatch(r'(subtitles|clip-\d{3,})\.(srt|vtt)', basename):
        return None
    base = context.document(host.templates.load_defaults())
    document = host.documents.load(context.source.task_id, base)
    if not any(cue.translation.strip() for cue in document.cues):
        return None
    original = [SubtitleSegment(cue.id, cue.start_seconds, cue.end_seconds, cue.text) for cue in document.cues]
    translated = [SubtitleSegment(cue.id, cue.start_seconds, cue.end_seconds, cue.translation) for cue in document.cues]
    if basename.startswith('clip-'):
        index = int(basename.partition('.')[0].removeprefix('clip-')) - 1
        if not 0 <= index < len(context.source.clips):
            return None
        clip = context.source.clips[index]
        original = media.clip_subtitles(original, clip.start, clip.end)
        translated = media.clip_subtitles(translated, clip.start, clip.end)
    content = render_bilingual_srt(original, [cue.text for cue in translated])
    if name.endswith('.vtt'):
        content = 'WEBVTT\n\n' + re.sub(r'(?<=\d{2}:\d{2}:\d{2}),', '.', content)
    return TextArtifact(content, 'text/vtt' if name.endswith('.vtt') else 'application/x-subrip')
