from __future__ import annotations

import json
from typing import TYPE_CHECKING

from sqlmodel import Session, select

from app.models_unified import UnifiedOperation
from app.services.task_operations import OperationConflict, _changed, canonical, digest, set_operation_waiting
from app.services.unified_database import begin_unified_mutation
from app.services.unified_files import checked_path, file_sha256, make_parents, sync_directory

if TYPE_CHECKING:
    from app.arctime.unified_host import NativeHost
    from app.arctime.workflow import OwnedUpload


def finish_upload(host: NativeHost, task_id: str, upload: OwnedUpload) -> None:
    target = checked_path(host.root, f'.unified/uploads/{task_id}.mp4')
    make_parents(target)
    upload.move_to(target, host.root)
    sync_directory(target.parent)
    checksum = file_sha256(target)
    with Session(host.engine) as session:
        begin_unified_mutation(session)
        operation = session.exec(select(UnifiedOperation).where(UnifiedOperation.task_id == task_id)).one()
        if operation.attempt != 0 or operation.state != 'paused':
            raise OperationConflict('upload operation eligibility changed')
        snapshot = json.loads(operation.snapshot_json)
        snapshot['config'].update(local_source=str(target), source_sha256=checksum, upload_pending=False)
        operation.snapshot_json = canonical(snapshot)
        operation.snapshot_sha256 = digest(operation.snapshot_json)
        session.add(operation)
        set_operation_waiting(session, operation.id, 'queued')
        session.commit()


def fail_upload(host: NativeHost, task_id: str) -> None:
    with Session(host.engine) as session:
        begin_unified_mutation(session)
        operation = session.exec(select(UnifiedOperation).where(UnifiedOperation.task_id == task_id)).one()
        if operation.attempt != 0 or operation.state != 'paused':
            raise OperationConflict('upload failure cannot overwrite an attempted operation')
        operation.state, operation.failure_code = 'failed', 'upload_incomplete_reselect_file'
        _changed(session, operation)
        session.commit()
