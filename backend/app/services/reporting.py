from __future__ import annotations

import json
from contextlib import contextmanager
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlmodel import Session, select

from app.models import Artifact, ClipCandidate, PipelineRun
from app.repositories.tasks import TaskRecord, get_task_record
from app.services.storage import ensure_task_dirs, persist_artifact_metadata, refresh_task_storage, reconcile_storage_after_cleanup


@dataclass(frozen=True, slots=True)
class PreparedTaskReport:
    record: TaskRecord
    output_path: Path


def generate_task_report(session: Session, task_id: str) -> PreparedTaskReport:
    """Prepare the canonical report without exposing a nonterminal artifact."""
    record = get_task_record(session, task_id)
    if record is None:
        raise ValueError(f"Unknown task_id: {task_id}")
    return PreparedTaskReport(record, ensure_task_dirs(task_id)["reports"] / "task-report.md")


@contextmanager
def publish_task_report(session: Session, prepared: PreparedTaskReport) -> Iterator[Artifact]:
    """Publish terminal rows, restoring prior bytes if registration or commit fails."""
    record = prepared.record
    task_id = record.task.id
    if record.task.status not in {"success", "failed", "cancelled"}:
        raise ValueError("Final reports require a terminal task state")
    report_text = _render_report(session, record, _collect_exported_clips(record.artifacts))
    output_path = prepared.output_path
    backup = output_path.with_suffix(".md.previous")
    temporary = output_path.with_suffix(".md.tmp")
    backed_up = False
    replaced = False
    committed = False
    try:
        temporary.write_text(report_text, encoding="utf-8")
        if output_path.exists():
            output_path.replace(backup)
            backed_up = True
        temporary.replace(output_path)
        replaced = True
        artifact = _persist_report_artifact(session, task_id=record.task.id, output_path=output_path)
        yield artifact
        committed = True
    finally:
        if not committed:
            if backed_up:
                backup.replace(output_path)
            elif replaced:
                output_path.unlink(missing_ok=True)
        if committed and backed_up:
            backup.unlink()
            reconcile_storage_after_cleanup(session, task_id=task_id)
        temporary.unlink(missing_ok=True)


def _render_report(session: Session, record: TaskRecord, exported_clips: list[dict[str, Any]]) -> str:
    run_id = session.info.get("pipeline_run_id")
    run = session.get(PipelineRun, run_id) if run_id is not None else None
    source_metadata = _collect_source_metadata(record.artifacts)
    model_metadata = _collect_model_metadata(record.artifacts)
    retries = [stage for stage in record.stages if stage.attempts > 1]
    failed_stages = [stage for stage in record.stages if stage.status == "failed"]
    clip_candidates = _collect_clip_candidates(session, record.task.id)

    lines: list[str] = [
        "# Task Report",
        "",
        "## Task",
        "",
        f"- Task ID: `{record.task.id}`",
        f"- Source URL: {record.task.source_url}",
        f"- Normalized Source URL: {record.task.normalized_source_url}",
        f"- Source Video ID: {record.task.source_video_id or 'n/a'}",
        f"- Task Status: {record.task.status}",
        f"- Canonical Run ID: `{run.id if run is not None else 'standalone'}`",
        f"- Canonical Run Status: {run.status if run is not None else record.task.status}",
        "- Scope: Canonical pipeline terminal snapshot; later manual exports are separate operations.",
        "",
        "## Source Metadata",
        "",
    ]
    if source_metadata:
        for key, value in source_metadata.items():
            lines.append(f"- {key}: {value}")
    else:
        lines.append("- No source metadata recorded")

    lines.extend(["", "## Stage Timings", "", "| Stage | Status | Attempts | Started | Finished | Summary |", "| --- | --- | ---: | --- | --- | --- |"])
    for stage in record.stages:
        lines.append(
            "| {name} | {status} | {attempts} | {started} | {finished} | {summary} |".format(
                name=stage.name,
                status=stage.status,
                attempts=stage.attempts,
                started=stage.started_at.isoformat() if stage.started_at else "-",
                finished=stage.finished_at.isoformat() if stage.finished_at else "-",
                summary=stage.summary or "-",
            )
        )

    lines.extend(["", "## Model Metadata", ""])
    if model_metadata:
        for entry in model_metadata:
            lines.append(f"- {entry['stage_name']}/{entry['kind']}: {json.dumps(entry['model_metadata'], ensure_ascii=False, sort_keys=True)}")
    else:
        lines.append("- No model metadata recorded")

    lines.extend(["", "## Retries", ""])
    if retries:
        for stage in retries:
            lines.append(f"- {stage.name}: {stage.attempts} attempts")
    else:
        lines.append("- No retries recorded")

    lines.extend(["", "## Failures", ""])
    if failed_stages:
        for stage in failed_stages:
            lines.append(f"- {stage.name}: {stage.summary or stage.status}")
    else:
        lines.append("- No failed stages recorded")

    lines.extend(["", "## Artifacts", ""])
    if record.artifacts:
        for artifact in record.artifacts:
            lines.append(f"- {artifact.stage_name}/{artifact.kind}: `{artifact.path}`")
    else:
        lines.append("- No artifacts recorded")

    lines.extend(["", "## Exported Clips", ""])
    if exported_clips:
        for clip in exported_clips:
            lines.append(
                f"- `{clip['filename']}` ({clip['start_s']}s → {clip['end_s']}s) from candidate {clip['candidate_id']}"
            )
    else:
        lines.append("- No exported clips recorded")

    lines.extend(["", "## Clip Candidates", ""])
    if clip_candidates:
        for candidate in clip_candidates:
            lines.append(
                f"- Candidate {candidate['id']}: {candidate['start_s']}s → {candidate['end_s']}s [{candidate['status']}] score={candidate['score']}"
            )
    else:
        lines.append("- No clip candidates recorded")

    return "\n".join(lines) + "\n"


