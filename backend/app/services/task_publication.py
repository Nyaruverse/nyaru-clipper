from __future__ import annotations

import json
import os
import zipfile
from collections.abc import Callable
from pathlib import Path

from sqlalchemy import Engine
from sqlmodel import Session, select

from app.arctime.workflow import exclusive_lock
from app.models_unified import OperationAttempt, OperationStep, UnifiedOperation, UnifiedPublication
from app.services.publication_receipts import OutputMember, OutputState, PreparedReceipt
from app.services.task_operations import OperationConflict, canonical, digest, require_token
from app.services.unified_files import checked_path, file_sha256, immutable_bytes, make_parents, publish_file, sync_directory
from app.services.workstation_events import publish_event
from app.services.unified_database import begin_unified_mutation


class Publisher:
    def __init__(self, engine: Engine, root: Path, *, fault: Callable[[str], None] = lambda point: None) -> None:
        self.engine, self.root, self.fault = engine, root.absolute(), fault
        self.lock = checked_path(self.root, ".unified/.publication.lock")
        make_parents(self.lock)

    def registered(self, publication_id: str) -> PreparedReceipt:
        with Session(self.engine) as session:
            publication = session.get(UnifiedPublication, publication_id)
            if publication is None or publication.state != "committed":
                raise OperationConflict("publication is not committed")
            content = self._receipt_path(publication_id).read_bytes()
            if digest(content) != publication.receipt_sha256 or content.decode() != publication.receipt_json:
                raise OperationConflict("registered publication receipt is corrupt")
            receipt = PreparedReceipt.model_validate_json(content)
            step = session.get(OperationStep, receipt.step_id)
            if (not self._proof(session, publication, receipt) or step is None or step.state != "succeeded"
                    or self._files(receipt)[0] != "all"):
                raise OperationConflict("registered publication proof or required files unavailable")
            return receipt

    def publish(self, operation_id: str, token: str, step_id: str, files: dict[str, Path], *,
                document_sha256: str | None = None) -> str:
        with exclusive_lock(self.lock):
            receipt = self._prepare(operation_id, token, step_id, files, document_sha256)
            self.fault("intent")
            immutable_bytes(self._receipt_path(receipt.publication_id), canonical(receipt.model_dump(mode="json")).encode())
            self.fault("prepared")
            self._ready(receipt)
            self.fault("ready")
            self._finish(receipt)
            return receipt.publication_id

    def _prepare(self, operation_id: str, token: str, step_id: str, files: dict[str, Path],
                 document_sha256: str | None) -> PreparedReceipt:
        with Session(self.engine) as session:
            durability = begin_unified_mutation(session)
            operation = require_token(session, operation_id, token)
            step = session.get(OperationStep, step_id)
            if (step is None or step.operation_id != operation_id or step.execution_token != token
                    or step.attempt != operation.attempt or set(files) != set(json.loads(step.required_roles_json))):
                raise OperationConflict("required child output set does not match")
            members = []
            for role, path in sorted(files.items()):
                relative = path.absolute().relative_to(self.root).as_posix()
                if not relative.startswith(f".unified/staging/{operation_id}/{operation.attempt}/"):
                    raise OperationConflict("staging belongs to another attempt")
                path = checked_path(self.root, relative)
                with path.open("rb") as stream:
                    os.fsync(stream.fileno())
                sync_directory(path.parent)
                if path.suffix == ".zip":
                    self._validate_archive(path)
                members.append({"role": role, "staging": relative, "size": path.stat().st_size, "sha256": file_sha256(path)})
            set_hash = digest(canonical(members))
            identity = digest(canonical([operation_id, operation.attempt, step_id, operation.snapshot_sha256, document_sha256, set_hash]))
            outputs = tuple(OutputMember(**member, target=f".unified/results/{identity}/{member['role']}{Path(member['staging']).suffix}") for member in members)
            snapshot = json.loads(operation.snapshot_json)
            receipt = PreparedReceipt(publication_id=identity, operation_id=operation_id, step_id=step_id,
                attempt=operation.attempt, execution_token=token, snapshot_sha256=operation.snapshot_sha256,
                input_sha256=digest(canonical(snapshot.get("input", {}))),
                configuration_sha256=digest(canonical(snapshot.get("config", {}))),
                child_snapshot_sha256=digest(step.metadata_json),
                sqlite_journal_mode=durability.journal_mode, sqlite_synchronous=durability.synchronous,
                document_sha256=document_sha256, outputs=outputs, set_sha256=set_hash)
            body = canonical(receipt.model_dump(mode="json"))
            existing = session.get(UnifiedPublication, identity)
            previous = session.exec(select(UnifiedPublication).where(UnifiedPublication.step_id == step_id)).first()
            if previous is not None and previous.id != identity:
                raise OperationConflict("child already has an immutable publication contract")
            if existing is None:
                session.add(UnifiedPublication(id=identity, operation_id=operation_id, attempt=operation.attempt,
                    execution_token=token, step_id=step_id, receipt_json=body, receipt_sha256=digest(body)))
            elif existing.receipt_json != body:
                raise OperationConflict("immutable publication identity conflict")
            session.commit()
            return receipt

    @staticmethod
    def _validate_archive(path: Path) -> None:
        with zipfile.ZipFile(path) as archive:
            names = archive.namelist()
            if len(set(names)) != len(names) or "manifest.json" not in names:
                raise OperationConflict("archive manifest or unique members missing")
            manifest = json.loads(archive.read("manifest.json"))
            checksums = manifest.get("sha256")
            if not isinstance(checksums, dict) or set(checksums) != set(names) - {"manifest.json"}:
                raise OperationConflict("archive required member set mismatch")
            for name, checksum in checksums.items():
                if Path(name).is_absolute() or ".." in Path(name).parts or digest(archive.read(name)) != checksum:
                    raise OperationConflict("archive required member checksum mismatch")

    def _receipt_path(self, publication_id: str) -> Path:
        return checked_path(self.root, f".unified/receipts/{publication_id}.json")

    def _ready(self, receipt: PreparedReceipt) -> None:
        with Session(self.engine) as session:
            begin_unified_mutation(session)
            require_token(session, receipt.operation_id, receipt.execution_token)
            publication = session.get(UnifiedPublication, receipt.publication_id)
            if publication is None:
                raise OperationConflict("publication intent missing")
            if digest(self._receipt_path(receipt.publication_id).read_bytes()) != publication.receipt_sha256:
                raise OperationConflict("receipt digest mismatch")
            if publication.state == "preparing":
                publication.state = "ready"
                session.add(publication)
            elif publication.state not in {"ready", "committed"}:
                raise OperationConflict("publication cannot become ready")
            session.commit()

    def _finish(self, receipt: PreparedReceipt) -> None:
        for member in receipt.outputs:
            with Session(self.engine) as session:
                begin_unified_mutation(session)
                require_token(session, receipt.operation_id, receipt.execution_token)
                publication = session.get(UnifiedPublication, receipt.publication_id)
                if publication is None or publication.state not in {"ready", "committed"}:
                    raise OperationConflict("publication is not ready")
                publish_file(checked_path(self.root, member.staging), checked_path(self.root, member.target), member.sha256, member.size)
                session.commit()
            self.fault(f"file:{member.role}")
        with Session(self.engine) as session:
            begin_unified_mutation(session)
            require_token(session, receipt.operation_id, receipt.execution_token)
            publication = session.get(UnifiedPublication, receipt.publication_id)
            step = session.get(OperationStep, receipt.step_id)
            if publication is None or step is None or self._files(receipt)[0] != "all":
                raise OperationConflict("complete required output set unavailable")
            if publication.state != "committed":
                publication.state, step.state = "committed", "succeeded"
                session.add_all([publication, step])
                publish_event(session, "publication.committed", publication.id, {
                    "publication_id": publication.id, "operation_id": receipt.operation_id, "step_id": receipt.step_id,
                })
            session.commit()
        self.fault("committed")

    def _files(self, receipt: PreparedReceipt) -> tuple[OutputState, bool]:
        present = 0
        staging = True
        for member in receipt.outputs:
            path = checked_path(self.root, member.target)
            if path.exists():
                if not path.is_file() or path.stat().st_size != member.size or file_sha256(path) != member.sha256:
                    return "bad", False
                present += 1
            else:
                source = checked_path(self.root, member.staging)
                staging = staging and source.is_file() and source.stat().st_size == member.size and file_sha256(source) == member.sha256
        return ("all" if present == len(receipt.outputs) else "partial" if present else "zero"), staging

    def reconcile(self, *, processes_released: Callable[[UnifiedOperation], bool]) -> list[str]:
        from app.services.publication_recovery import Reconciler
        return Reconciler(self).run(processes_released=processes_released)

    @staticmethod
    def _proof(session: Session, record: UnifiedPublication, receipt: PreparedReceipt) -> bool:
        attempt = session.get(OperationAttempt, record.execution_token)
        step = session.get(OperationStep, record.step_id)
        return (attempt is not None and attempt.operation_id == receipt.operation_id
            and attempt.attempt == receipt.attempt and attempt.snapshot_sha256 == receipt.snapshot_sha256
            and record.operation_id == receipt.operation_id and record.id == receipt.publication_id
            and record.step_id == receipt.step_id and record.attempt == receipt.attempt
            and record.execution_token == receipt.execution_token and step is not None
            and step.execution_token == receipt.execution_token and step.attempt == receipt.attempt
            and step.operation_id == receipt.operation_id and digest(step.metadata_json) == receipt.child_snapshot_sha256
            and (record.state != "committed" or step.state == "succeeded")
            and set(json.loads(step.required_roles_json)) == {member.role for member in receipt.outputs}
            and receipt.set_sha256 == digest(canonical([member.model_dump(exclude={"target"}) for member in receipt.outputs])))

