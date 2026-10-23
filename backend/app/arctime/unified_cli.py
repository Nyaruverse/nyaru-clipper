from __future__ import annotations

import argparse
import json
import socket
from pathlib import Path

from sqlmodel import Session

from app.api.routes.operations import snapshot
from app.api.schemas.operations import OperationInput
from pydantic import TypeAdapter
from app.arctime.gui import create_app
from app.services.task_operations import enqueue_operation, set_admissions
from app.services.task_requests import freeze_request
from app.services.unified_runtime import initialize, open_runtime


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Unified local runtime; every operation uses the shared executor')
    commands = parser.add_subparsers(dest='command', required=True)
    init = commands.add_parser('init')
    init.add_argument('--data', type=Path, required=True)
    init.add_argument('--credentials', type=Path, required=True)
    init.add_argument('--model', type=Path, required=True)
    init.add_argument('--threads', type=int, default=4)
    for name in ('serve', 'queue', 'pause', 'start', 'enqueue'):
        command = commands.add_parser(name)
        command.add_argument('--runtime', type=Path, required=True)
        if name == 'serve':
            command.add_argument('--port', type=int, default=0)
            command.add_argument('--host', default='127.0.0.1')
            command.add_argument('--ready', type=Path)
        if name == 'enqueue':
            command.add_argument('--request', type=Path, required=True)
    options = parser.parse_args(argv)
    if options.command == 'init':
        print(initialize(options.data, options.credentials, options.model, threads=options.threads))
        return 0
    host = open_runtime(options.runtime)
    if options.command == 'serve':
        import uvicorn
        from app.arctime.http_server import CompanionServer
        from app.arctime.media import write_json
        from app.services.host_binding import private_host
        address = private_host(options.host)
        with socket.socket() as listener:
            listener.bind((address, options.port))
            listener.listen(128)
            ready = {'url': f'http://{address}:{listener.getsockname()[1]}'}
            if options.ready:
                write_json(options.ready, ready)
            print(json.dumps(ready), flush=True)
            try:
                CompanionServer(uvicorn.Config(create_app(host.root, host=host, model=host.model, bind_host=address),
                    log_level='warning', access_log=False)).run(sockets=[listener])
            finally:
                if options.ready:
                    options.ready.unlink(missing_ok=True)
        return 0
    with Session(host.engine) as session:
        if options.command in {'pause', 'start'}:
            set_admissions(session, paused=options.command == 'pause')
        elif options.command == 'enqueue':
            payload = TypeAdapter(OperationInput).validate_json(options.request.read_bytes())
            configuration = host.configuration(payload)
            body = freeze_request(host.root, payload.task_id, payload.model_dump(mode='json', exclude={'kind', 'task_id'}))
            enqueue_operation(session, payload.task_id, payload.kind, {'input': body, 'config': configuration})
        print(snapshot(session).model_dump_json())
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
