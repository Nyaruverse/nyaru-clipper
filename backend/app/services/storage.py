from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Final

from sqlmodel import Session, select
from sqlalchemy import event
from sqlalchemy.exc import OperationalError, SQLAlchemyError

from app.models import Artifact, CANONICAL_STAGES, PipelineRun, Task, TaskJob
from app.paths import ensure_data_dir, get_data_dir


STAGE_LOG_TAIL_BYTES: Final = 64 * 1024


def build_artifact_content_path(*, task_id: str, artifact_id: int, artifact_path: str | Path) -> str:
    filename = Path(artifact_path).name
    return f"/api/tasks/{task_id}/artifacts/{artifact_id}/content/{filename}"


def get_tasks_root() -> Path:
    return get_data_dir() / "tasks"


def get_task_root(task_id: str) -> Path:
    return get_tasks_root() / task_id


def ensure_task_dirs(task_id: str) -> dict[str, Path]:
    task_root = ensure_data_dir() / "tasks" / task_id
    task_dirs = {
        "raw": task_root / "raw",
        "work": task_root / "work",
        "exports": task_root / "exports",
        "reports": task_root / "reports",
        "logs": task_root / "logs",
    }
    for path in task_dirs.values():
        path.mkdir(parents=True, exist_ok=True)
    return task_dirs


def log_file_for_stage(task_id: str, stage_name: str) -> Path:
    task_dirs = ensure_task_dirs(task_id)
    return task_dirs["logs"] / f"{stage_name}.log"


def summarize_stage_log(task_id: str, stage_name: str) -> str | None:
    """Read the last nonblank complete line within 64 KiB; unavailable tails yield None."""
    log_path = get_task_root(task_id) / "logs" / f"{stage_name}.log"
    try:
        with log_path.open("rb", buffering=0) as stream:
            stream.seek(0, 2)
            offset = max(0, stream.tell() - STAGE_LOG_TAIL_BYTES)
            stream.seek(offset)
            tail = stream.read(STAGE_LOG_TAIL_BYTES)
    except OSError:
        return None
    if offset:
        # Discard a partial credential line whose redaction label may precede the window.
        tail = tail.partition(b"\n")[2]
    return next((line.strip() for line in reversed(tail.decode("utf-8", errors="replace").splitlines()) if line.strip()), None)


def resolve_task_artifact_path(task_id: str, artifact_path: str | Path) -> Path:
    candidate = Path(artifact_path).resolve()
    task_root = get_task_root(task_id).resolve()
    candidate.relative_to(task_root)
    return candidate


def directory_size(root: Path) -> int:
    """Count the entire managed tree, including unregistered recovery files."""
    if not root.is_dir():
        return 0
    return sum(path.stat().st_size for path in root.rglob("*") if path.is_file())


def refresh_task_storage(session: Session, *, task_id: str) -> None:
    """Refresh immediately unless this task has an explicit publication batch."""
    if ("artifact_batch", task_id) in session.info:
        return
    task = session.get(Task, task_id)
    if task is not None:
        task.storage_bytes = directory_size(get_task_root(task_id))
        session.add(task)


def reconcile_storage_after_cleanup(session: Session, *, task_id: str) -> None:
    """Recount committed publication cleanup without committing caller state.

    A failed recount leaves the conservative pre-cleanup total until recovery;
    it must not turn an already committed publication into a failed one.
    """
    from app.services.workstation_events import publish_task_updated
    from app.services.workstation_queue import begin_queue_mutation

    try:
        with Session(session.get_bind()) as accounting:
            begin_queue_mutation(accounting)
            refresh_task_storage(accounting, task_id=task_id)
            task = accounting.get(Task, task_id)
            if task is not None:
                publish_task_updated(accounting, task)
            accounting.commit()
    except (OSError, SQLAlchemyError):
        logging.getLogger(__name__).warning("storage_recount_deferred task_id=%s", task_id)


