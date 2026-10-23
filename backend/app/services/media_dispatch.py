from __future__ import annotations

import threading
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, JsonValue

from app.api.schemas.operations import LiveOperation, RecordingOperation
from app.arctime import companion_llm
from app.arctime.saozi import SaoziSelector
from app.arctime.subtitle_templates import StyleTemplate
from app.services.cpp_live import process_cpp_live
from app.services.cpp_recording import CppConfiguration, process_cpp_recording
from app.services.task_execution import Execution, WorkflowFailure
from app.services.unified_configuration import FrozenProjects
from app.services.whisperx_adapter import WhisperXAdapter, WhisperXConfiguration

if TYPE_CHECKING:
    from app.arctime.unified_host import NativeHost


class _Configuration(BaseModel):
    model_config = ConfigDict(frozen=True)
    model_path: Path | None = None
    model_sha256: str | None = None
    threads: int = 4
    llm_model: str | None = None
    subtitle_template: StyleTemplate | None = None
    project: JsonValue | None = None
    whisperx: WhisperXConfiguration | None = None
    local_source: Path | None = None
    source_sha256: str | None = None


def process_media(host: NativeHost, execution: Execution, payload: RecordingOperation | LiveOperation,
                  snapshot: JsonValue) -> None:
    configuration = _Configuration.model_validate(snapshot)
    credentials = None
    selector = None
    requester = None
    key = None
    if payload.request.saozi:
        credentials = companion_llm.LLMConfig(host.root, settings_root=host.settings_root, credential_root=host.credential_root, preferences=host.globals)
    try:
        if credentials is not None:
            if configuration.llm_model is None:
                raise WorkflowFailure('provider_snapshot_missing')
            key = companion_llm.require_key(credentials, configuration.llm_model)
            requester = companion_llm.requester(credentials, configuration.llm_model)
            selector = SaoziSelector(key, configuration.llm_model, request_json=requester)

        def translate(directory: Path, final: bool = True) -> set[str]:
            from app.arctime.saozi_translation import translate
            if key is None or configuration.llm_model is None:
                raise WorkflowFailure('provider_snapshot_missing')
            changed: set[str] = set()
            translate(directory, key, final=final, model=configuration.llm_model, locked=isinstance(payload, LiveOperation),
                progress=lambda message: execution.check(), request_json=requester, changed_artifact=changed.add)
            return {name.removesuffix('.ja-zh.srt') + '.mp4' for name in changed if name.startswith('clip-')}

        projects = FrozenProjects(host.settings_root, configuration.project)
        cpp = None
        if isinstance(payload, LiveOperation) or payload.engine == 'whisper.cpp':
            if configuration.model_path is None or configuration.model_sha256 is None:
                raise WorkflowFailure('asr_model_unavailable_offline')
            cpp = CppConfiguration(model=configuration.model_path, model_sha256=configuration.model_sha256, threads=configuration.threads)
        if isinstance(payload, LiveOperation):
            if selector is None or cpp is None:
                raise WorkflowFailure('live_provider_missing')
            stop = threading.Event()
            with host.live_lock:
                host.live_events[execution.task_id] = stop
            try:
                process_cpp_live(execution, payload.request, cpp, selector=selector, templates=projects,
                    stop=stop, template=configuration.subtitle_template, translate=translate)
            finally:
                with host.live_lock:
                    host.live_events.pop(execution.task_id, None)
        else:
            adapter = None
            if payload.engine == 'whisperx':
                if configuration.whisperx is None:
                    raise WorkflowFailure('asr_configuration_missing')
                adapter = WhisperXAdapter(execution, configuration.whisperx)
            process_cpp_recording(execution, payload.request, cpp, local_source=configuration.local_source,
                source_sha256=configuration.source_sha256, selector=selector, translate=translate if selector else None,
                template=configuration.subtitle_template, templates=projects, adapter=adapter)
    finally:
        if credentials is not None:
            credentials.chatgpt.close()
