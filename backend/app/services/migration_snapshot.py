from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from uuid import UUID
from typing import assert_never

from pydantic import BaseModel, ConfigDict, JsonValue, model_validator

from app.arctime.subtitle_document import SubtitleDocument
from app.services.task_artifacts import WorkstationArtifacts, resolve_workstation
from app.services.task_operations import OperationConflict, canonical, digest
from app.services.unified_files import checked_path, file_sha256, publish_file
from app.services.public_runtime_settings import PublicRuntimeSettings


class MigrationModel(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)


class SourceRoots(MigrationModel):
    tasks: Path
    settings: Path
    database: Path | None = None
    media: Path | None = None
    database_name: str = 'tasks.sqlite3'
    public_runtime: PublicRuntimeSettings | None = None

    @model_validator(mode='after')
    def explicit_paths(self) -> SourceRoots:
        if any(not path.is_absolute() or '..' in path.parts for path in self.roots):
            raise OperationConflict('source roots must be explicit absolute paths')
        if Path(self.database_name).name != self.database_name or self.database_name in {'', '.', '..'}:
            raise OperationConflict('unsafe historical database filename')
        return self

    @property
    def roots(self) -> tuple[Path, ...]:
        paths = (self.tasks, self.settings, *((self.database,) if self.database else ()), *((self.media,) if self.media else ()))
        return tuple(sorted(set(paths)))


class SourceFile(MigrationModel):
    role: str
    path: str
    sha256: str
    size: int


class TaskMetadata(MigrationModel):
    title: str | None = None
    source_url: str
    normalized_source_url: str
    source_video_id: str | None = None
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None = None
    highlight_filtering_enabled: bool = True
    status: str = 'success'
    tags: tuple[str, ...] = ()


class Candidate(MigrationModel):
    source_id: UUID
    legacy_id: str
    generation: str
    files: tuple[SourceFile, ...]
    context: WorkstationArtifacts
    document: SubtitleDocument
    legacy_fingerprint: str
    metadata: TaskMetadata
    history: JsonValue
    public_runtime: PublicRuntimeSettings | None = None


def public_json(value: JsonValue) -> None:
    forbidden = {'api_key', 'access_token', 'refresh_token', 'id_token', 'password', 'cookie', 'authorization', 'client_secret'}
    match value:
        case dict():
            if any(key.casefold() in forbidden or key.casefold().endswith(('_api_key', '_token')) for key in value):
                raise OperationConflict('private credential fields cannot enter migration packages')
            for child in value.values():
                public_json(child)
        case list():
            for child in value:
                public_json(child)
        case str() | int() | float() | bool() | None:
            return
        case unreachable:
            assert_never(unreachable)


def inventory(roots: SourceRoots) -> tuple[SourceFile, ...]:
    files = []
    for role in ('tasks', 'settings', 'database', 'media'):
        root = getattr(roots, role)
        if root is None:
            continue
        checked_path(root, '.probe')
        if not root.is_dir():
            raise OperationConflict('source protection domain missing')
        for path in sorted(root.rglob('*')):
            checked_path(root, path.relative_to(root).as_posix())
            if path.is_dir():
                continue
            if not path.is_file() or path.stat().st_nlink != 1:
                raise OperationConflict('source contains unsupported file or hard link')
            if path.name in {'.lock', '.gui.lock'}:
                continue
            if path.name in {'config.json', 'credentials.json', '.chatgpt'} or '.chatgpt' in path.parts:
                raise OperationConflict('credential storage must be separated before migration')
            if path.suffix == '.json':
                public_json(json.loads(path.read_bytes()))
            files.append(SourceFile(role=role, path=path.relative_to(root).as_posix(),
                sha256=file_sha256(path), size=path.stat().st_size))
    return tuple(files)


def generation(files: tuple[SourceFile, ...], public_runtime: PublicRuntimeSettings | None = None) -> str:
    members = [entry.model_dump(mode='json') for entry in files]
    return digest(canonical(members if public_runtime is None else {'files': members, 'public_runtime': public_runtime.model_dump(mode='json')}))


def copy_context(destination: Path, context: WorkstationArtifacts, prefix: str) -> WorkstationArtifacts:
    mapping = {}
    for reference in context.files:
        source = context.checked(reference)
        name = f'{prefix}/{reference.storage}/{reference.path}'
        publish_file(source, checked_path(destination, name), reference.sha256, source.stat().st_size)
        mapping[reference.storage, reference.path] = reference.model_copy(update={'storage': 'task', 'path': name})
    result = context.model_copy(update={'root': destination, 'media_root': None,
        'video': mapping[context.video.storage, context.video.path],
        'transcript': mapping[context.transcript.storage, context.transcript.path],
        'subtitles': mapping[context.subtitles.storage, context.subtitles.path],
        'translation': mapping[context.translation.storage, context.translation.path] if context.translation else None,
        'clips': tuple(clip.model_copy(update={'video': mapping[clip.video.storage, clip.video.path]}) for clip in context.clips),
        'supporting': tuple(mapping[item.storage, item.path] for item in context.supporting)})
    resolve_workstation(result)
    return result


def read_candidate(root: Path, name: str, checksum: str) -> Candidate:
    path = checked_path(root, name)
    if file_sha256(path) != checksum:
        raise OperationConflict('migration candidate receipt hash mismatch')
    result = Candidate.model_validate_json(path.read_bytes())
    context = resolve_workstation(result.context)
    from app.arctime.subtitle_document import validate_source
    validate_source(result.document, context.document(result.document.style))
    if generation(result.files, result.public_runtime) != result.generation:
        raise OperationConflict('migration generation receipt mismatch')
    for entry in result.files:
        archive = checked_path(root, f'.unified/imports/{result.source_id}/{result.generation}/archive/{entry.role}/{entry.path}')
        if archive.stat().st_size != entry.size or file_sha256(archive) != entry.sha256:
            raise OperationConflict('migration archive member hash mismatch')
    return result


def archive_sources(root: Path, roots: SourceRoots, files: tuple[SourceFile, ...], prefix: str) -> None:
    for entry in files:
        source_root = getattr(roots, entry.role)
        source = checked_path(source_root, entry.path)
        publish_file(source, checked_path(root, f'{prefix}/{entry.role}/{entry.path}'), entry.sha256, entry.size)
    if inventory(roots) != files:
        raise OperationConflict('source changed during preparation; retain candidate and prepare a fresh generation')
