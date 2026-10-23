from __future__ import annotations

from app.arctime import media
from app.arctime.subtitle_encoding import burn_clip, video_dimensions
from app.arctime.subtitle_exports import _package
from app.arctime.subtitle_inputs import ExportRequest, load_inputs
from app.arctime.subtitle_render import render_document_ass
from app.arctime.subtitle_templates import ProjectTemplates
from app.services.publication_reuse import reuse_publication
from app.services.task_artifacts import ResolvedArtifacts
from app.services.task_execution import Execution
from app.services.task_operations import canonical, digest


def export_result(execution: Execution, context: ResolvedArtifacts, request: ExportRequest, templates: ProjectTemplates,
                  *, video_label: str | None = None) -> str:
    request = request.for_format()
    document = request.document or context.document(request.style)
    request = request.model_copy(update={"document": document})
    workspace = execution.staging("styled-export")
    inputs = load_inputs(workspace, request, artifacts=context)
    project = templates.download_project(request.arctime_template_id) if request.arctime_template_id else None
    identity = digest(canonical({"renderer_revision": 4, "package_revision": 1, "request": request.model_dump(mode="json"),
        "inputs": inputs.digests, "project": digest(project) if project else None, 'video_label': video_label}))
    key = f"export:{identity}"
    existing = reuse_publication(execution, key)
    if existing is not None:
        return existing.publication_id
    workspace = execution.staging(key)
    dimensions = video_dimensions(inputs.source)
    if inputs.document is None:
        raise ExportContractError("validated export document is required")
    (workspace / "subtitle.ass").write_text(render_document_ass(inputs.document, request.bilingual), encoding="utf-8")
    match request.kind:
        case "ass":
            product = workspace / "subtitle.ass"
        case "burn":
            product = burn_clip(inputs.source, workspace, media.probe_video(inputs.source), lambda message: execution.check())
        case "arctime":
            product = _package(workspace, inputs, request, project, dimensions)
        case unreachable:
            from typing import assert_never
            assert_never(unreachable)
    snapshot = workspace / "document.json"
    snapshot.write_text(document.model_dump_json(), encoding="utf-8")
    return execution.publish(key, {"product": product, "document": snapshot}, document_sha256=digest(snapshot.read_bytes()),
        metadata={'request': {**request.model_dump(mode='json', exclude={'document'}), 'video': video_label or request.video}})


class ExportContractError(ValueError):
    pass


