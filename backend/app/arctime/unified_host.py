from __future__ import annotations

import os
import threading
from collections.abc import Iterator
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, JsonValue, model_validator
from sqlalchemy import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session, select

from app.api.schemas.operations import ExportOperation, LiveOperation, OperationInput, RecordingOperation, TranslateOperation
from app.arctime.companion_models import JobInput
from app.arctime.subtitle_inputs import ExportRequest
from app.arctime.subtitle_templates import TemplateStore
from app.models import Task
from app.models_unified import OperationAttempt, TaskBinding, UnifiedOperation, UnifiedRuntime
from app.services.global_documents import GlobalDocuments
from app.services.runtime_guard import execution_slot
from app.services.source_seal import Supervisor
from app.services.task_artifacts import ResolvedArtifacts, WorkstationArtifacts, resolve_workstation
from app.services.task_documents import Documents
from app.services.task_execution import Execution, Executor
from app.services.task_operations import (
    OperationConflict, canonical, digest, enqueue_operation, request_cancel, retry_operation, runtime, set_operation_waiting,
)
from app.services.task_publication import Publisher
from app.services.task_requests import freeze_request
from app.services.unified_database import begin_unified_mutation
from app.services.unified_files import checked_path

if TYPE_CHECKING:
    from app.arctime.companion_manager import JobManager
    from app.arctime.workflow import OwnedUpload


class _Roots(BaseModel):
    model_config = ConfigDict(frozen=True)
    task: Path
    settings: Path
    credential: Path
    guard: Path

    @model_validator(mode='after')
    def independent(self) -> _Roots:
        roots = [self.task, self.settings, self.credential, self.guard]
        for index, root in enumerate(roots):
            checked_path(root, '.probe')
            if any(root.is_relative_to(other) or other.is_relative_to(root) for other in roots[index + 1:]):
                raise OperationConflict('unified task/settings/credential/guard protection domains overlap')
        return self


