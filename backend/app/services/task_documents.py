from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import UUID, uuid5

from sqlalchemy import Engine
from sqlmodel import Session, select

from app.arctime.subtitle_document import SubtitleDocument, validate_source
from app.models_unified import DocumentHead, DocumentVersion, TaskBinding, UnifiedOperation
from app.services.task_operations import OperationConflict, digest
from app.services.unified_files import checked_path, immutable_bytes
from app.services.workstation_events import publish_event
from app.services.unified_database import begin_unified_mutation

if TYPE_CHECKING:
    from app.services.task_artifacts import WorkstationArtifacts
    from app.services.task_execution import Execution


class DocumentConflict(ValueError):
    pass


class Documents:
    def __init__(self, engine: Engine, root: Path, *, fault: Callable[[str], None] = lambda point: None) -> None:
        self.engine, self.root, self.fault = engine, root.absolute(), fault

    def is_activated(self, task_id: str) -> bool:
        with Session(self.engine) as session:
            binding = session.get(TaskBinding, task_id)
            return binding is not None and binding.state == "activated"

    def context_registered(self, context: WorkstationArtifacts) -> bool:
        if context.root.absolute() != self.root or any(
            reference.storage == 'task' and not reference.path.startswith('.unified/results/') for reference in context.files
        ):
            return False
        with Session(self.engine) as session:
            binding = session.get(TaskBinding, context.task_id)
            return binding is not None and binding.state == 'activated' and binding.context_json == context.model_dump_json()

    def load(self, task_id: str, base: SubtitleDocument, *, source: bool = False) -> SubtitleDocument:
        with Session(self.engine) as session:
            head = session.get(DocumentHead, task_id)
            if head is None:
                return base
            path = checked_path(self.root, head.body_path)
            content = path.read_bytes()
            if digest(content) != head.body_sha256:
                raise DocumentConflict("registered subtitle document hash mismatch")
            document = SubtitleDocument.model_validate_json(content)
            if document.revision != head.revision:
                raise DocumentConflict("registered subtitle revision mismatch")
            validate_source(document, base)
            return base.model_copy(update={"revision": head.revision}) if source else document

    def save(self, task_id: str, document: SubtitleDocument, *, base: SubtitleDocument,
             execution: Execution | None = None) -> SubtitleDocument:
        validate_source(document, base)
        saved = document.model_copy(update={"revision": document.revision + 1, "source_fingerprint": base.source_fingerprint})
        body = saved.model_dump_json().encode()
        checksum = digest(body)
        relative = f"{task_id}/.unified/documents/r{saved.revision}-{checksum}.json"
        immutable_bytes(checked_path(self.root, relative), body)
        self.fault("body")
        with Session(self.engine) as session:
            begin_unified_mutation(session)
            binding = session.get(TaskBinding, task_id)
            if binding is None or binding.state != "activated":
                raise OperationConflict("document task is not activated")
            active = session.exec(select(UnifiedOperation).where(UnifiedOperation.task_id == task_id,
                UnifiedOperation.state == 'running', UnifiedOperation.kind.in_(['process_recording', 'process_live', 'translate']))).first()
            if execution is not None:
                from app.services.task_operations import require_token
                owned = require_token(session, execution.operation_id, execution.token)
                if owned.task_id != task_id or owned.kind != 'translate' or active is None or active.id != owned.id:
                    raise DocumentConflict('document operation ownership changed')
            elif active is not None:
                raise DocumentConflict('任务仍在处理，请保留草稿并在处理停止后保存')
            head = session.get(DocumentHead, task_id)
            if execution is not None and head is not None and (head.revision, head.body_sha256) == (saved.revision, checksum):
                return saved
            if document.revision != (head.revision if head else 0):
                raise DocumentConflict("字幕版本冲突；请保留当前编辑并重新载入")
            if head is None:
                head = DocumentHead(task_id=task_id, revision=saved.revision, body_sha256=checksum, body_path=relative)
            else:
                head.revision, head.body_sha256, head.body_path = saved.revision, checksum, relative
            session.add_all([head, DocumentVersion(id=uuid5(UUID(task_id), str(saved.revision)).hex,
                task_id=task_id, revision=saved.revision, body_sha256=checksum, body_path=relative)])
            from app.services.migration_groups import record_new_write
            record_new_write(session)
            publish_event(session, "document.saved", task_id, {"task_id": task_id, "revision": saved.revision})
            self.fault("before_commit")
            session.commit()
        self.fault("committed")
        return saved
