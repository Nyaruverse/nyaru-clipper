import json

import httpx
import pytest
from pydantic import SecretStr

from app.arctime import media, saozi, saozi_translation, translation, workflow
from app.services.subtitles import SubtitleSegment, render_srt


def source(directory):
    cues = [SubtitleSegment(str(i), i * 30, i * 30 + 30, 'こんにちは') for i in range(5)]
    (directory / 'subtitles.srt').write_text(render_srt(cues))
    workflow.write_manifest(directory, {'version': 2, 'state': 'completed', 'subtitles': 'subtitles.srt',
        'artifacts': {'subtitles.srt': media.fingerprint(directory / 'subtitles.srt')},
        'completed_clips': [], 'selection': []})
    return cues


def translate_json(prompt, text):
    return json.dumps({'segments': [{'id': row['id'], 'zh': '你好'} for row in json.loads(text)['segments']]})


@pytest.mark.parametrize('run', [translation.translate_run, saozi_translation.translate])
def test_injected_translation_keeps_timings_and_isolates_cache(tmp_path, run):
    cues = source(tmp_path)
    original = (tmp_path / 'subtitles.srt').read_bytes()
    with httpx.Client(transport=httpx.MockTransport(lambda r: pytest.fail('DeepSeek network forbidden'))) as client:
        state = run(tmp_path, SecretStr(''), model='chatgpt:slug', request_json=translate_json, client=client)
        assert state['state'] == 'completed'
        assert state['identity']['model'] == 'chatgpt:slug'
        before = (tmp_path / 'translation.json').read_bytes()
        with pytest.raises(ValueError, match='缓存'):
            run(tmp_path, SecretStr('key'), client=client)
        assert (tmp_path / 'translation.json').read_bytes() == before
    assert (tmp_path / 'subtitles.srt').read_bytes() == original
    result = media.read_subtitles(tmp_path / 'subtitles.ja-zh.srt')
    assert [(c.start_seconds, c.end_seconds) for c in result] == [(c.start_seconds, c.end_seconds) for c in cues]
    assert all(c.text == 'こんにちは\n你好' for c in result)


@pytest.mark.parametrize('model', ['deepseek-v4-pro', 'chatgpt:slug'])
def test_reject_model_without_callback_before_network(tmp_path, model):
    with httpx.Client(transport=httpx.MockTransport(lambda r: pytest.fail('network forbidden'))) as client:
        for run in (translation.translate_run, saozi_translation.translate):
            with pytest.raises(ValueError):
                run(tmp_path, SecretStr('key'), model=model, client=client)
        with pytest.raises(ValueError):
            saozi.SaoziSelector(SecretStr('key'), model, client=client)
        with pytest.raises(ValueError):
            translation._request(client, SecretStr('key'), [], 0, model)


def test_pro_cannot_use_callback(tmp_path):
    for run in (translation.translate_run, saozi_translation.translate):
        with pytest.raises(ValueError):
            run(tmp_path, SecretStr('key'), model='deepseek-v4-pro', request_json=lambda *a: pytest.fail('called'))
    assert translation.MODELS == ('deepseek-flash',)


@pytest.mark.parametrize('value', ['{}', '{"candidate_id":999,"title":"x","reasons":["x"]}',
    '{"candidate_id":true,"title":"x","reasons":["x"]}'])
def test_selector_injection_still_validates_candidates(tmp_path, value):
    cues = source(tmp_path)
    selector = saozi.SaoziSelector(SecretStr(''), 'chatgpt:slug', request_json=lambda *a: value)
    with pytest.raises(ValueError):
        selector.choose(cues, 0, 150)


def test_selector_injection_and_cache_identity(tmp_path):
    cues = source(tmp_path)
    calls = []
    def request(prompt, text):
        calls.append(json.loads(text))
        return '{"candidate_id":1,"title":"主题","reasons":["结束"]}'
    selector = saozi.SaoziSelector(SecretStr(''), 'chatgpt:slug', request_json=request)
    result = selector.plan(tmp_path, cues, 150)
    assert result[0]['end'] == 60 and len(calls) == 1
    assert selector.plan(tmp_path, cues, 150) == result and len(calls) == 1
    before = (tmp_path / 'saozi.json').read_bytes()
    with pytest.raises(ValueError, match='缓存'):
        saozi.SaoziSelector(SecretStr('key'), 'deepseek-flash').plan(tmp_path, cues, 150)
    assert (tmp_path / 'saozi.json').read_bytes() == before


@pytest.mark.parametrize('run', [translation.translate_run, saozi_translation.translate])
def test_injected_bad_rows_do_not_publish(tmp_path, run):
    source(tmp_path)
    with pytest.raises(ValueError):
        run(tmp_path, SecretStr(''), model='chatgpt:slug', request_json=lambda *a: '{"segments":[]}')
    assert not (tmp_path / 'subtitles.ja-zh.srt').exists()


def test_saozi_resumes_v1_chatgpt_checkpoint_with_injection(tmp_path, monkeypatch):
    source(tmp_path)
    monkeypatch.setattr(translation, 'BATCH_SIZE', 2)
    calls = []
    def interrupted(prompt, text):
        calls.append(text)
        if len(calls) == 2:
            raise ValueError('ChatGPT temporary failure')
        return translate_json(prompt, text)
    with pytest.raises(ValueError):
        translation.translate_run(tmp_path, SecretStr(''), model='chatgpt:slug', request_json=interrupted)
    state = saozi_translation.translate(tmp_path, SecretStr(''), model='chatgpt:slug', request_json=translate_json)
    assert state['state'] == 'completed' and state['identity']['version'] == 1
    assert len(state['batches']) == 3


def test_flash_identity_remains_legacy_shape(tmp_path):
    import hashlib
    source(tmp_path)
    def respond(request):
        payload = json.loads(request.content)
        text = translate_json('', payload['messages'][1]['content'])
        return httpx.Response(200, json={'choices': [{'finish_reason': 'stop', 'message': {'content': text}}]})
    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        state = translation.translate_run(tmp_path, SecretStr('key'), client=client)
    assert state['identity'] == {'version': 1, 'source_sha256': media.fingerprint(tmp_path / 'subtitles.srt'),
        'model': 'deepseek-flash', 'prompt_sha256': hashlib.sha256(translation.PROMPT.encode()).hexdigest(),
        'batch_size': translation.BATCH_SIZE}
