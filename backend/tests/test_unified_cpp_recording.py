from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import pytest
from sqlmodel import Session, select
from fastapi.testclient import TestClient

from app.arctime.companion_models import JobInput
from app.arctime.local_asr import DEFAULT_MODEL
from app.arctime.subtitle_encoding import subtitle_ffmpeg
from app.arctime.gui import create_app
from app.arctime.subtitle_document import SubtitleDocument
from app.arctime.subtitle_inputs import ExportRequest
from app.arctime.subtitle_templates import TemplateStore
from app.models_unified import UnifiedOperation, UnifiedPublication
from app.services.cpp_recording import CppConfiguration, process_cpp_recording
from app.services.task_execution import Execution, Executor
from app.services.task_operations import bind_task, enqueue_operation, set_admissions
from app.services.unified_files import file_sha256
from app.services.task_documents import Documents
from app.services.unified_exports import export_result
from test_unified_operations import database
from unification_media import build_media


@pytest.mark.skipif(sys.platform != 'darwin', reason='Actual macOS whisper.cpp acceptance profile')
def test_real_cpp_recording_uses_shared_executor_and_publishes_editor_context(tmp_path: Path) -> None:
    reference = build_media(tmp_path / 'reference')
    source = tmp_path / 'short-ja.mp4'
    subprocess.run([subtitle_ffmpeg(), '-v', 'error', '-nostdin', '-n', '-i', str(reference / 'source.mp4'),
        '-t', '10', '-c:v', 'copy', '-c:a', 'aac', str(source)], capture_output=True, check=True, timeout=30)
    before = file_sha256(source)
    configuration = CppConfiguration(model=DEFAULT_MODEL, model_sha256=file_sha256(DEFAULT_MODEL), threads=4)
    request = JobInput(url='https://local.invalid', ranges=[('1', '6')], language='ja')
    engine = database(tmp_path)
    with Session(engine) as session:
        binding = bind_task(session, uuid4(), 'actual-recording', 'g', origin='native')
        enqueue_operation(session, binding.task_id, 'process_recording', {'config': configuration.model_dump(mode='json'), 'input': request.model_dump(mode='json')})
        set_admissions(session, paused=False)
        session.commit()
    contexts = []

    def process(execution: Execution) -> None:
        contexts.append(process_cpp_recording(execution, request, configuration, local_source=source, source_sha256=before))

    Executor(engine, tmp_path / 'tasks', tmp_path / 'guard').iteration(process)
    with Session(engine) as session:
        assert session.exec(select(UnifiedOperation)).one().state == 'succeeded'
        assert len(session.exec(select(UnifiedPublication)).all()) == 2
    context = contexts[0]
    assert context.source.source_language == 'ja' and context.cues
    assert all(0 <= cue.start_seconds < cue.end_seconds <= context.source.duration for cue in context.cues)
    assert len(context.source.clips) == 1 and context.source.clips[0].start == 1.
    assert file_sha256(source) == before
    root = tmp_path / 'tasks'
    url = f'/companion-api/jobs/{context.source.task_id}/subtitle-document'
    with TestClient(create_app(root, artifacts=(context,), documents=Documents(engine, root),
                              settings_root=tmp_path / 'settings', credential_root=tmp_path / 'credentials')) as client:
        loaded = client.get(url)
        assert loaded.status_code == 200, loaded.text
        edited = loaded.json()
        edited['cues'][0]['text'] = '実際の認識結果から保存した編集字幕'
        saved = client.post(url, json=edited)
        assert saved.status_code == 200, saved.text
        document = SubtitleDocument.model_validate(saved.json())
        assert client.post(url.removesuffix('/subtitle-document') + '/subtitle-export', json={
            'kind': 'burn', 'video': 'clip-001.mp4', 'style': document.style.model_dump()}).status_code == 409
    with TestClient(create_app(root, artifacts=(context,), documents=Documents(engine, root),
                              settings_root=tmp_path / 'settings', credential_root=tmp_path / 'credentials')) as reopened:
        assert reopened.get(url).json()['cues'][0]['text'] == '実際の認識結果から保存した編集字幕'
    request = ExportRequest(kind='burn', video='clip-001.mp4', style=document.style, document=document)
    with Session(engine) as session:
        enqueue_operation(session, context.source.task_id, 'export', {'input': request.model_dump(mode='json'), 'config': {}})
        session.commit()
    Executor(engine, root, tmp_path / 'guard').iteration(lambda execution: export_result(
        execution, context, request, TemplateStore(tmp_path / 'settings')))
    with Session(engine) as session:
        assert all(operation.state == 'succeeded' for operation in session.exec(select(UnifiedOperation)).all())
        assert len(session.exec(select(UnifiedPublication)).all()) == 3
