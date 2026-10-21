from __future__ import annotations

import json
from typing import Callable

import anyio
import httpx
from pydantic import SecretStr

JsonRequest = Callable[[str, str], str]
TOTAL_TIMEOUT = 120
RETRY_DELAY = 1
MAX_STREAM_BYTES = 2 * 1024 * 1024


def _invalid_constant(value: str) -> None:
    raise ValueError("nonstandard JSON constant")


def _completed_text(event: dict, completed_items: dict[int, dict]) -> str:
    response = event['response']
    if response['status'] != 'completed':
        raise ValueError('incomplete')
    output = response['output']
    if output == []:
        if sorted(completed_items) != list(range(len(completed_items))):
            raise ValueError('missing completed item')
        output = [completed_items[index] for index in range(len(completed_items))]
        if any(item['type'] != 'reasoning' and item.get('status') != 'completed' for item in output):
            raise ValueError('incomplete output item')
    texts = []
    for item in output:
        if item['type'] == 'reasoning':
            continue
        if item['type'] != 'message' or item['role'] != 'assistant':
            raise ValueError('unexpected output')
        for content in item['content']:
            if content['type'] != 'output_text':
                raise ValueError('non-text output')
            texts.append(content['text'])
    text = ''.join(texts)
    if not text.strip() or not isinstance(json.loads(text, parse_constant=_invalid_constant), dict):
        raise ValueError('invalid JSON object')
    return text


class ChatGPTProvider:
    def __init__(self, model: str, token: Callable[[], SecretStr], *, transport=None):
        if not model.strip() or model.startswith('chatgpt:'):
            raise ValueError('请选择有效的 ChatGPT 账户模型')
        self.model, self.token, self.transport = model, token, transport

    def __call__(self, instructions: str, input_json: str) -> str:
        try:
            return anyio.run(self._request, instructions, input_json)
        except TimeoutError:
            raise ValueError('ChatGPT 请求总时长超时；已完成结果已保留') from None

    async def _request(self, instructions: str, input_json: str) -> str:
        with anyio.fail_after(TOTAL_TIMEOUT):
            async with httpx.AsyncClient(transport=self.transport, timeout=httpx.Timeout(30, connect=10),
                                         follow_redirects=False) as client:
                for attempt in range(3):
                    received = False
                    try:
                        try:
                            credential = await anyio.to_thread.run_sync(self.token, abandon_on_cancel=True)
                            token = credential.get_secret_value()
                        except Exception:
                            raise ValueError('ChatGPT 授权不可用，请重新连接账户') from None
                        if not token.strip():
                            raise ValueError('ChatGPT 授权不可用，请重新连接账户')
                        async with client.stream('POST', 'https://api.openai.com/v1/responses',
                                headers={'Authorization': f'Bearer {token}'},
                                json={'model': self.model, 'instructions': instructions,
                                      'input': [{'role': 'user', 'content': input_json}],
                                      'store': False, 'stream': True}) as response:
                            if response.status_code in {401, 403}:
                                raise ValueError('ChatGPT 授权失效或无权限，请重新连接账户')
                            if response.status_code in {402, 429}:
                                raise ValueError('ChatGPT 订阅额度不可用，请检查账户用量后重试')
                            if response.status_code in {500, 502, 503, 504} and attempt < 2:
                                pass
                            elif response.status_code != 200:
                                raise ValueError(f'ChatGPT 请求失败（HTTP {response.status_code}）')
                            else:
                                pending = b''
                                size = 0
                                completed_items: dict[int, dict] = {}
                                async for chunk in response.aiter_bytes():
                                    received = True
                                    size += len(chunk)
                                    if size > MAX_STREAM_BYTES:
                                        raise ValueError('ChatGPT 返回内容超过上限')
                                    pending = (pending + chunk).replace(b'\r\n', b'\n')
                                    while b'\n\n' in pending:
                                        frame, pending = pending.split(b'\n\n', 1)
                                        data = b'\n'.join(line[5:].lstrip(b' ') for line in frame.split(b'\n')
                                                          if line.startswith(b'data:'))
                                        if not data:
                                            continue
                                        try:
                                            event = json.loads(data)
                                            kind = event['type']
                                            if kind == 'response.output_item.done':
                                                index = event['output_index']
                                                if type(index) is not int or index < 0 or index in completed_items:
                                                    raise ValueError('invalid completed item index')
                                                completed_items[index] = event['item']
                                            if kind == 'response.completed':
                                                return _completed_text(event, completed_items)
                                            if kind in {'response.failed', 'response.incomplete', 'error'}:
                                                code = event.get('response', {}).get('error', {}) or {}
                                                if code.get('code') in {'subscription_sharing_usage_limit_exceeded',
                                                                        'subscription_sharing_usage_unavailable'}:
                                                    raise ValueError('ChatGPT 订阅额度不可用，请检查账户用量后重试')
                                                raise ValueError('ChatGPT 返回失败或不完整；已完成结果已保留')
                                        except (KeyError, TypeError, AttributeError, UnicodeError, RecursionError, json.JSONDecodeError):
                                            raise ValueError('ChatGPT 返回格式无效；已完成结果已保留') from None
                                        except ValueError as exc:
                                            if str(exc).startswith('ChatGPT '):
                                                raise
                                            raise ValueError('ChatGPT 返回格式无效；已完成结果已保留') from None
                                raise ValueError('ChatGPT 流中断，未收到完整结果；请重试')
                    except httpx.RequestError:
                        if received or attempt == 2:
                            raise ValueError('ChatGPT 网络连接失败或流中断；已完成结果已保留') from None
                    await anyio.sleep(RETRY_DELAY * (attempt + 1))
        raise ValueError('ChatGPT 请求失败；已完成结果已保留')