def _collect_source_metadata(artifacts: list[Artifact]) -> dict[str, Any]:
    for artifact in reversed(artifacts):
        if artifact.kind == "source_metadata":
            metadata = json.loads(artifact.metadata_json)
            source_metadata = metadata.get("source_metadata")
            if isinstance(source_metadata, dict):
                return source_metadata
    return {}


def _collect_model_metadata(artifacts: list[Artifact]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for artifact in artifacts:
        metadata = json.loads(artifact.metadata_json)
        model_metadata = metadata.get("model_metadata")
        if isinstance(model_metadata, dict):
            entries.append(
                {
                    "stage_name": artifact.stage_name,
                    "kind": artifact.kind,
                    "model_metadata": model_metadata,
                }
            )
    return entries


def _collect_exported_clips(artifacts: list[Artifact]) -> list[dict[str, Any]]:
    clips: list[dict[str, Any]] = []
    for artifact in artifacts:
        if artifact.kind != "clip_export":
            continue
        metadata = json.loads(artifact.metadata_json)
        clips.append(
            {
                "filename": metadata.get("filename") or Path(artifact.path).name,
                "candidate_id": metadata.get("candidate_id"),
                "start_s": metadata.get("start_s"),
                "end_s": metadata.get("end_s"),
            }
        )
    return clips


def _collect_clip_candidates(session: Session, task_id: str) -> list[dict[str, Any]]:
    candidates = session.exec(
        select(ClipCandidate).where(ClipCandidate.task_id == task_id).order_by(ClipCandidate.id)
    ).all()
    return [
        {
            "id": candidate.id,
            "start_s": candidate.start_seconds,
            "end_s": candidate.end_seconds,
            "status": candidate.status,
            "score": candidate.score,
        }
        for candidate in candidates
    ]


def _persist_report_artifact(session: Session, *, task_id: str, output_path: Path) -> Artifact:
    existing = session.exec(
        select(Artifact)
        .where(Artifact.task_id == task_id)
        .where(Artifact.stage_name == "report")
        .where(Artifact.kind == "task_report_markdown")
        .where(Artifact.path == str(output_path))
    ).first()
    metadata = {"filename": output_path.name}
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
        stage_name="report",
        kind="task_report_markdown",
        path=output_path,
        metadata=metadata,
    )
