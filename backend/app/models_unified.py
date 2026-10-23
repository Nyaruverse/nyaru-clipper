from __future__ import annotations

from datetime import datetime

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel


def _now() -> datetime:
    from app.models import utc_now
    return utc_now()


class UnifiedRuntime(SQLModel, table=True):
    id: int = Field(default=1, primary_key=True)
    instance_id: str
    paused: bool = True
    recovering: bool = False
    revision: int = 0
    root_roles_json: str = "{}"


class TaskBinding(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("source_instance_id", "legacy_id"),)
    task_id: str = Field(primary_key=True, foreign_key="task.id")
    source_instance_id: str
    legacy_id: str
    source_generation: str
    origin: str
    state: str = "prepared"
    root_group_id: str | None = None
    context_json: str = "{}"


class UnifiedOperation(SQLModel, table=True):
    id: str = Field(primary_key=True)
    task_id: str = Field(index=True, foreign_key="task.id")
    kind: str
    state: str = Field(default="queued", index=True)
    attempt: int = 0
    execution_token: str | None = None
    priority: int = 0
    position: int = 0
    snapshot_json: str
    snapshot_sha256: str
    cancel_requested: bool = False
    active_process_group_id: int | None = None
    failure_code: str | None = None
    external_retry_acknowledged: bool = False
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


class OperationAttempt(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("operation_id", "attempt"),)
    execution_token: str = Field(primary_key=True)
    operation_id: str = Field(index=True, foreign_key="unifiedoperation.id")
    attempt: int
    snapshot_sha256: str
    state: str = "running"
    owner_pid: int
    external_retry_acknowledged: bool = False
    created_at: datetime = Field(default_factory=_now)
    finished_at: datetime | None = None


class OperationProcess(SQLModel, table=True):
    id: str = Field(primary_key=True)
    operation_id: str = Field(index=True, foreign_key="unifiedoperation.id")
    execution_token: str = Field(index=True)
    process_group_id: int
    released: bool = False


class OperationStep(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("operation_id", "attempt", "step_key"),)
    id: str = Field(primary_key=True)
    operation_id: str = Field(index=True, foreign_key="unifiedoperation.id")
    attempt: int
    execution_token: str
    step_key: str
    state: str = "running"
    required_roles_json: str
    metadata_json: str = "{}"
    failure_code: str | None = None
    reused_publication_id: str | None = None


class UnifiedPublication(SQLModel, table=True):
    id: str = Field(primary_key=True)
    operation_id: str = Field(index=True, foreign_key="unifiedoperation.id")
    attempt: int
    execution_token: str
    step_id: str = Field(foreign_key="operationstep.id")
    state: str = "preparing"
    receipt_json: str
    receipt_sha256: str
    failure_code: str | None = None


class DocumentHead(SQLModel, table=True):
    task_id: str = Field(primary_key=True, foreign_key="task.id")
    revision: int
    body_sha256: str
    body_path: str


class DocumentVersion(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("task_id", "revision"),)
    id: str = Field(primary_key=True)
    task_id: str = Field(index=True, foreign_key="task.id")
    revision: int
    body_sha256: str
    body_path: str
    created_at: datetime = Field(default_factory=_now)


class GlobalHead(SQLModel, table=True):
    key: str = Field(primary_key=True)
    revision: int
    body_sha256: str
    body_path: str
    deleted: bool = False


class GlobalVersion(SQLModel, table=True):
    __table_args__ = (UniqueConstraint('key', 'revision'),)
    id: str = Field(primary_key=True)
    key: str = Field(index=True)
    revision: int
    body_sha256: str
    body_path: str
    deleted: bool = False
    created_at: datetime = Field(default_factory=_now)
