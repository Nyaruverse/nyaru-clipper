from __future__ import annotations

import importlib
import json
from pathlib import Path

import httpx
import pytest
from pydantic import SecretStr

from app.services.subtitles import SubtitleSegment


@pytest.fixture
def module(monkeypatch):
    assert importlib.util.find_spec('app.arctime.saozi') is not None, 'semantic selector is missing'
    module = importlib.import_module('app.arctime.saozi')
    monkeypatch.setattr(module.time, 'sleep', lambda _: None)
    return module


def cues(duration=305):
    return [SubtitleSegment(str(i), i * 10, min(i * 10 + 10, duration), f'段落 {i}。')
            for i in range((duration + 9) // 10)]


def reply(payload=None, status=200):
    return httpx.Response(status, json={'choices': [{'finish_reason': 'stop', 'message': {
        'content': json.dumps(payload or {'candidate_id': 1, 'title': '话题', 'reasons': ['话题收束']})}}]})


def selector(module, handler):
    return module.SaoziSelector(SecretStr('test-secret'), 'deepseek-flash',
                               httpx.Client(transport=httpx.MockTransport(handler)))


def test_contiguous_coverage_and_short_tail(module, tmp_path):
    calls = []
    instance = selector(module, lambda request: calls.append(request) or reply())
    result = instance.plan(tmp_path, cues(), 305)
    assert result[0]['start'] == 0 and result[-1]['end'] == 305
    assert all(a['end'] == b['start'] for a, b in zip(result, result[1:]))
    assert all(60 <= row['end'] - row['start'] <= 120 for row in result[:-1])
    assert len(calls) == 4
    assert instance.choose(cues(40), 0, 40)['end'] == 40
    assert '尾段' in ' '.join(instance.choose(cues(40), 0, 40)['reasons'])
    assert all(row['score'] is None for row in result)


def test_candidates_exclude_overlaps_and_include_only_20_seconds_context(module):
    rows = [SubtitleSegment('a', 0, 70, '一'), SubtitleSegment('b', 65, 90, '二'),
            SubtitleSegment('c', 90, 120, '三'), SubtitleSegment('d', 125, 135, '后文'),
            SubtitleSegment('e', 150, 160, '不应发送')]
    requests = []
    instance = selector(module, lambda request: requests.append(json.loads(request.content)) or reply())
    assert instance.choose(rows, 0, 200)['end'] == 90
    request = requests[0]
    data = json.loads(request['messages'][1]['content'])
    assert [c['end'] for c in data['candidates']] == [90, 120]
    assert '不应发送' not in request['messages'][1]['content']
    assert '后文' in request['messages'][1]['content']
    assert request['model'] == 'deepseek-flash'
    assert request['response_format'] == {'type': 'json_object'}
    assert request['thinking'] == {'type': 'disabled'}


def test_live_waits_for_full_buffer(module):
    calls = []
    instance = selector(module, lambda request: calls.append(request) or reply())
    assert instance.choose(cues(), 60, 199, final=False) is None
    assert not calls
    assert instance.choose(cues(), 60, 200, final=False)['start'] == 60
    assert len(calls) == 1


def test_long_utterance_and_silence_keep_coverage_without_api(module, tmp_path):
    def no_api(request):
        pytest.fail('no candidate should not call API')
    instance = selector(module, no_api)
    long = [SubtitleSegment('long', 0, 310, '长句')]
    result = instance.choose(long, 0, 310)
    assert result['end'] == 120 and '受限' in ' '.join(result['reasons'])
    silent = instance.plan(tmp_path, [], 305)
    assert [(s['start'], s['end']) for s in silent] == [(0, 120), (120, 240), (240, 305)]
    assert all('无语音' in ' '.join(s['reasons']) for s in silent)


@pytest.mark.parametrize('payload', [
    {'candidate_id': 999, 'title': 'x', 'reasons': ['x']},
    {'candidate_id': True, 'title': 'x', 'reasons': ['x']},
    {'candidate_id': '1', 'title': 'x', 'reasons': ['x']},
    {'candidate_id': 1, 'title': '', 'reasons': ['x']},
    {'candidate_id': 1, 'title': 'x', 'reasons': []},
    {'candidate_id': 1, 'title': 'x', 'reasons': ['x'], 'end': 999},
])
def test_rejects_invalid_model_choices(module, payload):
    instance = selector(module, lambda request: reply(payload))
    with pytest.raises(ValueError, match='DeepSeek'):
        instance.choose(cues(), 0, 305)


def test_network_failure_retries_and_sanitizes(module):
    calls = []
    def fail(request):
        calls.append(request)
        raise httpx.ConnectError('test-secret response body', request=request)
    instance = selector(module, fail)
    with pytest.raises(ValueError) as caught:
        instance.choose(cues(), 0, 305)
    assert len(calls) == 3
    assert 'test-secret' not in str(caught.value)
    assert '网络' in str(caught.value)


@pytest.mark.parametrize('status', [401, 402, 403, 429, 500])
def test_http_failure_sanitized(module, status):
    calls = []
    instance = selector(module, lambda request: calls.append(request) or httpx.Response(status, text='test-secret'))
    with pytest.raises(ValueError) as caught:
        instance.choose(cues(), 0, 305)
    assert 'test-secret' not in str(caught.value)
    assert len(calls) == (3 if status in {429, 500} else 1)


def test_prefix_survives_failure_and_completed_calls_are_reused(module, tmp_path):
    calls = []
    instance = selector(module, lambda request: calls.append(request) or (reply() if len(calls) == 1 else reply(status=402)))
    with pytest.raises(ValueError):
        instance.plan(tmp_path, cues(), 305)
    saved = json.loads((tmp_path / 'saozi.json').read_text())
    assert saved['state'] == 'failed' and len(saved['selection']) == 1
    prefix = saved['selection'][0]
    resumed_calls = []
    resumed = selector(module, lambda request: resumed_calls.append(request) or reply())
    result = resumed.plan(tmp_path, cues(), 305)
    assert result[0] == prefix and len(resumed_calls) == 3
    assert resumed.plan(tmp_path, cues(), 305) == result
    assert len(resumed_calls) == 3
    assert not resumed.client.is_closed


@pytest.mark.parametrize('change', ['subtitle', 'model', 'duration', 'prompt', 'gap', 'hash', 'incomplete', 'shape'])
def test_corrupt_or_mismatched_cache_rejected_without_overwrite(module, tmp_path, change, monkeypatch):
    instance = selector(module, lambda request: reply())
    instance.plan(tmp_path, cues(), 305)
    path = tmp_path / 'saozi.json'
    saved = json.loads(path.read_text())
    rows, duration = cues(), 305
    if change == 'subtitle':
        rows[0].text = 'different'
    elif change == 'model':
        instance.model = 'deepseek-v4-pro'
    elif change == 'duration':
        duration = 306
    elif change == 'prompt':
        monkeypatch.setattr(module, 'PROMPT', module.PROMPT + ' changed')
    elif change == 'gap':
        saved['selection'][1]['start'] += 1
    elif change == 'hash':
        saved['selection'][0]['title'] = 'corrupted'
    elif change == 'incomplete':
        saved['selection'].pop()
    else:
        saved = []
    path.write_text(json.dumps(saved))
    before = path.read_bytes()
    with pytest.raises(ValueError):
        instance.plan(tmp_path, rows, duration)
    assert path.read_bytes() == before


@pytest.mark.parametrize('start,duration', [(-1, 200), (0, float('nan')), (0, float('inf')), (201, 200)])
def test_invalid_time_rejected(module, start, duration):
    instance = selector(module, lambda request: reply())
    with pytest.raises(ValueError):
        instance.choose(cues(), start, duration)


def test_semantic_selector_is_available():
    assert importlib.util.find_spec('app.arctime.saozi') is not None, 'semantic selector is missing'


@pytest.mark.parametrize('response', [
    httpx.Response(200, text='not JSON test-secret'),
    httpx.Response(200, json={'choices': []}),
    httpx.Response(200, json={'choices': [{'finish_reason': 'length', 'message': {'content': 'test-secret'}}]}),
    httpx.Response(200, json={'choices': [{'finish_reason': 'stop', 'message': {'content': '{}'}}]}),
])
def test_malformed_responses_are_sanitized(module, response):
    instance = selector(module, lambda request: response)
    with pytest.raises(ValueError) as caught:
        instance.choose(cues(), 0, 305)
    assert 'test-secret' not in str(caught.value)
    assert 'DeepSeek' in str(caught.value)


@pytest.mark.parametrize('fail', [False, True])
def test_owned_client_closed_after_success_and_failure(module, monkeypatch, fail):
    owned = httpx.Client(transport=httpx.MockTransport(lambda request: reply(status=402) if fail else reply()))
    monkeypatch.setattr(module.httpx, 'Client', lambda **kwargs: owned)
    instance = module.SaoziSelector(SecretStr('test-secret'), 'deepseek-flash')
    if fail:
        with pytest.raises(ValueError):
            instance.choose(cues(), 0, 305)
    else:
        assert instance.choose(cues(), 0, 305)['end'] == 60
    assert owned.is_closed


def test_transient_http_retry_succeeds(module):
    calls = []
    instance = selector(module, lambda request: calls.append(request) or reply(status=503 if len(calls) < 3 else 200))
    assert instance.choose(cues(), 0, 305)['end'] == 60
    assert len(calls) == 3


def test_cache_structural_validation_independent_of_digest(module, tmp_path):
    instance = selector(module, lambda request: reply())
    instance.plan(tmp_path, cues(), 305)
    path = tmp_path / 'saozi.json'
    saved = json.loads(path.read_text())
    saved['selection'][0]['end'] = 65
    saved['selection'][1]['start'] = 65
    saved['selection_sha256'] = module._digest(saved['selection'])
    path.write_text(json.dumps(saved))
    before = path.read_bytes()
    with pytest.raises(ValueError, match='缓存'):
        instance.plan(tmp_path, cues(), 305)
    assert path.read_bytes() == before


def test_symlink_cache_rejected(module, tmp_path):
    target = tmp_path / 'untouched.json'
    target.write_text('original')
    (tmp_path / 'saozi.json').symlink_to(target)
    instance = selector(module, lambda request: reply())
    with pytest.raises(ValueError):
        instance.plan(tmp_path, cues(), 305)
    assert target.read_text() == 'original'
