from __future__ import annotations

import argparse
import socket
from pathlib import Path

import uvicorn
import anyio
from sqlmodel import Session

from app.api.schemas.operations import ExportOperation
from app.arctime.gui import create_app
from app.arctime.http_server import CompanionServer
from app.arctime.local_asr import DEFAULT_MODEL
from app.arctime.media import write_json
from app.arctime.subtitle_inputs import ExportRequest
from app.arctime.subtitle_style import SubtitleStyle
from app.arctime.unified_host import NativeHost
from app.services.migration_snapshot import copy_context
from app.services.task_artifacts import resolve_workstation
from app.services.task_operations import bind_task, enqueue_operation
from app.services.task_requests import freeze_request
from app.services.unified_runtime import initialize, open_runtime
from unified_edit_fixture import make_editor_fixture


def serve(root: Path, bundle: Path, ready: Path) -> None:
    fixture = make_editor_fixture(root / 'source', bundle)
    credentials = root / 'credentials'
    credentials.mkdir()
    manifest = initialize(root / 'runtime', credentials, DEFAULT_MODEL)
    host = open_runtime(manifest)
    source = copy_context(host.root, fixture.artifacts.source, '.unified/results/browser-fixture')
    with Session(host.engine) as session:
        bind_task(session, source.source_instance_id, source.legacy_id, 'browser-fixture', origin='native', context_json=source.model_dump_json())
        for video in ('source.mp4', 'clip-001.mp4'):
            request = ExportRequest(kind='ass', video=video, style=SubtitleStyle(), bilingual=True,
                document=resolve_workstation(source).document(SubtitleStyle()))
            payload = ExportOperation(kind='export', task_id=source.task_id, request=request)
            body = freeze_request(host.root, source.task_id, payload.model_dump(mode='json', exclude={'kind', 'task_id'}))
            enqueue_operation(session, source.task_id, 'export', {'input': body, 'config': host.configuration(payload)})
        session.commit()
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0))
        listener.listen(128)
        write_json(ready, {'url': f'http://127.0.0.1:{listener.getsockname()[1]}', 'task_id': source.task_id})
        app = create_app(host.root, model=host.model, host=host)
        @app.post('/qa/disconnect-events')
        async def disconnect_events():
            app.state.stream_stopping.set()
            await anyio.sleep(.75)
            app.state.stream_stopping.clear()
            return {'disconnected': True}
        try:
            CompanionServer(uvicorn.Config(app,
                log_level='warning', access_log=False)).run(sockets=[listener])
        finally:
            ready.unlink(missing_ok=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--bundle', type=Path, required=True)
    parser.add_argument('--ready', type=Path, required=True)
    options = parser.parse_args()
    options.root.mkdir(mode=0o700, exist_ok=False)
    serve(options.root, options.bundle, options.ready)
