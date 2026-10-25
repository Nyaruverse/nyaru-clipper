from __future__ import annotations

import os
import signal
import subprocess
import time
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from pathlib import Path
from typing import IO
from uuid import uuid4

from sqlalchemy import Engine
from pydantic import BaseModel, ConfigDict, Field, JsonValue
from sqlmodel import Session, select

from app.models_unified import OperationProcess, UnifiedPublication
from app.services.runtime_guard import SlotBusy, execution_slot
from app.services.task_operations import OperationConflict, begin_step, claim_operation, complete_operation, require_token
from app.services.unified_files import checked_path, make_parents
from app.services.unified_database import begin_unified_mutation
from app.settings import Settings, execution_settings, get_settings


class ExecutionCancelled(RuntimeError):
    pass


class WorkflowFailure(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class ExternalOutcomeUnknown(WorkflowFailure):
    def __init__(self, *, response_registered: bool = False) -> None:
        super().__init__('local_response_delivery_interrupted' if response_registered else 'external_outcome_unknown_possible_repeat_charge')


class _Snapshot(BaseModel):
    model_config = ConfigDict(frozen=True)
    config: dict[str, JsonValue] = Field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Execution:
    engine: Engine
    root: Path
    operation_id: str
    token: str
    attempt: int
    task_id: str
    kind: str
    snapshot_json: str

    def check(self) -> None:
        with Session(self.engine) as session:
            operation = require_token(session, self.operation_id, self.token, cancelling=True)
            if operation.cancel_requested:
                raise ExecutionCancelled("operation cancellation requested")

    def staging(self, key: str) -> Path:
        from app.services.task_operations import digest
        path = checked_path(self.root, f".unified/staging/{self.operation_id}/{self.attempt}/{digest(key)}/.anchor")
        make_parents(path)
        return path.parent

    def publish(self, key: str, files: dict[str, Path], *, document_sha256: str | None = None,
                metadata: dict[str, JsonValue] | None = None) -> str:
        from app.services.task_publication import Publisher
        with Session(self.engine) as session:
            step = begin_step(session, self.operation_id, self.token, key, tuple(sorted(files)), metadata=metadata)
            step_id = step.id
            session.commit()
        return Publisher(self.engine, self.root).publish(self.operation_id, self.token, step_id, files,
            document_sha256=document_sha256)

    def fail_step(self, key: str, code: str, metadata: dict[str, JsonValue]) -> None:
        with Session(self.engine) as session:
            step = begin_step(session, self.operation_id, self.token, key, (), metadata=metadata)
            step.state, step.failure_code = 'failed', code
            session.add(step)
            from app.services.workstation_events import publish_event
            publish_event(session, 'operation.child-failed', self.operation_id,
                {'task_id': self.task_id, 'step_id': step.id, 'failure_code': code})
            session.commit()

    @contextmanager
    def process(self, command: list[str], *, cwd: Path | None = None, env: Mapping[str, str] | None = None,
                stdout: IO[str] | IO[bytes] | int = subprocess.PIPE, stderr: IO[str] | IO[bytes] | int = subprocess.PIPE) -> Iterator[subprocess.Popen[str]]:
        self.check()
        process = subprocess.Popen(command, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
            stdout=stdout, stderr=stderr, text=True, start_new_session=True)
        registration = OperationProcess(id=uuid4().hex, operation_id=self.operation_id,
            execution_token=self.token, process_group_id=process.pid)
        registration_id = registration.id
        try:
            with Session(self.engine) as session:
                begin_unified_mutation(session)
                require_token(session, self.operation_id, self.token)
                session.add(registration)
                session.commit()
            yield process
        finally:
            self._release_process(process)
            with Session(self.engine) as session:
                begin_unified_mutation(session)
                record = session.get(OperationProcess, registration_id)
                if record is not None:
                    record.released = True
                    session.add(record)
                    session.commit()
            for stream in (process.stdout, process.stderr):
                if stream is not None:
                    stream.close()

    @staticmethod
    def _release_process(process: subprocess.Popen[str]) -> None:
        try:
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except PermissionError:
                # macOS may deny signals to an exiting zombie; reap before checking the group again.
                process.wait(timeout=2)
                os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            process.wait()
            return
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=2)
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            return
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            try:
                os.killpg(process.pid, 0)
            except ProcessLookupError:
                return
            time.sleep(.02)
        raise OperationConflict("owned subprocess descendants have not exited")

    def wait(self, process: subprocess.Popen[str], *, timeout: float) -> tuple[str, str]:
        deadline = time.monotonic() + timeout
        while True:
            self.check()
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise subprocess.TimeoutExpired(process.args, timeout)
            try:
                stdout, stderr = process.communicate(timeout=min(.2, remaining))
                return stdout or "", stderr or ""
            except subprocess.TimeoutExpired:
                if time.monotonic() >= deadline:
                    raise

    def run_command(self, command: list[str], *, timeout: float = 7200, cwd: Path | None = None,
                    env: Mapping[str, str] | None = None, log: IO[str] | IO[bytes] | None = None) -> subprocess.CompletedProcess[str]:
        with self.process(command, cwd=cwd, env=env, stdout=log if log else subprocess.PIPE,
                          stderr=subprocess.STDOUT if log else subprocess.PIPE) as process:
            stdout, stderr = self.wait(process, timeout=timeout)
            return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)


