from __future__ import annotations

from pathlib import Path
import sys
import subprocess
import time

from fastapi.testclient import TestClient
import pytest
from sqlmodel import Session, select

from app.arctime.gui import create_app
from app.arctime.unified_host import NativeHost
from test_unified_operations import database
from app.arctime.local_asr import DEFAULT_MODEL
from app.arctime.subtitle_encoding import subtitle_ffmpeg
from app.models_unified import UnifiedOperation
from unification_media import build_media


def test_desktop_upload_adapts_to_paused_shared_queue_without_legacy_manifest(tmp_path: Path) -> None:
    model = tmp_path / 'fixture-model.bin'
    model.write_bytes(b'lmgg fixture-only model; never run inference')
    host = NativeHost(database(tmp_path), task_root=tmp_path / 'tasks', settings_root=tmp_path / 'settings',
        credential_root=tmp_path / 'credentials', guard_root=tmp_path / 'guard', model=model)
    with TestClient(create_app(host.root, model=model, host=host)) as client:
        uploaded = client.post('/companion-api/jobs/upload?language=ja&saozi=false&ranges=%5B%5B%221%22%2C%226%22%5D%5D',
            content=b'uploaded fixture bytes; queue stays paused', headers={'content-type': 'application/octet-stream'})
        assert uploaded.status_code == 202, uploaded.text
        task_id = uploaded.json()['id']
        assert len(task_id) == 32
        queue = client.get('/api/v2/operations').json()
        assert queue['paused'] is True and queue['operations'][0]['task_id'] == task_id
        assert queue['operations'][0]['state'] == 'queued' and queue['operations'][0]['attempt'] == 0
        jobs = client.get('/companion-api/jobs').json()
        assert jobs[0]['id'] == task_id and jobs[0]['state'] == 'queued'
        assert not (host.root / task_id / 'job.json').exists()
    reopened = NativeHost(host.engine, task_root=host.root, settings_root=host.settings_root,
        credential_root=host.credential_root, guard_root=host.guard_root, model=model)
    with TestClient(create_app(host.root, model=model, host=reopened)) as client:
        assert client.get('/companion-api/jobs').json()[0]['id'] == task_id
        assert client.get('/api/v2/operations').json()['paused'] is True


@pytest.mark.skipif(sys.platform != 'darwin', reason='Actual macOS whisper.cpp native-host profile')
def test_actual_desktop_upload_process_edit_export_and_reopen_use_shared_core(tmp_path: Path) -> None:
    reference = build_media(tmp_path / 'reference')
    source = tmp_path / 'short-ja.mp4'
    subprocess.run([subtitle_ffmpeg(), '-v', 'error', '-nostdin', '-n', '-i', str(reference / 'source.mp4'),
        '-t', '10', '-c:v', 'copy', '-c:a', 'aac', str(source)], capture_output=True, check=True, timeout=30)
    host = NativeHost(database(tmp_path), task_root=tmp_path / 'tasks', settings_root=tmp_path / 'settings',
        credential_root=tmp_path / 'credentials', guard_root=tmp_path / 'guard', model=DEFAULT_MODEL)
    with TestClient(create_app(host.root, host=host, model=DEFAULT_MODEL)) as client:
        uploaded = client.post('/companion-api/jobs/upload', params={'language': 'ja', 'saozi': 'false', 'ranges': '[["1","6"]]'},
            content=source.read_bytes(), headers={'content-type': 'application/octet-stream'})
        assert uploaded.status_code == 202, uploaded.text
        task_id = uploaded.json()['id']
        queue = client.get('/api/v2/operations').json()
        assert client.post('/api/v2/operations/queue', json={'paused': False, 'expected_revision': queue['revision']}).status_code == 200
        base = f'/companion-api/jobs/{task_id}'
        deadline = time.monotonic() + 60
        while client.get(base).json()['operation_state'] not in {'succeeded', 'failed', 'interrupted', 'cancelled'}:
            assert time.monotonic() < deadline
            time.sleep(.05)
        detail = client.get(base).json()
        assert detail['operation_state'] == 'succeeded', detail
        document = client.get(base + '/subtitle-document').json()
        document['cues'][0]['text'] = '統一コアを通して保存した字幕'
        saved = client.post(base + '/subtitle-document', json=document)
        assert saved.status_code == 200, saved.text
        document = saved.json()
        submitted = client.post(base + '/subtitle-export', json={'kind': 'burn', 'video': 'clip-001.mp4',
            'style': document['style'], 'document': document})
        assert submitted.status_code == 202, submitted.text
        deadline = time.monotonic() + 60
        while True:
            exports = client.get(base + '/subtitle-exports').json()
            if exports['active'] and exports['active']['state'] in {'completed', 'failed', 'interrupted'}:
                break
            assert time.monotonic() < deadline
            time.sleep(.05)
        assert exports['active']['state'] == 'completed', exports
        product = client.get(base + '/files/' + exports['outputs'][0]['filename'])
        assert product.status_code == 200 and len(product.content) > 1000
        with Session(host.engine) as session:
            snapshot = session.exec(select(UnifiedOperation).where(UnifiedOperation.kind == 'export')).one().snapshot_json
            assert 'document_ref' in snapshot and '統一コアを通して保存した字幕' not in snapshot
        assert not (host.root / task_id / 'job.json').exists()
    reopened = NativeHost(host.engine, task_root=host.root, settings_root=host.settings_root,
        credential_root=host.credential_root, guard_root=host.guard_root, model=DEFAULT_MODEL)
    with TestClient(create_app(host.root, host=reopened, model=DEFAULT_MODEL)) as client:
        assert client.get(base + '/subtitle-document').json()['cues'][0]['text'] == '統一コアを通して保存した字幕'
        assert client.get(base + '/files/' + exports['outputs'][0]['filename']).content == product.content
