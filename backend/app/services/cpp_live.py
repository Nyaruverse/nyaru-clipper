from __future__ import annotations

import json
import shutil
from pathlib import Path
from threading import Event
from collections.abc import Callable

from app.arctime.companion_models import JobInput
from app.arctime.live_capture import LiveCapture
from app.arctime.local_asr import LocalASR
from app.arctime.saozi import SaoziSelector
from app.arctime.saozi_live import run_live
from app.arctime.subtitle_templates import ProjectTemplates, StyleTemplate
from app.services.cpp_recording import CppConfiguration
from app.services.live_publication import publish_live_clips
from app.services.recording_results import publish_companion_result
from app.services.task_execution import Execution, ExecutionCancelled, ExternalOutcomeUnknown, WorkflowFailure
from app.services.task_operations import digest
from app.services.unified_files import checked_path, file_sha256


def process_cpp_live(execution: Execution, request: JobInput, configuration: CppConfiguration, *,
                     selector: SaoziSelector, templates: ProjectTemplates, stop: Event,
                     translate: Callable[[Path, bool], set[str] | None] | None = None,
                     template: StyleTemplate | None = None, capture: LiveCapture | None = None,
                     adapter: LocalASR | None = None) -> None:
    if not request.live or not request.saozi:
        raise WorkflowFailure('live_request_required')
    if configuration.model.is_symlink() or file_sha256(configuration.model) != configuration.model_sha256:
        raise WorkflowFailure('asr_model_changed')
    directory = execution.staging('workflow') / execution.task_id
    if execution.attempt > 1:
        previous = checked_path(execution.root, f'.unified/staging/{execution.operation_id}/{execution.attempt - 1}/{digest("workflow")}/{execution.task_id}')
        if previous.is_dir() and not directory.exists():
            if any(path.is_symlink() for path in [previous, *previous.rglob('*')]):
                raise WorkflowFailure('checkpoint_contains_symlink')
            shutil.copytree(previous, directory)
    directory.mkdir(exist_ok=True)
    failures: list[WorkflowFailure] = []
    translation_error: WorkflowFailure | None = None

    def bilingual(path: Path, final: bool) -> set[str] | None:
        nonlocal translation_error
        if translate is None or translation_error is not None:
            return set()
        execution.check()
        try:
            return translate(path, final)
        except ExecutionCancelled:
            raise
        except ExternalOutcomeUnknown as error:
            translation_error = error
        except (OSError, ValueError, RuntimeError):
            translation_error = WorkflowFailure('live_translation_failed')
        execution.fail_step('live-translation-failure', translation_error.code, {'child_kind': 'translation'})
        return set()

    def styled(path: Path, job: dict, changed: list[dict] | None) -> None:
        execution.check()
        try:
            publish_live_clips(execution, path, job, template, templates)
        except ExecutionCancelled:
            raise
        except (OSError, ValueError, RuntimeError):
            failure = WorkflowFailure('live_style_publication_failed')
            execution.fail_step(f'live-style-failure:{len(job.get("completed_clips", []))}', failure.code, {'child_kind': 'style'})
            failures.append(failure)

    try:
        run_live(directory, selector, adapter or LocalASR(configuration.model, request.language, configuration.threads), stop,
            lambda message: execution.check(), url=request.url if not (directory / 'job.json').exists() else None,
            capture=capture if execution.attempt == 1 else None, bilingual=bilingual, style_template=template, styled=styled)
    except (OSError, ValueError, RuntimeError):
        path = directory / 'job.json'
        if path.is_file():
            job = json.loads(path.read_bytes())
            publish_live_clips(execution, directory, job, None, templates)
        raise
    publish_companion_result(execution, directory)
    if translation_error is not None:
        raise translation_error
    if failures:
        raise failures[0]
