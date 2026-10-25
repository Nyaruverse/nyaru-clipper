from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from pydantic import Field
from sqlmodel import Session, select

from app.arctime.topic_models import TopicModel, TopicSegmentStore
from app.models_unified import UnifiedOperation, UnifiedPublication
from app.services.task_operations import OperationConflict, digest
from app.services.task_publication import Publisher
from app.services.unified_files import checked_path

if TYPE_CHECKING:
    from app.arctime.unified_host import NativeHost


class TopicClipItem(TopicModel):
    index: int
    file: str | None = None
    state: str
    error: str | None = None
    url: str | None = None


class CombinedClip(TopicModel):
    file: str
    url: str


class TopicClipsView(TopicModel):
    state: str = "not_started"
    operation_id: str | None = None
    items: list[TopicClipItem] = Field(default_factory=list)
    combined: CombinedClip | None = None
    error: str | None = None


def latest(
    host: NativeHost, task_id: str, kind: Literal["analyze_topics", "export_topics"]
) -> UnifiedOperation | None:
    with Session(host.engine) as session:
        return session.exec(
            select(UnifiedOperation)
            .where(UnifiedOperation.task_id == task_id, UnifiedOperation.kind == kind)
            .order_by(UnifiedOperation.created_at.desc(), UnifiedOperation.id.desc())
        ).first()


def state(operation: UnifiedOperation) -> str:
    return {"succeeded": "completed", "paused": "queued"}.get(
        operation.state, operation.state
    )


def products(
    host: NativeHost, operation: UnifiedOperation
) -> dict[str, tuple[str, Path]]:
    with Session(host.engine) as session:
        rows = session.exec(
            select(UnifiedPublication)
            .where(
                UnifiedPublication.operation_id == operation.id,
                UnifiedPublication.state == "committed",
            )
            .order_by(UnifiedPublication.attempt, UnifiedPublication.id)
        ).all()
    result = {}
    for row in rows:
        receipt = Publisher(host.engine, host.root).registered(row.id)
        for output in receipt.outputs:
            result[output.role] = (row.id, checked_path(host.root, output.target))
    return result


def topic_snapshot(host: NativeHost, task_id: str) -> TopicSegmentStore:
    context = host.context(task_id)
    operation = latest(host, task_id, "analyze_topics")
    if operation is None:
        return TopicSegmentStore(state="not_started")
    files = products(host, operation)
    if "topics" not in files:
        configuration = json.loads(operation.snapshot_json)["config"]
        return TopicSegmentStore(
            state=state(operation),
            operation_id=operation.id,
            error=operation.failure_code,
            document_revision=configuration.get("topic_document_revision"),
            document_sha256=configuration.get("topic_document_sha256"),
        )
    store = TopicSegmentStore.model_validate_json(files["topics"][1].read_bytes())
    current = (
        host.documents.load(task_id, context.document(host.templates.load_defaults()))
        if context
        else None
    )
    stale = (
        current is None
        or store.document_revision != current.revision
        or store.document_sha256 != digest(current.model_dump_json())
    )
    return store.model_copy(
        update={
            "state": "stale"
            if stale and operation.state == "succeeded"
            else state(operation),
            "operation_id": operation.id,
            "error": operation.failure_code,
        }
    )


def topic_download(
    host: NativeHost, task_id: str, publication_id: str, role: str
) -> Path:
    with Session(host.engine) as session:
        row = session.get(UnifiedPublication, publication_id)
        operation = session.get(UnifiedOperation, row.operation_id) if row else None
        if (
            row is None
            or row.state != "committed"
            or operation is None
            or operation.task_id != task_id
            or operation.kind != "export_topics"
        ):
            raise OperationConflict("topic publication is not registered for this task")
    receipt = Publisher(host.engine, host.root).registered(publication_id)
    output = next((member for member in receipt.outputs if member.role == role), None)
    if (
        output is None
        or not (role == "combined" or role.startswith("clip-"))
        or Path(output.target).suffix != ".mp4"
    ):
        raise OperationConflict("topic product does not exist")
    return checked_path(host.root, output.target)


def clips_snapshot(host: NativeHost, task_id: str) -> TopicClipsView:
    host.context(task_id)
    operation = latest(host, task_id, "export_topics")
    if operation is None:
        return TopicClipsView()
    from app.arctime.topic_models import TopicClipOptions

    request = TopicClipOptions.model_validate(
        json.loads(operation.snapshot_json)["input"]["request"]
    )
    files = products(host, operation)

    def url(role: str) -> str:
        return (
            f"/companion-api/jobs/{task_id}/topic-clips/files/{files[role][0]}/{role}"
        )

    items = []
    for index in request.indices:
        role = f"clip-{index:03d}"
        items.append(
            TopicClipItem(
                index=index,
                file=f"{role}.mp4" if role in files else None,
                state="completed" if role in files else state(operation),
                error=operation.failure_code,
                url=url(role) if role in files else None,
            )
        )
    combined = (
        CombinedClip(file="combined.mp4", url=url("combined"))
        if "combined" in files
        else None
    )
    return TopicClipsView(
        state=state(operation),
        operation_id=operation.id,
        items=items,
        combined=combined,
        error=operation.failure_code,
    )
