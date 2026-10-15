import asyncio
import importlib
import json
import time

import httpx
import pytest
from pydantic import SecretStr


def module():
    assert importlib.util.find_spec('app.arctime.chatgpt_provider'), 'Responses provider missing'
    return importlib.import_module('app.arctime.chatgpt_provider')


def event(kind, **values):
    return ('data: ' + json.dumps({'type': kind, **values}) + '\r\n\r\n').encode()


def completed(text='{"ok":true}'):
    return event('response.completed', response={'status': 'completed', 'output': [
        {'type': 'message', 'role': 'assistant', 'content': [{'type': 'output_text', 'text': text}]}]})


class Wire(httpx.AsyncByteStream):
    def __init__(self, data, delay=0, interrupt=False):
        self.data, self.delay, self.interrupt = data, delay, interrupt
        self.closed = False

    async def __aiter__(self):
        for offset in range(0, len(self.data), 7):
            await asyncio.sleep(self.delay)
            yield self.data[offset:offset + 7]
        if self.interrupt:
            raise httpx.ReadError('wire-secret')

    async def aclose(self):
        self.closed = True


def test_wire_contract_and_chunked_completed():
    mod = module()
    calls = []
    wire = Wire(b': keepalive\r\n\r\n' + completed())
    def handle(request):
        calls.append(request)
        assert str(request.url) == 'https://api.openai.com/v1/responses'
        assert request.headers['authorization'] == 'Bearer wire-secret'
        assert json.loads(request.content) == {'model': 'chosen-slug', 'instructions': 'rules',
            'input': [{'role': 'user', 'content': '{}'}], 'store': False, 'stream': True}
        return httpx.Response(200, stream=wire)
    provider = mod.ChatGPTProvider('chosen-slug', lambda: SecretStr('wire-secret'), transport=httpx.MockTransport(handle))
    assert json.loads(provider('rules', '{}')) == {'ok': True}
    assert wire.closed and len(calls) == 1


@pytest.mark.parametrize('data', [event('response.failed', response={'error': {'message': 'wire-secret'}}),
    event('response.incomplete'), event('error', message='wire-secret'), b'data: broken\n\n',
    event('response.output_text.delta', delta='{}'), completed(''), completed('not JSON'), completed('[]'),
    b'data: [DONE]\n\n', completed()[:-2]])
def test_rejects_unfinished_or_invalid_stream_without_secret(data):
    mod = module()
    calls = []
    provider = mod.ChatGPTProvider('slug', lambda: SecretStr('wire-secret'), transport=httpx.MockTransport(
        lambda request: calls.append(request) or httpx.Response(200, stream=Wire(data))))
    with pytest.raises(ValueError) as exc:
        provider('rules', '{}')
    assert 'wire-secret' not in str(exc.value)
    assert len(calls) == 1


@pytest.mark.parametrize('status', [401, 403, 402, 429])
def test_auth_quota_errors_are_not_retried(status):
    mod = module()
    calls = []
    provider = mod.ChatGPTProvider('slug', lambda: SecretStr('wire-secret'), transport=httpx.MockTransport(
        lambda r: calls.append(r) or httpx.Response(status, text='wire-secret')))
    with pytest.raises(ValueError) as exc:
        provider('', '{}')
    assert 'wire-secret' not in str(exc.value)
    assert len(calls) == 1


def test_quota_after_text_is_failure():
    mod = module()
    data = event('response.output_text.delta', delta='{}') + event('response.failed', response={
        'error': {'code': 'subscription_sharing_usage_limit_exceeded', 'message': 'wire-secret'}})
    provider = mod.ChatGPTProvider('slug', lambda: SecretStr('wire-secret'), transport=httpx.MockTransport(
        lambda r: httpx.Response(200, stream=Wire(data))))
    with pytest.raises(ValueError, match='额度'):
        provider('', '{}')


def test_retry_before_output_refreshes_token(monkeypatch):
    mod = module()
    monkeypatch.setattr(mod, 'RETRY_DELAY', 0)
    tokens = []
    def token():
        tokens.append(1)
        return SecretStr(str(len(tokens)))
    def handle(request):
        assert request.headers['authorization'] == f'Bearer {len(tokens)}'
        return httpx.Response(503) if len(tokens) < 3 else httpx.Response(200, stream=Wire(completed()))
    assert mod.ChatGPTProvider('slug', token, transport=httpx.MockTransport(handle))('', '{}') == '{"ok":true}'
    assert len(tokens) == 3


def test_absolute_deadline_stops_drip_feed(monkeypatch):
    mod = module()
    monkeypatch.setattr(mod, 'TOTAL_TIMEOUT', .06)
    wire = Wire(completed(), delay=.02)
    provider = mod.ChatGPTProvider('slug', lambda: SecretStr('wire-secret'), transport=httpx.MockTransport(
        lambda r: httpx.Response(200, stream=wire)))
    start = time.monotonic()
    with pytest.raises(ValueError, match='超时'):
        provider('', '{}')
    assert time.monotonic() - start < .5
    assert wire.closed


def test_interrupted_output_is_not_retried():
    mod = module()
    calls = []
    provider = mod.ChatGPTProvider('slug', lambda: SecretStr('wire-secret'), transport=httpx.MockTransport(
        lambda r: calls.append(r) or httpx.Response(200, stream=Wire(event('response.output_text.delta', delta='{}'), interrupt=True))))
    with pytest.raises(ValueError):
        provider('', '{}')
    assert len(calls) == 1