current_execution: ContextVar[Execution | None] = ContextVar("unified_execution", default=None)


class Executor:
    def __init__(self, engine: Engine, root: Path, guard_root: Path) -> None:
        self.engine, self.root, self.guard_root = engine, root, guard_root

    def iteration(self, dispatch: Callable[[Execution], None]) -> str | None:
        try:
            with execution_slot(self.guard_root):
                return self._iteration(dispatch)
        except SlotBusy:
            return None

    def _iteration(self, dispatch: Callable[[Execution], None]) -> str | None:
        with Session(self.engine) as session:
            operation = claim_operation(session)
            if operation is None:
                session.commit()
                return None
            if operation.execution_token is None:
                raise OperationConflict("claimed operation has no token")
            execution = Execution(self.engine, self.root, operation.id, operation.execution_token, operation.attempt,
                operation.task_id, operation.kind, operation.snapshot_json)
            session.commit()
        context = current_execution.set(execution)
        settings_context = None
        state = "succeeded"
        failure_code = None
        try:
            values = get_settings().model_dump()
            captured = _Snapshot.model_validate_json(execution.snapshot_json).config
            values.update({key: value for key, value in captured.items() if key in Settings.model_fields and key != 'deepseek_api_key'})
            settings_context = execution_settings.set(Settings.model_validate(values))
            dispatch(execution)
            execution.check()
        except ExecutionCancelled:
            state, failure_code = "cancelled", "cancelled"
        except ExternalOutcomeUnknown as error:
            state, failure_code = 'interrupted', error.code
        except WorkflowFailure as error:
            state, failure_code = "failed", error.code
        except (OSError, ValueError, RuntimeError, subprocess.SubprocessError):
            state, failure_code = "failed", "workflow_failed"
        finally:
            if settings_context is not None:
                execution_settings.reset(settings_context)
            current_execution.reset(context)
        with Session(self.engine) as session:
            pending = session.exec(select(UnifiedPublication).where(
                UnifiedPublication.operation_id == execution.operation_id,
                UnifiedPublication.attempt == execution.attempt,
                UnifiedPublication.state.in_(['preparing', 'ready']),
            )).first() is not None
        if pending:
            from app.services.task_publication import Publisher
            Publisher(self.engine, self.root).reconcile(processes_released=lambda candidate:
                candidate.id == execution.operation_id and candidate.execution_token == execution.token)
            return execution.operation_id
        with Session(self.engine) as session:
            complete_operation(session, execution.operation_id, execution.token, state, failure_code=failure_code)
            session.commit()
        return execution.operation_id
