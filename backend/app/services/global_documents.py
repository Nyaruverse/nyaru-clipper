from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
from uuid import uuid4

from sqlalchemy import Engine
from sqlmodel import Session, select

from app.models_unified import GlobalHead, GlobalVersion
from app.services.task_operations import OperationConflict, digest
from app.services.unified_database import begin_unified_mutation
from app.services.unified_files import checked_path, immutable_bytes
from app.services.workstation_events import publish_event


class GlobalDocuments:
    def __init__(self, engine: Engine, root: Path, *, fault: Callable[[str], None] = lambda point: None) -> None:
        self.engine, self.root, self.fault = engine, root.absolute(), fault
        self._active: ContextVar[Session | None] = ContextVar('global_document_session', default=None)

    @contextmanager
    def mutation(self) -> Iterator[None]:
        if self._active.get() is not None:
            yield
            return
        with Session(self.engine) as session:
            begin_unified_mutation(session)
            token = self._active.set(session)
            try:
                yield
                self.fault('before_commit')
                session.commit()
                self.fault('committed')
            finally:
                self._active.reset(token)

    @contextmanager
    def _session(self) -> Iterator[Session]:
        active = self._active.get()
        if active is not None:
            yield active
        else:
            with Session(self.engine) as session:
                yield session

    def read(self, key: str) -> bytes | None:
        self._key(key)
        with self._session() as session:
            head = session.get(GlobalHead, key)
            if head is None or head.deleted:
                return None
            content = checked_path(self.root, head.body_path).read_bytes()
            if digest(content) != head.body_sha256:
                raise OperationConflict('registered global document hash mismatch')
            return content

    def keys(self, prefix: str) -> list[str]:
        self._key(prefix + '/probe')
        with self._session() as session:
            return sorted(row.key for row in session.exec(select(GlobalHead).where(GlobalHead.deleted == False)).all()
                if row.key.startswith(prefix + '/'))

    def write(self, key: str, content: bytes | None) -> None:
        self._key(key)
        session = self._active.get()
        if session is None:
            raise OperationConflict('global document writes require one shared transaction')
        current = session.get(GlobalHead, key)
        if content is None and (current is None or current.deleted):
            raise FileNotFoundError(key)
        revision = current.revision + 1 if current else 1
        checksum = digest(content or b'')
        relative = f'.unified/global/{digest(key)}/r{revision}-{checksum}'
        immutable_bytes(checked_path(self.root, relative), content or b'')
        self.fault('body')
        head = GlobalHead(key=key, revision=revision, body_sha256=checksum, body_path=relative, deleted=content is None)
        if current is not None:
            for field in ('revision', 'body_sha256', 'body_path', 'deleted'):
                setattr(current, field, getattr(head, field))
            head = current
        session.add_all([head, GlobalVersion(id=uuid4().hex, key=key, revision=revision,
            body_sha256=checksum, body_path=relative, deleted=content is None)])
        from app.services.migration_groups import record_new_write
        record_new_write(session)
        publish_event(session, 'settings.saved', digest(key), {'key': key, 'revision': revision, 'deleted': content is None})
        session.flush()

    def _key(self, key: str) -> None:
        if not key or key.startswith('.') or '\\' in key or any(part.startswith('.') for part in Path(key).parts):
            raise OperationConflict('invalid public settings key')
        checked_path(self.root, key)
