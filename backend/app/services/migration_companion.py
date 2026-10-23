from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import UUID

from pydantic import BaseModel, ConfigDict, TypeAdapter

from app.arctime import media
from app.arctime.subtitle_document import base_document, load_document
from app.arctime.subtitle_style import SubtitleStyle
from app.services.migration_snapshot import SourceRoots, TaskMetadata, generation, inventory
from app.services.recording_results import _Checkpoint
from app.services.task_artifacts import ArtifactClip, ArtifactCue, ArtifactFile, WorkstationArtifacts, resolve_workstation
from app.services.task_import import discover_companion
from app.services.task_migration import Migrator
from app.services.task_operations import OperationConflict, canonical, digest
from app.services.unified_files import checked_path, file_sha256, immutable_bytes


class _Record(BaseModel):
    model_config = ConfigDict(extra='ignore')
    url: str = 'unavailable:legacy'
    started_at: float | None = None
    title: str | None = None
    tags: tuple[str, ...] = ()
    archived_at: datetime | None = None
    archived: bool = False
    created_at: datetime | None = None
    updated_at: datetime | None = None


def prepare_companion(migration: Migrator, source_id: UUID, roots: SourceRoots, *, legacy_id: str,
                      batch_id: str | None = None) -> str:
    item = next((item for item in discover_companion(roots.tasks, source_id) if item.identity.legacy_id == legacy_id), None)
    if item is None or item.eligibility != 'terminal':
        raise OperationConflict('only verified terminal Companion tasks can prepare; withdraw old queue eligibility first')
    directory = checked_path(roots.tasks, legacy_id)
    job = _Checkpoint.model_validate_json(checked_path(directory, 'job.json').read_bytes())
    before = inventory(roots)
    prefix = f'.unified/import-normalization/{source_id}/{generation(before)}/{legacy_id}'
    old_base = base_document(directory, SubtitleStyle())
    document = load_document(directory, old_base.style, base=old_base)
    raw = media.read_subtitles(checked_path(directory, job.subtitles))
    transcript_path = directory / 'transcript.json'
    cues = TypeAdapter(tuple[ArtifactCue, ...]).validate_python(json.loads(transcript_path.read_bytes())['segments']) if transcript_path.is_file() else tuple(
        ArtifactCue(id=str(index + 1), start_seconds=cue.start_seconds, end_seconds=cue.end_seconds, text=cue.text)
        for index, cue in enumerate(raw))
    if len(cues) != len(raw):
        raise OperationConflict('raw transcript and subtitles differ')
    normalized = canonical({'segments': [cue.model_dump(mode='json') for cue in cues]}).encode()
    transcript = prefix + '/transcript.json'
    immutable_bytes(checked_path(migration.root, transcript), normalized)
    reference = lambda name: ArtifactFile(storage='media', path=name, sha256=file_sha256(checked_path(directory, name)))
    translation = None
    if any(cue.translation for cue in old_base.cues):
        if len(cues) != len(old_base.cues):
            raise OperationConflict('legacy bilingual source count mismatch')
        pairs = [cue.model_copy(update={'translated_text': translated.translation}).model_dump(mode='json')
            for cue, translated in zip(cues, old_base.cues, strict=True)]
        body = canonical({'segments': pairs}).encode()
        name = prefix + '/translation.json'
        immutable_bytes(checked_path(migration.root, name), body)
        translation = ArtifactFile(path=name, sha256=digest(body))
    if len(job.completed_clips) > len(job.selection):
        raise OperationConflict('legacy clip selection count mismatch')
    context = WorkstationArtifacts(source_instance_id=source_id, legacy_id=legacy_id, root=migration.root,
        media_root=directory, duration=job.duration, video=reference(job.video),
        transcript=ArtifactFile(path=transcript, sha256=digest(normalized)), subtitles=reference(job.subtitles),
        translation=translation, source_language=job.asr.language,
        target_language={'ja': 'zh', 'zh': 'ja'}.get(job.asr.language) if translation else None,
        clips=tuple(ArtifactClip(video=reference(clip.video), start=bounds.start, end=bounds.end)
            for clip, bounds in zip(job.completed_clips, job.selection)),
        supporting=tuple(reference(clip.subtitles) for clip in job.completed_clips))
    resolved = resolve_workstation(context)
    base = resolved.document(document.style)
    if (base.width, base.height, base.fps, base.duration) != (document.width, document.height, document.fps, document.duration):
        raise OperationConflict('legacy source compatibility geometry mismatch')
    job_record = _Record.model_validate_json((directory / 'job.json').read_bytes())
    gui = directory / 'gui.json'
    record = _Record.model_validate_json(gui.read_bytes()) if gui.is_file() else job_record
    started = record.started_at if record.started_at is not None else job_record.started_at
    started = started if started is not None else (directory / 'job.json').stat().st_mtime
    created = record.created_at or job_record.created_at or datetime.fromtimestamp(started, timezone.utc)
    metadata = TaskMetadata(title=record.title, source_url=job_record.url, normalized_source_url=job_record.url,
        created_at=created, updated_at=record.updated_at or job_record.updated_at or created,
        archived_at=record.archived_at or (created if record.archived else None), tags=record.tags)
    if inventory(roots) != before:
        raise OperationConflict('Companion source changed during preparation')
    return migration.prepare(source_id, resolved, document.model_copy(update={'source_fingerprint': context.fingerprint}),
        metadata=metadata, history={'legacy_source_fingerprint': document.source_fingerprint,
            'legacy_base_fingerprint': old_base.source_fingerprint, 'legacy_document_sha256': digest(document.model_dump_json()),
            'legacy_metadata': record.model_dump(mode='json'),
            'archive_time_origin': 'saved archived_at' if record.archived_at else 'creation-time surrogate' if record.archived else None,
            'metadata_time_origin': 'saved started_at' if record.started_at is not None or job_record.started_at is not None else 'job manifest mtime'}, batch_id=batch_id)
