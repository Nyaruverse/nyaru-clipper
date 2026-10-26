from __future__ import annotations

import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field

from app.arctime import media, workflow
from app.arctime.companion_models import JobInput
from app.arctime.local_asr import LocalASR
from app.arctime.subtitle_templates import ProjectTemplates, StyleTemplate
from app.services.recording_results import publish_companion_result
from app.services.asr_adapter import AsrAdapter
from app.services.task_artifacts import ResolvedArtifacts
from app.services.task_execution import Execution, WorkflowFailure
from app.services.task_operations import digest
from app.services.unified_exports import export_result
from app.services.unified_files import checked_path, file_sha256

if TYPE_CHECKING:
    from app.arctime.saozi import SaoziSelector


class CppConfiguration(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    model: Path
    model_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    threads: int = Field(ge=1, le=64)


def process_cpp_recording(execution: Execution, request: JobInput, configuration: CppConfiguration | None, *,
                          local_source: Path | None = None, source_sha256: str | None = None,
                          selector: SaoziSelector | None = None, translate: Callable[[Path], None] | None = None,
                          template: StyleTemplate | None = None, templates: ProjectTemplates | None = None,
                          adapter: AsrAdapter | None = None) -> ResolvedArtifacts:
    if request.live:
        raise WorkflowFailure('live_requires_process_live')
    if request.saozi and (selector is None or translate is None or request.language not in {'auto', 'ja', 'zh'}):
        raise WorkflowFailure('saozi_provider_or_language_unavailable')
    if configuration is not None and (configuration.model.is_symlink() or file_sha256(configuration.model) != configuration.model_sha256):
        raise WorkflowFailure('asr_model_changed')
    if local_source is not None and (source_sha256 is None or local_source.is_symlink() or file_sha256(local_source) != source_sha256):
        raise WorkflowFailure('input_source_changed')
    if template is not None and templates is None:
        raise WorkflowFailure('template_store_unavailable')
    if adapter is None:
        if configuration is None:
            raise WorkflowFailure('asr_adapter_required')
        adapter = LocalASR(configuration.model, request.language, configuration.threads)
    root = execution.staging('workflow')
    directory = root / execution.task_id
    if execution.attempt > 1:
        previous = checked_path(execution.root, f'.unified/staging/{execution.operation_id}/{execution.attempt - 1}/{digest("workflow")}/{execution.task_id}')
        if previous.is_dir() and not directory.exists():
            if any(path.is_symlink() for path in [previous, *previous.rglob('*')]):
                raise WorkflowFailure('checkpoint_contains_symlink')
            shutil.copytree(previous, directory)
    if not directory.exists():
        directory = workflow.create_run(request.url, root,
            [(media.parse_time(start), media.parse_time(end)) for start, end in request.ranges],
            request.highlights, adapter, run_id=execution.task_id, saozi=request.saozi,
            recognition_only=request.recognition_only,
            local_source=local_source, llm_model=selector.model if selector else None,
            progress=lambda message: execution.check())
    try:
        workflow.resume_run(directory, adapter, selector=selector, progress=lambda message: execution.check())
        if translate is not None:
            translate(directory)
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError):
        if (directory / 'transcript.json').is_file() and (directory / 'subtitles.srt').is_file():
            publish_companion_result(execution, directory)
        raise
    context = publish_companion_result(execution, directory)
    if template is not None and templates is not None:
        from app.arctime.subtitle_inputs import ExportRequest
        document = context.document(template.style)
        for index in range(len(context.source.clips)):
            for kind in ('ass', 'burn'):
                export_result(execution, context, ExportRequest(kind=kind, video=f'clip-{index + 1:03d}.mp4',
                    style=template.style, bilingual=context.source.translation is not None, document=document), templates)
    return context
