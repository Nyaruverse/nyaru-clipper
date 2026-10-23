from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Literal, assert_never
from uuid import UUID, uuid5

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.arctime import media
from app.services.subtitles import SubtitleSegment, SubtitleWord

if TYPE_CHECKING:
    from app.arctime.subtitle_document import SubtitleDocument
    from app.arctime.subtitle_style import SubtitleStyle

Digest = Annotated[str, Field(pattern=r'^[0-9a-f]{64}$')]


class ArtifactError(ValueError):
    def __init__(self, message: str = '工作站来源缺失、已改变或格式无效；原文件已保留') -> None:
        super().__init__(message)


def artifact_path(root: Path, name: str) -> Path:
    relative = Path(name)
    if relative.is_absolute() or '..' in relative.parts or any(component.is_symlink() for component in (root, *root.parents)):
        raise ArtifactError()
    path = root / relative
    for component in (path, *path.parents):
        if component == root:
            break
        if component.is_symlink():
            raise ArtifactError()
    if not path.is_file() or not path.resolve().is_relative_to(root.resolve()):
        raise ArtifactError()
    return path


class ArtifactFile(BaseModel):
    model_config = ConfigDict(frozen=True, extra='forbid')
    path: str
    sha256: Digest
    storage: Literal['task', 'media'] = 'task'


class ArtifactWord(BaseModel):
    model_config = ConfigDict(frozen=True, allow_inf_nan=False)
    text: str
    start_seconds: float = Field(ge=0)
    end_seconds: float = Field(ge=0)
    confidence: float | None = Field(default=None, ge=0, le=1)


class ArtifactCue(BaseModel):
    model_config = ConfigDict(frozen=True, allow_inf_nan=False)
    id: str
    start_seconds: float = Field(ge=0)
    end_seconds: float = Field(gt=0)
    text: str
    words: tuple[ArtifactWord, ...] | None = None
    translated_text: str | None = None

    @model_validator(mode='after')
    def ordered(self) -> ArtifactCue:
        if not self.text.strip() or self.start_seconds >= self.end_seconds:
            raise ArtifactError()
        for word in self.words or ():
            if not self.start_seconds <= word.start_seconds <= word.end_seconds <= self.end_seconds:
                raise ArtifactError()
        return self

    def segment(self, *, translated: bool = False) -> SubtitleSegment:
        return SubtitleSegment(self.id, self.start_seconds, self.end_seconds,
            self.translated_text or '' if translated else self.text,
            [SubtitleWord(word.text, word.start_seconds, word.end_seconds, word.confidence)
             for word in self.words] if self.words is not None else None)


class _Transcript(BaseModel):
    model_config = ConfigDict(frozen=True)
    segments: tuple[ArtifactCue, ...]


class ArtifactClip(BaseModel):
    model_config = ConfigDict(frozen=True, allow_inf_nan=False)
    video: ArtifactFile
    start: float = Field(ge=0)
    end: float = Field(gt=0)


class WorkstationArtifacts(BaseModel):
    model_config = ConfigDict(frozen=True, extra='forbid', allow_inf_nan=False)
    source_instance_id: UUID
    legacy_id: str = Field(min_length=1, max_length=128)
    root: Path
    media_root: Path | None = None
    duration: float = Field(gt=0)
    video: ArtifactFile
    transcript: ArtifactFile
    subtitles: ArtifactFile
    translation: ArtifactFile | None = None
    source_language: str = Field(pattern=r'^[a-z]{2,8}$')
    target_language: str | None = Field(default=None, pattern=r'^[a-z]{2,8}$')
    clips: tuple[ArtifactClip, ...] = ()
    supporting: tuple[ArtifactFile, ...] = ()

    @property
    def task_id(self) -> str:
        return uuid5(self.source_instance_id, self.legacy_id).hex

    @property
    def files(self) -> tuple[ArtifactFile, ...]:
        return (self.video, self.transcript, self.subtitles,
                *((self.translation,) if self.translation is not None else ()),
                *(clip.video for clip in self.clips), *self.supporting)

    @property
    def fingerprint(self) -> str:
        payload = self.model_dump(mode='json', exclude={'root', 'media_root'})
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()

    def checked(self, reference: ArtifactFile) -> Path:
        match reference.storage:
            case 'task':
                root = self.root
            case 'media':
                if self.media_root is None:
                    raise ArtifactError()
                root = self.media_root
            case unreachable:
                assert_never(unreachable)
        path = artifact_path(root, reference.path)
        if media.fingerprint(path) != reference.sha256:
            raise ArtifactError()
        return path


@dataclass(frozen=True, slots=True)
class ResolvedArtifacts:
    source: WorkstationArtifacts
    cues: tuple[ArtifactCue, ...]

    def verify(self) -> None:
        for reference in self.source.files:
            self.source.checked(reference)

    def signature(self) -> tuple:
        records = [self.source.fingerprint]
        for reference in self.source.files:
            path = self.source.checked(reference)
            info = path.stat()
            records.append((reference.path, info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns))
        return tuple(records)

    def document(self, style: SubtitleStyle) -> SubtitleDocument:
        from app.arctime.subtitle_document import Cue, SubtitleDocument
        from app.arctime.subtitle_encoding import video_metadata
        signature = self.signature()
        width, height, fps = video_metadata(self.source.checked(self.source.video))
        document = SubtitleDocument(source_fingerprint=self.source.fingerprint, revision=0, style=style,
            width=width, height=height, fps=fps, duration=self.source.duration,
            cues=[Cue(id=f'cue-{i + 1:06d}', start_seconds=cue.start_seconds, end_seconds=cue.end_seconds,
                      text=cue.text, translation=cue.translated_text or '') for i, cue in enumerate(self.cues)])
        if signature != self.signature():
            raise ArtifactError()
        document._signature = signature
        return document


def resolve_workstation(source: WorkstationArtifacts) -> ResolvedArtifacts:
    for reference in source.files:
        source.checked(reference)
    original = _Transcript.model_validate_json(source.checked(source.transcript).read_bytes()).segments
    if (len({cue.id for cue in original}) != len(original)
            or any(cue.end_seconds > source.duration for cue in original)
            or list(original) != sorted(original, key=lambda cue: (cue.start_seconds, cue.end_seconds))):
        raise ArtifactError()
    srt = media.read_subtitles(source.checked(source.subtitles))
    if len(srt) != len(original) or any(
        cue.text != row.text or abs(cue.start_seconds - row.start_seconds) > .001001
        or abs(cue.end_seconds - row.end_seconds) > .001001 for cue, row in zip(original, srt, strict=True)
    ):
        raise ArtifactError()
    cues = original
    if source.translation is not None:
        translated = _Transcript.model_validate_json(source.checked(source.translation).read_bytes()).segments
        if source.target_language is None or len(translated) != len(original):
            raise ArtifactError()
        for cue, row in zip(original, translated, strict=True):
            if (cue.model_dump(exclude={'translated_text'}) != row.model_dump(exclude={'translated_text'})
                    or not row.translated_text or not row.translated_text.strip()):
                raise ArtifactError()
        cues = translated
    for clip in source.clips:
        if not 0 <= clip.start < clip.end <= source.duration:
            raise ArtifactError()
    resolved = ResolvedArtifacts(source, cues)
    resolved.verify()
    return resolved
