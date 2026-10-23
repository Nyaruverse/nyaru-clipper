from __future__ import annotations

import json
import re
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict
from sqlmodel import Session, select

from app.models_unified import OperationStep, UnifiedOperation, UnifiedPublication
from app.services.task_publication import Publisher
from app.services.unified_files import checked_path

if TYPE_CHECKING:
    from app.arctime.unified_host import NativeHost


class PartialClip(BaseModel):
    model_config = ConfigDict(frozen=True)
    clip_index: int
    start: float
    end: float
    publication_id: str
    bilingual_publication_id: str | None = None
    source_language: str | None = None


def clips(host: NativeHost, task_id: str) -> list[PartialClip]:
    with Session(host.engine) as session:
        rows = session.exec(select(UnifiedPublication).join(UnifiedOperation)
            .where(UnifiedOperation.task_id == task_id, UnifiedPublication.state == 'committed')
            .order_by(UnifiedPublication.attempt.desc())).all()
        metadata = {row.id: session.get(OperationStep, row.step_id) for row in rows}
    result = {}
    bilingual = {}
    for row in rows:
        step = metadata[row.id]
        if step is None:
            continue
        try:
            Publisher(host.engine, host.root).registered(row.id)
            clip = PartialClip.model_validate({**json.loads(step.metadata_json), 'publication_id': row.id})
            if re.fullmatch(r'live-clip-\d{3,}', step.step_key):
                result.setdefault(clip.clip_index, clip)
            elif re.fullmatch(r'live-bilingual-\d{3,}:[0-9a-f]{64}', step.step_key):
                bilingual.setdefault(clip.clip_index, clip)
        except (ValueError, OSError):
            continue
    for index, clip in result.items():
        translated = bilingual.get(index)
        if translated is not None and (translated.start, translated.end) == (clip.start, clip.end):
            result[index] = clip.model_copy(update={'bilingual_publication_id': translated.publication_id,
                'source_language': translated.source_language})
    return [result[index] for index in sorted(result)]


def file(host: NativeHost, task_id: str, name: str) -> Path | None:
    match = re.fullmatch(r'clip-(\d{3,})(\.ja-zh|\.zh-ja)?\.(mp4|srt)', name)
    if match is None:
        return None
    clip = next((clip for clip in clips(host, task_id) if clip.clip_index == int(match.group(1))), None)
    if clip is None:
        return None
    bilingual = match.group(2) is not None
    if bilingual and (clip.bilingual_publication_id is None or match.group(3) != 'srt'
            or match.group(2) != { 'ja': '.ja-zh', 'zh': '.zh-ja'}.get(clip.source_language)):
        return None
    receipt = Publisher(host.engine, host.root).registered(clip.bilingual_publication_id if bilingual else clip.publication_id)
    role = 'bilingual_srt' if bilingual else 'video' if match.group(3) == 'mp4' else 'subtitles'
    member = next(member for member in receipt.outputs if member.role == role)
    return checked_path(host.root, member.target)
