from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, assert_never

from pydantic import JsonValue

from app.api.schemas.operations import ExportOperation, LiveOperation, OperationInput, RecordingOperation, TranslateOperation
from app.arctime import companion_llm
from app.services.task_operations import OperationConflict, digest
from app.services.task_requests import RequestDocument, freeze_request
from app.services.unified_files import checked_path, immutable_bytes

if TYPE_CHECKING:
    from app.arctime.unified_host import NativeHost


def configuration_for(host: NativeHost, payload: OperationInput) -> dict[str, JsonValue]:
    from app.api.routes.operations import configuration_snapshot
    from app.services.public_runtime_settings import PublicRuntimeSettings, effective_settings
    content = host.globals.read('runtime/settings.json')
    public = PublicRuntimeSettings.model_validate_json(content) if content is not None else None
    settings = effective_settings(content)
    configuration = configuration_snapshot(payload, model=public.cpp_model if public else host.model,
        threads=public.cpp_threads if public else host.threads, settings=settings)
    template_id = None
    project_id = None
    match payload:
        case RecordingOperation(engine='whisperx', request=request):
            from app.services.whisperx_adapter import snapshot_whisperx
            configuration['whisperx'] = snapshot_whisperx(settings, request.language).model_dump(mode='json')
            template_id = request.subtitle_template_id
        case RecordingOperation(request=request) | LiveOperation(request=request):
            template_id = request.subtitle_template_id
        case TranslateOperation():
            context = host.context(payload.task_id)
            if context is None or context.source.source_language != payload.source_language:
                raise OperationConflict('translation source is not ready or language changed')
            document = host.documents.load(payload.task_id, context.document(host.templates.load_defaults()))
            if payload.document_revision is not None and payload.document_revision != document.revision:
                raise OperationConflict('document revision changed')
            configuration['translation_document'] = freeze_request(host.root, payload.task_id,
                {'request': {'document': document.model_dump(mode='json')}})
        case ExportOperation(request=request):
            project_id = request.arctime_template_id
        case unreachable:
            assert_never(unreachable)
    if template_id is not None:
        template = next((item for item in host.templates.list_styles() if item.id == template_id), None)
        if template is None:
            raise OperationConflict('selected template does not exist')
        configuration['subtitle_template'] = template.model_dump(mode='json')
        project_id = template.arctime_template_id
    if project_id is not None:
        content = host.templates.download_project(project_id)
        checksum = digest(content)
        path = f'.unified/operation-projects/{payload.task_id}/{checksum}.atpj'
        immutable_bytes(checked_path(host.settings_root, path), content)
        configuration['project'] = {'id': project_id, 'body': RequestDocument(path=path, sha256=checksum).model_dump(mode='json')}
    cloud = (isinstance(payload, (RecordingOperation, LiveOperation)) and payload.request.saozi
        or isinstance(payload, TranslateOperation) and payload.provider != 'hf')
    if cloud:
        credentials = companion_llm.LLMConfig(host.root, settings_root=host.settings_root, credential_root=host.credential_root, preferences=host.globals)
        try:
            if isinstance(payload, TranslateOperation):
                model = 'chatgpt:' + payload.model.removeprefix('chatgpt:') if payload.provider == 'chatgpt' else payload.model
            else:
                model = companion_llm.selected_model(credentials)
            companion_llm.require_key(credentials, model)
            configuration['llm_model'] = model
        finally:
            credentials.chatgpt.close()
    return configuration


class FrozenProjects:
    def __init__(self, root: Path, value: JsonValue | None) -> None:
        self.root, self.value = root, value

    def download_project(self, template_id: str) -> bytes:
        if not isinstance(self.value, dict) or self.value.get('id') != template_id:
            raise OperationConflict('project is absent from the queued snapshot')
        reference = RequestDocument.model_validate(self.value['body'])
        content = checked_path(self.root, reference.path).read_bytes()
        if digest(content) != reference.sha256:
            raise OperationConflict('frozen project body changed')
        return content
