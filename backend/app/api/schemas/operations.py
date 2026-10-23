from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.arctime.companion_models import JobInput
from app.arctime.subtitle_inputs import ExportRequest
from app.services.task_operations import OperationKind


class OperationInputError(ValueError):
    pass


class OperationSchema(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class RecordingOperation(OperationSchema):
    kind: Literal["process_recording"]
    task_id: str = Field(pattern=r"^[0-9a-f]{32}$")
    engine: Literal["whisper.cpp", "whisperx"]
    request: JobInput

    @model_validator(mode="after")
    def recording_only(self) -> RecordingOperation:
        if self.request.live:
            raise OperationInputError("live recording requires process_live")
        return self


class LiveOperation(OperationSchema):
    kind: Literal["process_live"]
    task_id: str = Field(pattern=r"^[0-9a-f]{32}$")
    request: JobInput

    @model_validator(mode="after")
    def live_only(self) -> LiveOperation:
        if not self.request.live:
            raise OperationInputError("process_live requires a live request")
        return self


class TranslateOperation(OperationSchema):
    kind: Literal["translate"]
    task_id: str = Field(pattern=r"^[0-9a-f]{32}$")
    source_language: Literal["ja", "zh"]
    target_language: Literal["ja", "zh"]
    provider: Literal["deepseek", "chatgpt", "hf"]
    model: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9:._/-]+$")
    document_revision: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def distinct_languages(self) -> TranslateOperation:
        if self.source_language == self.target_language:
            raise OperationInputError("translation languages must differ")
        return self


class ExportOperation(OperationSchema):
    kind: Literal["export"]
    task_id: str = Field(pattern=r"^[0-9a-f]{32}$")
    request: ExportRequest


OperationInput = Annotated[RecordingOperation | LiveOperation | TranslateOperation | ExportOperation, Field(discriminator="kind")]


class OperationView(OperationSchema):
    model_config = ConfigDict(extra="ignore", frozen=True, from_attributes=True)
    id: str
    task_id: str
    kind: OperationKind
    state: Literal["queued", "paused", "running", "succeeded", "failed", "interrupted", "cancelled"]
    attempt: int
    priority: int
    position: int
    cancel_requested: bool
    failure_code: str | None


class OperationsSnapshot(OperationSchema):
    revision: int
    paused: bool
    recovering: bool
    operations: tuple[OperationView, ...]


class ReorderOperations(OperationSchema):
    expected_revision: int = Field(ge=0)
    ordered_ids: list[str] = Field(max_length=10000)


class QueueAdmissions(OperationSchema):
    expected_revision: int = Field(ge=0)
    paused: bool


class WaitingOperation(OperationSchema):
    state: Literal["queued", "paused"]
    priority: int | None = Field(default=None, ge=-100, le=100)


class RetryOperation(OperationSchema):
    acknowledge_external_outcome: bool = False
