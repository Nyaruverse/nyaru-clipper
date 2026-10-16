from __future__ import annotations

import hashlib
import json
import os
import threading
from collections import OrderedDict
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.arctime import media, workflow
from app.arctime.subtitle_style import SubtitleStyle, TextStyle, _text


class Emphasis(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, frozen=True)
    start: int = Field(ge=0)
    end: int = Field(gt=0)
    color: str = Field(pattern=r'^#[0-9A-Fa-f]{6}$')
    bold: bool


class Cue(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, frozen=True, allow_inf_nan=False)
    id: str = Field(pattern=r'^(cue-\d{6}|edit-[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})$')
    start_seconds: float = Field(ge=0)
    end_seconds: float = Field(gt=0)
    text: str = Field(max_length=10000)
    translation: str = Field(default='', max_length=10000)
    original_style: TextStyle | None = None
    translation_style: TextStyle | None = None
    original_emphasis: list[Emphasis] = Field(default_factory=list, max_length=1000)
    translation_emphasis: list[Emphasis] = Field(default_factory=list, max_length=1000)

    @model_validator(mode='after')
    def valid_cue(self) -> Cue:
        if self.start_seconds >= self.end_seconds:
            raise ValueError('Cue end must follow start.')
        for text, spans in ((self.text, self.original_emphasis), (self.translation, self.translation_emphasis)):
            _text(text)
            previous = 0
            for span in spans:
                if not previous <= span.start < span.end <= len(text):
                    raise ValueError('Emphasis must be ordered, nonoverlapping Unicode codepoint ranges.')
                previous = span.end
        return self


class SubtitleDocument(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, frozen=True, allow_inf_nan=False)
    version: Literal[1] = 1
    source_fingerprint: str = Field(pattern=r'^[0-9a-f]{64}$')
    revision: int = Field(ge=0)
    style: SubtitleStyle
    cues: list[Cue] = Field(max_length=50000)
    width: int = Field(gt=0, le=16384)
    height: int = Field(gt=0, le=16384)
    duration: float = Field(gt=0)
    fps: float = Field(gt=0, le=1000)

    @model_validator(mode='after')
    def valid_document(self) -> SubtitleDocument:
        if type(self.version) is not int or len({cue.id for cue in self.cues}) != len(self.cues):
            raise ValueError('Version must be integer 1 and cue IDs must be unique.')
        if any(cue.end_seconds > self.duration for cue in self.cues):
            raise ValueError('Cue time exceeds source duration.')
        for style in [self.style.original, self.style.translation, *(s for cue in self.cues for s in (cue.original_style, cue.translation_style) if s)]:
            if (style.x is not None and style.x > self.width) or (style.y is not None and style.y > self.height):
                raise ValueError('Subtitle position exceeds source canvas.')
        return self


def base_document(directory: Path, style: SubtitleStyle) -> SubtitleDocument:
    # Import here to keep the request models independent of filesystem operations.
    from app.arctime.subtitle_inputs import ExportRequest, load_inputs
    from app.arctime.subtitle_encoding import video_metadata
    job = workflow._path(directory, 'job.json')
    translation = workflow._path(directory, 'translation.json')
    bilingual = False
    if translation.is_file():
        bilingual = json.loads(translation.read_bytes()).get('state') == 'completed'
    inputs = load_inputs(directory, ExportRequest(kind='ass', video='source.mp4', style=style, bilingual=bilingual))
    width, height, fps = video_metadata(inputs.source)
    source = {'job': media.fingerprint(job), 'artifacts': inputs.digests,
              'translation': media.fingerprint(translation) if translation.is_file() else None,
              'width': width, 'height': height, 'fps': fps}
    fingerprint = hashlib.sha256(json.dumps(source, sort_keys=True).encode()).hexdigest()
    cues = [Cue(id=f'cue-{index + 1:06d}', start_seconds=cue.start_seconds, end_seconds=cue.end_seconds,
                text=cue.text, translation=inputs.translated[index].text if inputs.translated else '')
            for index, cue in enumerate(inputs.original)]
    return SubtitleDocument(source_fingerprint=fingerprint, revision=0, style=style, cues=cues,
                            width=width, height=height, fps=fps, duration=json.loads(job.read_bytes())['duration'])


