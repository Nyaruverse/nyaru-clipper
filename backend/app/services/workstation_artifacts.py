from __future__ import annotations

from pathlib import Path
import json
from collections.abc import Mapping
from uuid import UUID

from pydantic import BaseModel, ConfigDict
from sqlmodel import Session, select

from app.arctime import media
from app.models import Artifact, QueueEntry, Task, TaskExecutionControl, TaskJob
from app.services.source_catalog import configured_local_roots, resolve_local_reference_artifact
from app.services.task_artifacts import (
    ArtifactClip, ArtifactError, ArtifactFile, ResolvedArtifacts, WorkstationArtifacts,
    artifact_path, resolve_workstation,
)


class _Language(BaseModel):
    model_config = ConfigDict(frozen=True)
    language: str | None = None
    source_language: str | None = None
    target_language: str | None = None
    source_language_code: str | None = None
    target_language_code: str | None = None


class _Metadata(_Language):
    model_metadata: _Language = _Language()


class _ClipMetadata(BaseModel):
    model_config = ConfigDict(frozen=True)
    start_s: float
    end_s: float


def _language(value: str | None) -> str:
    normalized = {'zho_Hans': 'zh', 'zho_Hant': 'zh', 'jpn_Jpan': 'ja', 'eng_Latn': 'en'}.get(value or '', value)
    if normalized is None:
        raise ArtifactError('来源语种信息缺失，请先核对原产物')
    return normalized


def snapshot_workstation(session: Session, *, task_id: str, root: Path, source_instance_id: UUID,
                         path_aliases: Mapping[Path, Path] | None = None, media_root: Path | None = None) -> ResolvedArtifacts:
    task = session.get(Task, task_id)
    if task is None or task.status not in {'success', 'failed', 'cancelled'}:
        raise ArtifactError('只接受已停止处理的工作站结果')
    control = session.get(TaskExecutionControl, task_id)
    queued = session.get(QueueEntry, task_id)
    if (session.exec(select(TaskJob).where(TaskJob.task_id == task_id, TaskJob.status == 'running')).first()
            or (control is not None and control.active_process_group_id is not None)
            or (queued is not None and queued.state in {'queued', 'running'})):
        raise ArtifactError('工作站任务仍有执行资格或进程，请先停止并核对')
    records = session.exec(select(Artifact).where(Artifact.task_id == task_id).order_by(Artifact.id)).all()
    by_kind = {record.kind: record for record in records}

    def required(kind: str) -> Artifact:
        record = by_kind.get(kind)
        if record is None:
            raise ArtifactError()
        return record

    def reference(record: Artifact) -> ArtifactFile:
        path = Path(record.path)
        for old, new in sorted((path_aliases or {}).items(), key=lambda item: len(item[0].parts), reverse=True):
            if path.is_absolute() and path.is_relative_to(old):
                path = new / path.relative_to(old)
                break
        if not path.is_absolute():
            path = root / path
        try:
            name = str(path.relative_to(root))
        except ValueError:
            raise ArtifactError() from None
        return ArtifactFile(path=name, sha256=media.fingerprint(artifact_path(root, name)))

    video_row = required('source_video')
    video = reference(video_row)
    supporting: tuple[ArtifactFile, ...] = ()
    local_metadata = json.loads(video_row.metadata_json)
    local_reference = None if media_root is not None else resolve_local_reference_artifact(video_row.metadata_json)
    if media_root is not None:
        from app.services.source_catalog import LocalMediaSource
        if local_metadata.get('import_mode') == 'reference':
            relative = local_metadata.get('relative_path')
            if not isinstance(relative, str):
                raise ArtifactError('来源媒体引用缺失')
            local_reference = LocalMediaSource(root_id=local_metadata['root_id'], relative_path=relative,
                path=artifact_path(media_root, relative))
    if local_reference is not None:
        supporting = (video,)
        media_root = media_root or next(item.path for item in configured_local_roots() if item.id == local_reference.root_id)
        video = ArtifactFile(storage='media', path=local_reference.relative_path,
                             sha256=media.fingerprint(artifact_path(media_root, local_reference.relative_path)))
    else:
        media_root = None
    subtitles_row = required('subtitle_srt')
    metadata = _Metadata.model_validate_json(subtitles_row.metadata_json)
    original = reference(required('transcript_json'))
    transcript_meta = _Metadata.model_validate_json(artifact_path(root, original.path).read_bytes())
    source_language = _language(metadata.language or transcript_meta.model_metadata.language)
    translation_row = by_kind.get('bilingual_transcript_json')
    target_language = None
    translated = None
    if translation_row is not None:
        translated = reference(translation_row)
        languages = _Metadata.model_validate_json(artifact_path(root, translated.path).read_bytes()).model_metadata
        declared_source = languages.source_language or languages.source_language_code
        if _language(declared_source) != source_language:
            raise ArtifactError('译文语种方向与识别原文不一致')
        target_language = _language(languages.target_language or languages.target_language_code)
    clips = []
    exported = {record.path: record for record in records if record.kind == 'clip_export'}
    for record in exported.values():
        bounds = _ClipMetadata.model_validate_json(record.metadata_json)
        clips.append(ArtifactClip(video=reference(record), start=bounds.start_s, end=bounds.end_s))
    source = WorkstationArtifacts(source_instance_id=source_instance_id, legacy_id=task_id, root=root, media_root=media_root,
        duration=media.probe_video(artifact_path(media_root or root, video.path)), video=video, transcript=original,
        subtitles=reference(subtitles_row), translation=translated, source_language=source_language,
        target_language=target_language, clips=tuple(clips), supporting=supporting)
    return resolve_workstation(source)
