from __future__ import annotations

import json
from typing import TYPE_CHECKING, assert_never

from pydantic import TypeAdapter

from app.api.schemas.operations import ExportOperation, LiveOperation, OperationInput, RecordingOperation, TranslateOperation
from app.services.media_dispatch import process_media
from app.services.task_execution import Execution, ExecutionCancelled, WorkflowFailure
from app.services.task_requests import restore_request
from app.services.unified_exports import export_result
from app.services.unified_configuration import FrozenProjects

if TYPE_CHECKING:
    from app.arctime.unified_host import NativeHost


def dispatch(host: NativeHost, execution: Execution) -> None:
    if host.stopping.is_set():
        raise ExecutionCancelled('host is stopping')
    snapshot = json.loads(execution.snapshot_json)
    body = restore_request(host.root, snapshot['input'])
    payload = TypeAdapter(OperationInput).validate_python({'kind': execution.kind, 'task_id': execution.task_id, **body})
    match payload:
        case RecordingOperation() | LiveOperation():
            process_media(host, execution, payload, snapshot['config'])
        case ExportOperation(request=request):
            context = host.context(execution.task_id)
            if context is None:
                raise WorkflowFailure('missing_input')
            export_result(execution, context, request, FrozenProjects(host.settings_root, snapshot['config'].get('project')))
        case TranslateOperation():
            from app.arctime import companion_llm
            from app.arctime.subtitle_document import SubtitleDocument
            from app.services.unified_translation import translate_document
            from pydantic import SecretStr
            context = host.context(execution.task_id)
            if context is None:
                raise WorkflowFailure('missing_input')
            frozen = restore_request(host.root, snapshot['config']['translation_document'])
            document = SubtitleDocument.model_validate(frozen['request']['document'])
            credentials = companion_llm.LLMConfig(host.root, settings_root=host.settings_root, credential_root=host.credential_root, preferences=host.globals)
            try:
                model = 'chatgpt:' + payload.model.removeprefix('chatgpt:') if payload.provider == 'chatgpt' else payload.model
                key = companion_llm.require_key(credentials, model) if payload.provider != 'hf' else SecretStr('')
                translate_document(execution, context, payload, document, host.documents, key=key,
                    requester=companion_llm.requester(credentials, model) if payload.provider != 'hf' else None)
            finally:
                credentials.chatgpt.close()
        case unreachable:
            assert_never(unreachable)