def validate_source(document: SubtitleDocument, base: SubtitleDocument) -> None:
    if (document.source_fingerprint, document.width, document.height, document.duration, document.fps) != (
            base.source_fingerprint, base.width, base.height, base.duration, base.fps):
        raise ValueError('字幕来源已改变；请保留当前编辑并重新载入原任务')


def load_document(directory: Path, style: SubtitleStyle, *, source: bool = False, base: SubtitleDocument | None = None) -> SubtitleDocument:
    base = base or base_document(directory, style)
    path = workflow._path(directory, 'subtitle-document.json')
    if not path.is_file():
        return base
    document = SubtitleDocument.model_validate_json(path.read_bytes())
    if source:
        return base.model_copy(update={'revision': document.revision})
    validate_source(document, base)
    return document


def save_document(directory: Path, document: SubtitleDocument, *, base: SubtitleDocument | None = None) -> SubtitleDocument:
    with workflow.exclusive_lock(workflow._path(directory, '.lock')):
        base = base or base_document(directory, document.style)
        validate_source(document, base)
        path = workflow._path(directory, 'subtitle-document.json')
        current = SubtitleDocument.model_validate_json(path.read_bytes()) if path.is_file() else base
        if document.revision != current.revision:
            raise ValueError('字幕版本冲突；请保留当前编辑并重新载入')
        if current.source_fingerprint != document.source_fingerprint:
            backup = workflow._path(directory, f'subtitle-document-{current.source_fingerprint}-r{current.revision}.json')
            if backup.exists():
                if backup.read_bytes() != path.read_bytes():
                    raise ValueError('旧编辑备份冲突；原文件已保留')
            else:
                os.link(path, backup)
        saved = document.model_copy(update={'revision': document.revision + 1})
        media.write_json(workflow._path(directory, 'subtitle-document.json'), saved.model_dump())
        return saved


def clip_document(document: SubtitleDocument, start: float, end: float) -> SubtitleDocument:
    cues = [cue.model_copy(update={'start_seconds': max(cue.start_seconds, start) - start,
                                   'end_seconds': min(cue.end_seconds, end) - start})
            for cue in document.cues if cue.start_seconds < end and cue.end_seconds > start]
    return document.model_copy(update={'cues': cues, 'duration': end - start})


def _source_signature(directory: Path) -> tuple:
    job_path = workflow._path(directory, 'job.json')
    job = json.loads(job_path.read_bytes())
    names = {'job.json', 'translation.json', job['video'], job['subtitles'], *job['artifacts']}
    translation_path = workflow._path(directory, 'translation.json')
    if translation_path.is_file():
        translation = json.loads(translation_path.read_bytes())
        names.update(translation.get('artifacts', {}))
    signature = []
    for name in sorted(names):
        path = workflow._path(directory, name)
        try:
            info = path.stat()
        except FileNotFoundError:
            signature.append((name, None))
        else:
            signature.append((name, info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns))
    return tuple(signature)


class DocumentStore:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.bases: OrderedDict[Path, tuple[tuple, SubtitleDocument]] = OrderedDict()

    def base(self, directory: Path, style: SubtitleStyle) -> SubtitleDocument:
        signature = _source_signature(directory)
        with self.lock:
            cached = self.bases.get(directory)
            if cached and cached[0] == signature:
                self.bases.move_to_end(directory)
                return cached[1].model_copy(update={'style': style})
        document = base_document(directory, style)
        if _source_signature(directory) != signature:
            raise ValueError('字幕来源在校验期间改变，请重试')
        with self.lock:
            self.bases[directory] = signature, document
            self.bases.move_to_end(directory)
            while len(self.bases) > 32:
                self.bases.popitem(last=False)
        return document

    def load(self, directory: Path, style: SubtitleStyle, *, source: bool = False) -> SubtitleDocument:
        job = json.loads(workflow._path(directory, 'job.json').read_bytes())
        if job.get('live') and job.get('subtitle_template'):
            style = SubtitleStyle.model_validate(job['subtitle_template']['style'])
        return load_document(directory, style, source=source, base=self.base(directory, style))

    def save(self, directory: Path, document: SubtitleDocument) -> SubtitleDocument:
        return save_document(directory, document, base=self.base(directory, document.style))