class NativeHost:
    def __init__(self, engine: Engine, *, task_root: Path, settings_root: Path, credential_root: Path,
                 guard_root: Path, model: Path, threads: int = 4, supervisor: Supervisor | None = None) -> None:
        roles = _Roots(task=task_root.absolute(), settings=settings_root.absolute(),
            credential=credential_root.absolute(), guard=guard_root.absolute())
        if engine.url.database and any(Path(engine.url.database).absolute().is_relative_to(root) for root in
                (roles.task, roles.settings, roles.credential, roles.guard)):
            raise OperationConflict('unified database overlaps another protection domain')
        with Session(engine) as session:
            begin_unified_mutation(session)
            state = runtime(session)
            value = roles.model_dump_json()
            if state.root_roles_json not in {'{}', value}:
                raise OperationConflict('runtime root roles changed; use an explicit verified relocation')
            state.root_roles_json, self.instance_id = value, state.instance_id
            session.add(state)
            session.commit()
        self.engine, self.root = engine, roles.task
        self.settings_root, self.credential_root, self.guard_root = roles.settings, roles.credential, roles.guard
        self.model, self.threads = model, threads
        self.supervisor = supervisor
        self.failure_code: str | None = None
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.documents = Documents(engine, self.root)
        self.globals = GlobalDocuments(engine, self.settings_root)
        self.templates = TemplateStore(self.settings_root, documents=self.globals)
        self.executor = Executor(engine, self.root, self.guard_root)
        self.stopping = threading.Event()
        self.live_events: dict[str, threading.Event] = {}
        self.live_lock = threading.RLock()
        self.thread: threading.Thread | None = None

    def sessions(self) -> Iterator[Session]:
        with Session(self.engine) as session:
            yield session

    def ids(self) -> list[str]:
        with Session(self.engine) as session:
            return [row.task_id for row in session.exec(select(TaskBinding).where(TaskBinding.state == 'activated')).all()]

    def context(self, task_id: str) -> ResolvedArtifacts | None:
        with Session(self.engine) as session:
            binding = session.get(TaskBinding, task_id)
            if binding is None or binding.state != 'activated':
                raise HTTPException(404, '统一任务不存在')
            if binding.context_json == '{}':
                return None
            source = WorkstationArtifacts.model_validate_json(binding.context_json)
        if source.root != self.root or source.task_id != task_id:
            raise OperationConflict('registered task context does not match this host')
        return resolve_workstation(source)

    def configuration(self, payload: OperationInput) -> dict[str, JsonValue]:
        from app.services.unified_configuration import configuration_for
        return configuration_for(self, payload)

    def submit(self, manager: JobManager, request: JobInput | None, task_id: str | None, *, deferred: bool) -> str:
        if request is None:
            if task_id is None:
                raise HTTPException(404, '任务不存在')
            with Session(self.engine) as session:
                operation = session.exec(select(UnifiedOperation).where(UnifiedOperation.task_id == task_id,
                    UnifiedOperation.kind.in_(['process_recording', 'process_live'])).order_by(UnifiedOperation.created_at.desc())).first()
                if operation is None:
                    raise HTTPException(409, '此结果没有可恢复的处理操作')
                retry_operation(session, operation.id)
                session.commit()
            return task_id
        with Session(self.engine) as session:
            state = session.get(UnifiedRuntime, 1)
            if state is None:
                raise OperationConflict('unified runtime identity missing')
            instance_id = state.instance_id
        legacy_id = uuid4().hex
        from uuid import uuid5
        identifier = uuid5(UUID(instance_id), legacy_id).hex
        payload = LiveOperation(kind='process_live', task_id=identifier, request=request) if request.live else RecordingOperation(
            kind='process_recording', task_id=identifier, engine=request.engine, request=request)
        configuration = self.configuration(payload)
        if deferred:
            configuration['upload_pending'] = True
        with Session(self.engine) as session:
            begin_unified_mutation(session)
            state = runtime(session)
            if state.instance_id != instance_id:
                raise OperationConflict('runtime identity changed during admission')
            body = payload.model_dump(mode='json', exclude={'kind', 'task_id'})
            from app.services.task_operations import bind_task
            binding = bind_task(session, UUID(state.instance_id), legacy_id, digest(canonical(body)), origin='native')
            task = session.get(Task, binding.task_id)
            if task is None:
                raise OperationConflict('new native task registration missing')
            task.source_url, task.normalized_source_url = request.url, request.url
            session.add(task)
            operation = enqueue_operation(session, identifier, payload.kind, {'input': body, 'config': configuration})
            if deferred:
                set_operation_waiting(session, operation.id, 'paused')
            session.commit()
        if deferred:
            manager.active = {'id': identifier, 'state': 'uploading', 'message': '正在导入录像', 'model': configuration.get('llm_model'), 'error': None}
        return identifier

    def finish_upload(self, task_id: str, upload: OwnedUpload) -> None:
        from app.arctime.native_upload import finish_upload
        finish_upload(self, task_id, upload)

    def fail_upload(self, task_id: str) -> None:
        from app.arctime.native_upload import fail_upload
        fail_upload(self, task_id)

    def enqueue_export(self, task_id: str, request: ExportRequest) -> str:
        context = self.context(task_id)
        if context is None:
            raise HTTPException(409, '视频与字幕尚未就绪')
        if request.document is None:
            request = request.model_copy(update={'document': self.documents.load(task_id, context.document(request.style))})
        payload = ExportOperation(kind='export', task_id=task_id, request=request)
        body = freeze_request(self.root, task_id, payload.model_dump(mode='json', exclude={'kind', 'task_id'}))
        with Session(self.engine) as session:
            enqueue_operation(session, task_id, 'export', {'input': body, 'config': self.configuration(payload)})
            session.commit()
        return task_id

    def enqueue_translation(self, task_id: str, model: str) -> str:
        context = self.context(task_id)
        if context is None or context.source.source_language not in {'ja', 'zh'}:
            raise HTTPException(409, '中日翻译需要已识别语言的字幕')
        source = context.source.source_language
        payload = TranslateOperation(kind='translate', task_id=task_id, source_language=source,
            target_language='zh' if source == 'ja' else 'ja', provider='chatgpt' if model.startswith('chatgpt:') else 'deepseek',
            model=model.removeprefix('chatgpt:'))
        configuration = self.configuration(payload)
        with Session(self.engine) as session:
            enqueue_operation(session, task_id, 'translate', {'input': payload.model_dump(mode='json', exclude={'kind', 'task_id'}),
                'config': configuration})
            session.commit()
        return task_id

    def dispatch(self, execution: Execution) -> None:
        if self.supervisor is not None:
            self.supervisor.verify()
        from app.services.unified_dispatch import dispatch
        dispatch(self, execution)

    def start(self) -> None:
        if self.thread is not None and self.thread.is_alive():
            raise OperationConflict('unified executor already started')
        with Session(self.engine) as session:
            if session.exec(select(TaskBinding).where(TaskBinding.state == 'activated', TaskBinding.origin != 'native')).first():
                if self.supervisor is None:
                    raise OperationConflict('historical ownership requires its continuously holding Supervisor')
                from app.services.migration_ownership import verify_ownership
                verify_ownership(self.engine, self.supervisor)
                seal = self.supervisor.verify()
                if session.exec(select(TaskBinding).where(TaskBinding.state == 'activated', TaskBinding.origin != 'native',
                        TaskBinding.root_group_id != seal.root_group_id)).first():
                    raise OperationConflict('historical binding belongs to another Supervisor epoch')
        with execution_slot(self.guard_root):
            Publisher(self.engine, self.root).reconcile(processes_released=self._released)
        self.stopping.clear()
        self.thread = threading.Thread(target=self._loop, name='unified-executor', daemon=False)
        self.thread.start()

    def _released(self, operation: UnifiedOperation) -> bool:
        with Session(self.engine) as session:
            attempt = session.get(OperationAttempt, operation.execution_token)
            if attempt is None:
                return False
            try:
                os.kill(attempt.owner_pid, 0)
            except ProcessLookupError:
                return True
            return False

    def _loop(self) -> None:
        while not self.stopping.is_set():
            try:
                self.executor.iteration(self.dispatch)
            except (OSError, ValueError, RuntimeError, SQLAlchemyError):
                self.failure_code = 'executor_recovery_required'
                self.stopping.set()
                try:
                    with Session(self.engine) as session:
                        begin_unified_mutation(session)
                        state = runtime(session)
                        state.paused, state.recovering = True, True
                        state.revision += 1
                        from app.services.migration_groups import record_new_write
                        record_new_write(session)
                        session.add(state)
                        session.commit()
                except (OSError, ValueError, SQLAlchemyError):
                    self.failure_code = 'database_recovery_required'
                return
            self.stopping.wait(.2)

    def stop(self) -> None:
        self.stopping.set()
        with self.live_lock:
            for event in self.live_events.values():
                event.set()
        with Session(self.engine) as session:
            for operation in session.exec(select(UnifiedOperation).where(UnifiedOperation.state == 'running')).all():
                attempt = session.get(OperationAttempt, operation.execution_token)
                if attempt is not None and attempt.owner_pid == os.getpid() and operation.kind != 'process_live':
                    request_cancel(session, operation.id)
            session.commit()
        if self.thread is not None:
            self.thread.join()

    def stop_live(self, task_id: str) -> None:
        with self.live_lock:
            event = self.live_events.get(task_id)
            if event is None:
                raise HTTPException(409, '没有正在录制的直播任务')
            event.set()
