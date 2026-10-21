from __future__ import annotations

import fcntl
import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Literal
from uuid import uuid4

from sqlmodel import Session, select

from app.models import Artifact, ClipCandidate, PipelineRun, QueueEntry, StageRun, Task, TaskExecutionControl, TaskJob, TaskStage, utc_now
from app.services.export_encoding import ExportEncodingConfig, ExportInvocation, execute_video_export
from app.repositories.tasks import get_task_record
from app.services.workstation_events import publish_stage_updated, publish_task_updated
from app.services.workstation_queue import begin_queue_mutation
from app.services.workstation_runs import sync_stage_run
from app.services.source_catalog import resolve_local_reference_artifact
from app.services.storage import ensure_task_dirs, log_file_for_stage, persist_artifact_metadata, refresh_task_storage, reconcile_storage_after_cleanup
from app.settings import get_settings


@dataclass(slots=True)
class ClipExportResult:
    task_id: str
    candidate_id: int
    start_s: float
    end_s: float
    output_path: Path
    artifact_id: int


class ClipExportFailure(RuntimeError):
    def __init__(self, *, code: str, message: str):
        super().__init__(message)
        self.code = code


def export_confirmed_clip(
    session: Session,
    task_id: str,
    *,
    candidate_id: int,
    start_s: float | None = None,
    end_s: float | None = None,
) -> ClipExportResult:
    begin_queue_mutation(session)
    record = get_task_record(session, task_id)
    if record is None:
        raise ValueError(f"Unknown task_id: {task_id}")
    original_state = _manual_export_state(session, task_id)

    candidate = session.exec(
        select(ClipCandidate).where(ClipCandidate.task_id == task_id).where(ClipCandidate.id == candidate_id)
    ).first()
    if candidate is None:
        raise LookupError(f"Clip candidate {candidate_id} not found for task {task_id}")

    source_video_path = _resolve_source_video_path(task_id, record)
    source_reference = _source_video_reference(record, source_video_path)
    source_duration_s = _resolve_source_duration_seconds(task_id, record)
    clip_start_s = float(candidate.start_seconds if start_s is None else start_s)
    clip_end_s = float(candidate.end_seconds if end_s is None else end_s)
    _validate_range(clip_start_s, clip_end_s, source_duration_s)

    task_dirs = ensure_task_dirs(task_id)
    output_path = task_dirs["exports"] / _build_export_filename(clip_start_s, clip_end_s)
    log_path = log_file_for_stage(task_id, "export")
    settings = get_settings()
    with (output_path.parent / ".manual-export.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ClipExportFailure(code="export_busy", message="This clip is already being exported.") from exc
        with tempfile.NamedTemporaryFile(
            dir=output_path.parent, prefix=f".{output_path.stem}-", suffix=".partial.mp4", delete=False
        ) as temporary:
            temporary_path = Path(temporary.name)
        backup_path = temporary_path.with_suffix(".previous")
        published = committed = False
        try:
            session.rollback()
            temporary_path.unlink()
            execution = execute_video_export(
                ExportInvocation(
                    source_path=source_video_path,
                    output_path=temporary_path,
                    start_s=clip_start_s,
                    end_s=clip_end_s,
                    source_reference=source_reference,
                ),
                ExportEncodingConfig(
                    ffmpeg_binary=settings.ffmpeg_binary,
                    export_video_backend=settings.export_video_backend,
                    windows_ffmpeg_binary=settings.windows_ffmpeg_binary,
                ),
                log_path,
            )
            ffmpeg_result = execution.completed_process
            begin_queue_mutation(session)
            if _manual_export_state(session, task_id) != original_state:
                raise ClipExportFailure(code="export_state_changed", message="Task changed while this clip was being exported. Retry the export.")
            if ffmpeg_result.returncode != 0 or not temporary_path.is_file() or temporary_path.stat().st_size == 0:
                _record_manual_export(session, task_id, status="failed", summary="ffmpeg_failed")
                session.commit()
                raise ClipExportFailure(
                    code="ffmpeg_failed",
                    message=_safe_source_error(
                        ffmpeg_result.stderr or "ffmpeg failed during clip export", source_video_path, source_reference
                    ),
                )
            if output_path.exists():
                os.link(output_path, backup_path)
            temporary_path.replace(output_path)
            published = True
            artifact = _persist_export_artifact(
                session,
                task_id=task_id,
                candidate_id=candidate_id,
                output_path=output_path,
                start_s=clip_start_s,
                end_s=clip_end_s,
                source_duration_s=source_duration_s,
                source_video_reference=source_reference,
                export_backend=execution.export_backend,
                video_encoder=execution.video_encoder,
            )
            candidate.status = "exported"
            session.add(candidate)
            _record_manual_export(
                session,
                task_id,
                status="success",
                summary=f"Exported clip {output_path.name}",
            )
            session.commit()
            committed = True
            return ClipExportResult(
                task_id=task_id,
                candidate_id=candidate_id,
                start_s=clip_start_s,
                end_s=clip_end_s,
                output_path=output_path,
                artifact_id=int(artifact.id),
            )
        finally:
            if published and not committed:
                session.rollback()
                if backup_path.exists():
                    backup_path.replace(output_path)
                else:
                    output_path.unlink(missing_ok=True)
            temporary_path.unlink(missing_ok=True)
            removed_backup = backup_path.exists()
            backup_path.unlink(missing_ok=True)
            if committed and removed_backup:
                reconcile_storage_after_cleanup(session, task_id=task_id)


def _manual_export_state(session: Session, task_id: str) -> tuple[str, ...]:
    """Capture exact task-local ownership state under the queue writer lock."""
    task = session.get(Task, task_id)
    jobs = session.exec(select(TaskJob).where(TaskJob.task_id == task_id).order_by(TaskJob.id)).all()
    stages = session.exec(select(TaskStage).where(TaskStage.task_id == task_id).order_by(TaskStage.id)).all()
    control = session.get(TaskExecutionControl, task_id)
    queue = session.get(QueueEntry, task_id)
    runs = session.exec(select(PipelineRun).where(PipelineRun.task_id == task_id).order_by(PipelineRun.id)).all()
    run_stages = session.exec(select(StageRun).join(PipelineRun, StageRun.run_id == PipelineRun.id).where(PipelineRun.task_id == task_id).order_by(StageRun.id)).all()
    candidates = session.exec(select(ClipCandidate).where(ClipCandidate.task_id == task_id).order_by(ClipCandidate.id)).all()
    if (
        task is None or task.status in {"running", "cancelled"}
        or any(job.status in {"running", "cancelled"} for job in jobs)
        or any(stage.status in {"running", "cancelled"} for stage in stages)
        or any(run.status == "running" for run in runs)
        or queue is not None and queue.state == "running"
        or control is not None and (control.execution_token is not None or control.cancel_requested or control.force_kill_requested or control.active_process_group_id is not None)
    ):
        raise ClipExportFailure(code="export_busy", message="Task is active or cancelled; manual export is unavailable.")
    queue_state = json.dumps(queue.model_dump(mode="json", exclude={"position", "updated_at"}), sort_keys=True) if queue else "null"
    return (queue_state, *(json.dumps(row.model_dump(mode="json"), sort_keys=True) for row in [task, *jobs, *stages, control, *runs, *run_stages, *candidates] if row is not None))


def _record_manual_export(session: Session, task_id: str, *, status: Literal["success", "failed"], summary: str) -> None:
    """Record the manual operation without rewriting completed pipeline history."""
    task = session.get(Task, task_id)
    assert task is not None
    stages = session.exec(select(TaskStage).where(TaskStage.task_id == task_id)).all()
    stage = next(stage for stage in stages if stage.name == "export")
    job = session.exec(select(TaskJob).where(TaskJob.task_id == task_id)).first()
    previous_manual = session.exec(
        select(PipelineRun).where(PipelineRun.task_id == task_id).where(PipelineRun.trigger == "manual_export")
        .order_by(PipelineRun.created_at.desc(), PipelineRun.id.desc())
    ).first()
    recovering_manual_failure = (
        stage.status == "failed" and job is not None and job.status == "failed" and job.stage_name == "export"
        and previous_manual is not None and previous_manual.status == "failed"
        and previous_manual.finished_at is not None
        and job.updated_at == job.finished_at == previous_manual.finished_at
    )
    now = utc_now()
    stage.status = status
    stage.summary = summary
    stage.failure_code = None
    stage.updated_at = stage.finished_at = now
    session.add(stage)
    run = PipelineRun(id=f"run-{uuid4().hex}", task_id=task_id, status=status, trigger="manual_export", created_at=now, started_at=now, finished_at=now)
    session.add(run)
    session.flush()
    sync_stage_run(session, run.id, stage)
    publish_stage_updated(session, stage)
    # Pending scheduling and unrelated failures retain ownership of the task/job status.
    others_complete = all(item.status in {"success", "skipped"} for item in stages if item.name != "export")
    if others_complete and (task.status == "success" or task.status == "failed" and recovering_manual_failure) and (job is None or job.status == "success" or job.status == "failed" and job.stage_name == "export"):
        task.status = status
        task.updated_at = now
        session.add(task)
        if job is not None:
            job.status = status
            job.stage_name = "report" if status == "success" else "export"
            job.updated_at = job.finished_at = now
            session.add(job)
        publish_task_updated(session, task)


def _resolve_source_video_path(task_id: str, record) -> Path:
    task_dirs = ensure_task_dirs(task_id)
    raw_dir = task_dirs["raw"]
    preferred = raw_dir / "source.mp4"
    if preferred.exists():
        return preferred

    for artifact in reversed(record.artifacts):
        if artifact.stage_name == "ingest" and artifact.kind == "source_video":
            local_source = resolve_local_reference_artifact(artifact.metadata_json)
            if local_source is not None:
                return local_source.path
            candidate = Path(artifact.path)
            if candidate.exists():
                return candidate

    raw_files = sorted(path for path in raw_dir.iterdir() if path.is_file()) if raw_dir.exists() else []
    if raw_files:
        return raw_files[0]
    raise ClipExportFailure(code="missing_input", message="Clip export requires a downloaded source video before export can run.")


def _source_video_reference(record, source_video_path: Path) -> str:
    """Return a local source locator for durable metadata, or the managed artifact path otherwise."""
    for artifact in reversed(record.artifacts):
        if artifact.stage_name != "ingest" or artifact.kind != "source_video":
            continue
        local_source = resolve_local_reference_artifact(artifact.metadata_json)
        if local_source is not None:
            return local_source.locator
    return str(source_video_path)


def _safe_source_error(message: str, source_video_path: Path, source_reference: str) -> str:
    """Prevent a subprocess diagnostic from disclosing a trusted local reference path."""
    return message.replace(str(source_video_path), source_reference)


def _resolve_source_duration_seconds(task_id: str, record) -> float:
    task_dirs = ensure_task_dirs(task_id)
    preferred_probe = task_dirs["work"] / "media-probe.json"
    candidate_paths = [preferred_probe]
    for artifact in reversed(record.artifacts):
        if artifact.stage_name == "media_prep" and artifact.kind == "media_probe":
            candidate_paths.append(Path(artifact.path))

    for candidate_path in candidate_paths:
        if not candidate_path.exists():
            continue
        payload = json.loads(candidate_path.read_text(encoding="utf-8"))
        duration = _coerce_duration(payload)
        if duration is not None:
            return duration

    for artifact in reversed(record.artifacts):
        if artifact.stage_name == "media_prep" and artifact.kind == "media_probe":
            payload = json.loads(artifact.metadata_json)
            duration = _coerce_duration(payload.get("ffprobe_metadata"))
            if duration is not None:
                return duration

    raise ClipExportFailure(code="missing_input", message="Clip export requires media probe metadata with source duration.")


def _coerce_duration(payload: object) -> float | None:
    if not isinstance(payload, dict):
        return None
    format_payload = payload.get("format")
    if not isinstance(format_payload, dict):
        return None
    duration = format_payload.get("duration")
    try:
        return float(duration)
    except (TypeError, ValueError):
        return None


def _validate_range(start_s: float, end_s: float, source_duration_s: float) -> None:
    if start_s < 0 or end_s <= start_s:
        raise ClipExportFailure(code="invalid_range", message="Clip range must have non-negative bounds and end after start.")
    if end_s > source_duration_s:
        raise ClipExportFailure(
            code="invalid_range",
            message=f"Clip range {start_s:.3f}-{end_s:.3f}s falls outside the source duration {source_duration_s:.3f}s.",
        )


def _build_export_filename(start_s: float, end_s: float) -> str:
    start_ms = int(round(start_s * 1000))
    end_ms = int(round(end_s * 1000))
    return f"clip-{start_ms:08d}-{end_ms:08d}.mp4"


def _format_ffmpeg_seconds(seconds: float) -> str:
    return f"{seconds:.3f}"


def _persist_export_artifact(
    session: Session,
    *,
    task_id: str,
    candidate_id: int,
    output_path: Path,
    start_s: float,
    end_s: float,
    source_duration_s: float,
    source_video_reference: str,
    export_backend: str,
    video_encoder: str,
) -> Artifact:
    existing = session.exec(
        select(Artifact)
        .where(Artifact.task_id == task_id)
        .where(Artifact.stage_name == "export")
        .where(Artifact.kind == "clip_export")
        .where(Artifact.path == str(output_path))
    ).first()
    metadata = {
        "candidate_id": candidate_id,
        "start_s": start_s,
        "end_s": end_s,
        "source_duration_s": source_duration_s,
        "source_video_path": source_video_reference,
        "filename": output_path.name,
        "export_backend": export_backend,
        "video_encoder": video_encoder,
    }
    if existing is not None:
        existing.metadata_json = json.dumps(metadata, sort_keys=True)
        session.add(existing)
        session.flush()
        session.refresh(existing)
        refresh_task_storage(session, task_id=task_id)
        return existing
    return persist_artifact_metadata(
        session,
        task_id=task_id,
        stage_name="export",
        kind="clip_export",
        path=output_path,
        metadata=metadata,
    )
