from __future__ import annotations

import argparse
import os
import signal
import socket
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path[:0] = [str(ROOT / 'dependencies'), str(ROOT / 'legacy')]


class OfflineRecoveryError(RuntimeError):
    pass


def offline_audit(event: str, arguments: tuple) -> None:
    if event == 'socket.connect':
        raise OfflineRecoveryError('network requests are unavailable during local recovery')
    if event == 'import' and (arguments[0] in {'torch', 'whisperx', 'transformers'}):
        raise OfflineRecoveryError('model imports are unavailable during local recovery')


def main() -> int:
    if os.environ.get('NYARU_RECOVERY_LOCAL_ONLY') != '1':
        raise OfflineRecoveryError('launch this archived helper through the recovery launcher')
    sys.addaudithook(offline_audit)
    parser = argparse.ArgumentParser()
    parser.add_argument('--data', type=Path, required=True)
    parser.add_argument('--ready', type=Path, required=True)
    parser.add_argument('--parent-pid', type=int, required=True)
    options = parser.parse_args()
    if (ROOT / 'tools').is_dir():
        os.environ['PATH'] = str(ROOT / 'tools') + os.pathsep + os.environ.get('PATH', '')
        os.environ['DYLD_LIBRARY_PATH'] = str(ROOT / 'tools')
        os.environ['LD_LIBRARY_PATH'] = str(ROOT / 'tools')
    from app.arctime.gui import create_app
    from app.arctime.media import write_json
    from fastapi import Request
    from fastapi.responses import JSONResponse
    import uvicorn
    app = create_app(options.data / 'runs', model=ROOT / 'offline-no-model', web_dist=ROOT / 'web')

    @app.middleware('http')
    async def local_only(request: Request, call_next):
        path = request.url.path
        if request.method != 'GET' and not (path.startswith('/companion-api/') and (
                path.endswith(('/subtitle-document', '/subtitle-preview', '/subtitle-export'))
                or path in {'/companion-api/template-preview', '/companion-api/subtitle-settings', '/companion-api/studio-settings'}
                or path.startswith(('/companion-api/style-templates', '/companion-api/arctime-templates')))):
            return JSONResponse({'detail': '恢复模式只支持本地字幕编辑和导出'}, status_code=403)
        if path.startswith(('/companion-api/chatgpt', '/companion-api/llm-config', '/api/')):
            return JSONResponse({'detail': '恢复模式不访问在线供应商或统一数据库'}, status_code=403)
        return await call_next(request)

    server = uvicorn.Server(uvicorn.Config(app, loop='asyncio', http='h11', ws='none', log_level='warning', access_log=False))

    def watch_parent() -> None:
        while os.getppid() == options.parent_pid:
            time.sleep(.2)
        os.killpg(os.getpgrp(), signal.SIGKILL)

    threading.Thread(target=watch_parent, name='recovery-parent-watch', daemon=True).start()
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0))
        listener.listen(128)
        write_json(options.ready, {'url': f'http://127.0.0.1:{listener.getsockname()[1]}', 'pid': os.getpid()})
        try:
            server.run(sockets=[listener])
        finally:
            options.ready.unlink(missing_ok=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
