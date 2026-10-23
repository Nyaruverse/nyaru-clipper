from __future__ import annotations

from pathlib import Path
from uuid import UUID, uuid5

from sqlmodel import Session, select

from app.models import Task, TaskTag, TaskTagLink
from app.models_migration import MigrationBatch, MigrationGroup, MigrationMember
from app.models_unified import DocumentHead, DocumentVersion, TaskBinding
from app.services.migration_snapshot import Candidate
from app.services.task_operations import OperationConflict, digest
from app.services.unified_files import checked_path, immutable_bytes
from app.services.workstation_events import publish_event


def activate_candidate(session: Session, root: Path, candidate: Candidate, batch: MigrationBatch) -> None:
    task_id = candidate.context.task_id
    binding = session.get(TaskBinding, task_id)
    task = session.get(Task, task_id)
    if binding is None or task is None or binding.source_generation != candidate.generation or binding.root_group_id != batch.group_id:
        raise OperationConflict('migration binding changed before activation')
    if binding.state == 'activated':
        if binding.context_json != candidate.context.model_dump_json():
            raise OperationConflict('activated context differs; preserve current data')
        return
    head = session.get(DocumentHead, task_id)
    document = candidate.document
    if head is not None:
        prior = session.exec(select(MigrationMember).join(MigrationBatch).join(MigrationGroup).where(
            MigrationMember.task_id == task_id, MigrationMember.state == 'withdrawn',
            MigrationGroup.state == 'thawed', MigrationGroup.id != batch.group_id)).first()
        if prior is None:
            raise OperationConflict('existing editor document cannot be overwritten by migration')
        document = document.model_copy(update={'revision': max(document.revision, head.revision + 1)})
    body = document.model_dump_json().encode()
    checksum = digest(body)
    relative = f'{task_id}/.unified/documents/r{document.revision}-{checksum}.json'
    immutable_bytes(checked_path(root, relative), body)
    if head is None:
        head = DocumentHead(task_id=task_id, revision=document.revision, body_path=relative, body_sha256=checksum)
    else:
        head.revision, head.body_path, head.body_sha256 = document.revision, relative, checksum
    session.add_all([head, DocumentVersion(id=uuid5(UUID(task_id), str(document.revision)).hex, task_id=task_id,
            revision=document.revision, body_path=relative, body_sha256=checksum)])
    for name, value in candidate.metadata.model_dump(exclude={'tags'}).items():
        setattr(task, name, value)
    task.storage_bytes = sum(reference.size for reference in candidate.files if reference.role == 'tasks'
        and Path(reference.path).parts[0] == candidate.legacy_id)
    for label in candidate.metadata.tags:
        existing = session.exec(select(TaskTag).where(TaskTag.name == label)).first()
        if existing is None:
            existing = TaskTag(name=label)
            session.add(existing)
            session.flush()
        if session.get(TaskTagLink, (task_id, existing.name)) is None:
            session.add(TaskTagLink(task_id=task_id, tag_name=existing.name))
    binding.state, binding.context_json = 'activated', candidate.context.model_dump_json()
    session.add_all([task, binding])
    publish_event(session, 'task.created', task_id, {'task_id': task_id})
