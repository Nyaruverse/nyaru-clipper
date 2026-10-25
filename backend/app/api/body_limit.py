from __future__ import annotations

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send


class OperationsBodyLimit:
    def __init__(self, app: ASGIApp, *, maximum: int = 20 * 1024 * 1024) -> None:
        self.app, self.maximum = app, maximum

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope['type'] != 'http' or scope['method'] != 'POST' or not (scope['path'] == '/api/v2/operations' or
                scope['path'].startswith('/companion-api/jobs/') and scope['path'].endswith(('/topic-segments', '/topic-clips'))):
            await self.app(scope, receive, send)
            return
        chunks = []
        size = 0
        while True:
            message = await receive()
            if message['type'] == 'http.disconnect':
                return
            body = message.get('body', b'')
            size += len(body)
            if size > self.maximum:
                await JSONResponse({'detail': '操作请求超过 20 MiB 上限'}, status_code=413)(scope, receive, send)
                return
            chunks.append(body)
            if not message.get('more_body', False):
                break
        delivered = False

        async def bounded_receive() -> Message:
            nonlocal delivered
            if delivered:
                return await receive()
            delivered = True
            return {'type': 'http.request', 'body': b''.join(chunks), 'more_body': False}

        await self.app(scope, bounded_receive, send)