def test_bounded_retries_and_stream_size(monkeypatch):
    mod = module()
    monkeypatch.setattr(mod, 'RETRY_DELAY', 0)
    calls = []
    provider = mod.ChatGPTProvider('slug', lambda: SecretStr('secret'), transport=httpx.MockTransport(
        lambda r: calls.append(r) or httpx.Response(503)))
    with pytest.raises(ValueError):
        provider('', '{}')
    assert len(calls) == 3
    monkeypatch.setattr(mod, 'MAX_STREAM_BYTES', 20)
    provider = mod.ChatGPTProvider('slug', lambda: SecretStr('secret'), transport=httpx.MockTransport(
        lambda r: httpx.Response(200, stream=Wire(completed()))))
    with pytest.raises(ValueError, match='上限'):
        provider('', '{}')


def test_total_deadline_includes_token_callback(monkeypatch):
    mod = module()
    monkeypatch.setattr(mod, 'TOTAL_TIMEOUT', .04)
    def token():
        time.sleep(.3)
        return SecretStr('secret')
    provider = mod.ChatGPTProvider('slug', token, transport=httpx.MockTransport(lambda r: pytest.fail('request after deadline')))
    start = time.monotonic()
    with pytest.raises(ValueError, match='超时'):
        provider('', '{}')
    assert time.monotonic() - start < .2


@pytest.mark.parametrize('text', ['{"bad":NaN}', '{"bad":Infinity}'])
def test_nonstandard_json_is_rejected(text):
    mod = module()
    provider = mod.ChatGPTProvider('slug', lambda: SecretStr('secret'), transport=httpx.MockTransport(
        lambda r: httpx.Response(200, stream=Wire(completed(text)))))
    with pytest.raises(ValueError):
        provider('', '{}')


def test_token_callback_exception_is_sanitized():
    mod = module()
    def token():
        raise ValueError('credential-secret')
    with pytest.raises(ValueError) as exc:
        mod.ChatGPTProvider('slug', token)('', '{}')
    assert 'credential-secret' not in str(exc.value)


# Observed public Responses shape: completed items precede an empty terminal output.
OBSERVED_ITEMS = [
    {'output_index': 0, 'item': {'type': 'reasoning', 'role': None, 'status': None, 'content': []}},
    {'output_index': 1, 'item': {'type': 'message', 'role': 'assistant', 'status': 'completed',
        'content': [{'type': 'output_text', 'annotations': [], 'logprobs': [],
                     'text': '{"candidate_id":2,"title":"解释“やりますね”的用法","reasons":["前文说明该表达是称赞对方的日语，随后补充提醒观众注意理解偏差，话题在此收束","73秒后转为回应观众评论，内容方向有所变化"]}'}]}},
]


def streamed_items(items=OBSERVED_ITEMS):
    return b''.join(event('response.output_item.done', **item) for item in items)


def empty_terminal(kind='response.completed', status='completed'):
    return event(kind, response={'status': status, 'output': []})


def from_wire(data):
    return module().ChatGPTProvider('slug', lambda: SecretStr('fake-test-token'),
        transport=httpx.MockTransport(lambda r: httpx.Response(200, stream=Wire(data))))('', '{}')


def test_observed_completed_items_with_empty_terminal_output():
    result = from_wire(streamed_items() + empty_terminal())
    assert result == OBSERVED_ITEMS[1]['item']['content'][0]['text']


def test_completed_items_assembled_in_output_index_order():
    items = [dict(OBSERVED_ITEMS[1], output_index=1, item=dict(OBSERVED_ITEMS[1]['item'],
        content=[{'type': 'output_text', 'text': 'true}'}])),
        dict(OBSERVED_ITEMS[1], output_index=0, item=dict(OBSERVED_ITEMS[1]['item'],
        content=[{'type': 'output_text', 'text': '{"ok":'}]))]
    assert json.loads(from_wire(streamed_items(items) + empty_terminal())) == {'ok': True}


@pytest.mark.parametrize('terminal', [b'', empty_terminal('response.failed', 'failed'),
    empty_terminal('response.incomplete', 'incomplete'), empty_terminal(status='in_progress')])
def test_done_items_never_replace_success_terminal(terminal):
    with pytest.raises(ValueError):
        from_wire(streamed_items() + terminal)


@pytest.mark.parametrize('change', ['status', 'role', 'gap', 'duplicate', 'negative', 'bool'])
def test_invalid_completed_items_rejected(change):
    items = json.loads(json.dumps(OBSERVED_ITEMS))
    if change == 'status':
        items[1]['item']['status'] = 'in_progress'
    elif change == 'role':
        items[1]['item']['role'] = 'user'
    elif change == 'gap':
        items[1]['output_index'] = 2
    elif change == 'duplicate':
        items.append(items[1])
    elif change == 'negative':
        items[1]['output_index'] = -1
    else:
        items[1]['output_index'] = True
    with pytest.raises(ValueError):
        from_wire(streamed_items(items) + empty_terminal())


def test_delta_only_not_promoted_to_completed_item():
    with pytest.raises(ValueError):
        from_wire(event('response.output_text.delta', delta='{"ok":true}') + empty_terminal())