@contextmanager
def artifact_batch(session: Session, *, task_id: str) -> Iterator[None]:
    """Recount on successful exit; aborted callers must rollback and recount at recovery.

    Same-task nesting is rejected. Registration flushes/events remain transactional;
    callers must finish the batch before committing its publication.
    """
    key = ("artifact_batch", task_id)
    if key in session.info:
        raise RuntimeError(f"Artifact batch already active for {task_id}")
    session.info[key] = True
    try:
        yield
    finally:
        del session.info[key]
    # Do not issue SQL during exception unwinding, especially after a failed flush.
    refresh_task_storage(session, task_id=task_id)


def persist_artifact_metadata(
    session: Session,
    *,
    task_id: str,
    stage_name: str,
    kind: str,
    path: Path,
    metadata: dict[str, Any] | None = None,
) -> Artifact:
    artifact = Artifact(
        task_id=task_id,
        stage_name=stage_name,
        kind=kind,
        path=str(path),
        metadata_json=json.dumps(metadata or {}, sort_keys=True),
    )
    session.add(artifact)
    session.flush()
    refresh_task_storage(session, task_id=task_id)
    session.refresh(artifact)
    if artifact.id is None:
        raise RuntimeError("Persisted artifact is missing its ID")
    from app.services.workstation_events import publish_event

    publish_event(
        session,
        "artifact.ready",
        task_id,
        {
            "task_id": task_id,
            "artifact_id": artifact.id,
            "stage_name": stage_name,
            "kind": kind,
            "path": build_artifact_content_path(
                task_id=task_id,
                artifact_id=artifact.id,
                artifact_path=path,
            ),
        },
    )
    return artifact


def invalidate_translation_artifacts(session: Session, *, task_id: str) -> None:
    """Remove retry-invalid translation outputs while preserving reusable ASR and chunk caches."""
    artifacts = session.exec(
        select(Artifact).where(Artifact.task_id == task_id).where(Artifact.stage_name == "translation")
    ).all()
    for artifact in artifacts:
        try:
            artifact_path = resolve_task_artifact_path(task_id, artifact.path)
        except ValueError:
            artifact_path = None
        if artifact_path is not None:
            artifact_path.unlink(missing_ok=True)
        session.delete(artifact)

    work_dir = ensure_task_dirs(task_id)["work"]
    for filename in (
        "subtitles.zh-ja.preproofread.json",
        "subtitles.zh-ja.preproofread.srt",
        "proofread-audit.json",
        "subtitles.zh-ja.json",
        "subtitles.zh-ja.srt",
    ):
        (work_dir / filename).unlink(missing_ok=True)

    refresh_task_storage(session, task_id=task_id)


def cleanup_pending_retry(session: Session, run: PipelineRun) -> None:
    job = session.exec(select(TaskJob).where(TaskJob.task_id == run.task_id)).first()
    if (
        run.trigger == "retry"
        and run.status == "pending"
        and job is not None
        and job.status == "pending"
        and CANONICAL_STAGES.index(job.stage_name) <= CANONICAL_STAGES.index("translation")
    ):
        invalidate_translation_artifacts(session, task_id=run.task_id)


def schedule_retry_cleanup(session: Session, run_id: str) -> None:
    if "retry_cleanup_runs" not in session.info:
        session.info["retry_cleanup_runs"] = []
        event.listen(session, "after_commit", _cleanup_committed_retries)
        event.listen(session, "after_soft_rollback", _discard_rolled_back_retries)
    session.info["retry_cleanup_runs"].append(run_id)


def _discard_rolled_back_retries(session: Session, transaction) -> None:
    if transaction.parent is None:
        session.info["retry_cleanup_runs"].clear()


def _cleanup_committed_retries(session: Session) -> None:
    if session.in_nested_transaction():
        return
    from app.services.workstation_queue import begin_queue_mutation

    run_ids = list(session.info["retry_cleanup_runs"])
    session.info["retry_cleanup_runs"].clear()
    for run_id in run_ids:
        try:
            with Session(session.get_bind()) as cleanup:
                begin_queue_mutation(cleanup)
                run = cleanup.get(PipelineRun, run_id)
                if run is not None:
                    cleanup_pending_retry(cleanup, run)
                cleanup.commit()
        except (OSError, OperationalError):
            logging.getLogger(__name__).warning("retry_cleanup_deferred run_id=%s", run_id)
