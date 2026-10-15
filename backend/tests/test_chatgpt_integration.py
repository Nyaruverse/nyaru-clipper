import json
import time

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.arctime.gui import create_app
from app.services.subtitles import SubtitleSegment, render_srt


def test_initial_subscription_state_is_safe_and_not_configured(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        response = client.get('/companion-api/config')
        value = response.json()
        assert value['llm_provider'] == 'deepseek'
        assert value['llm_model'] == 'deepseek-flash'
        assert value['llm_configured'] is False
        assert value['chatgpt']['connected'] is False
        assert value['chatgpt']['authorization_pending'] is False
        assert 'access_token' not in response.text
        assert 'refresh_token' not in response.text


def test_subscription_cannot_be_selected_without_plan_authorization(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        response = client.post('/companion-api/llm-config', json={'provider': 'chatgpt', 'model': 'account-model'})
        assert response.status_code == 409
        assert client.get('/companion-api/config').json()['llm_provider'] == 'deepseek'


def test_login_pending_status_survives_unrelated_callback(tmp_path):
    with TestClient(create_app(tmp_path), base_url='http://127.0.0.1') as client:
        assert client.post('/companion-api/chatgpt/login').status_code == 200
        assert client.get('/companion-api/chatgpt').json()['authorization_pending'] is True
        assert client.get('/auth/callback?state=unrelated&code=unused').status_code == 400
        assert client.get('/companion-api/chatgpt').json()['authorization_pending'] is True


def test_flash_settings_preserve_key_and_survive_restart(tmp_path):
    (tmp_path / 'config.json').write_text(json.dumps({'deepseek_api_key': 'test-private-key',
                                                   'deepseek_model': 'deepseek-flash'}))
    with TestClient(create_app(tmp_path)) as client:
        response = client.post('/companion-api/llm-config', json={'provider': 'deepseek', 'model': 'deepseek-flash'})
        assert response.status_code == 200
        assert 'test-private-key' not in response.text
    with TestClient(create_app(tmp_path)) as client:
        value = client.get('/companion-api/config').json()
        assert value['llm_configured'] is True
        assert value['llm_model'] == 'deepseek-flash'
    assert json.loads((tmp_path / 'config.json').read_text())['deepseek_api_key'] == 'test-private-key'
    assert (tmp_path / 'config.json').stat().st_mode & 0o777 == 0o600


def test_foreign_site_cannot_start_or_logout_subscription(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        for endpoint in ('login', 'logout'):
            response = client.post('/companion-api/chatgpt/' + endpoint, headers={'Origin': 'https://foreign.invalid'})
            assert response.status_code == 403


def test_invalid_callback_is_not_cached_and_never_echoes_code(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        response = client.get('/auth/callback?code=private-code&state=wrong&client_id=untrusted')
        assert response.status_code == 400
        assert 'private-code' not in response.text
        assert response.headers['cache-control'] == 'no-store'
        assert response.headers['referrer-policy'] == 'no-referrer'


def test_successful_callback_redirects_away_from_authorization_code(tmp_path, monkeypatch):
    from app.arctime.chatgpt_auth import ChatGPTAuth
    monkeypatch.setattr(ChatGPTAuth, 'complete', lambda self, **kwargs: None)
    with TestClient(create_app(tmp_path)) as client:
        response = client.get('/auth/callback?code=private-code&state=valid', follow_redirects=False)
        assert response.status_code == 303
        assert response.headers['location'] == '/auth/result'
        assert 'private-code' not in response.text
        result = client.get(response.headers['location'])
        assert result.status_code == 200 and 'Nyaru Clipper' in result.text
        assert result.headers['cache-control'] == 'no-store'


def test_pro_is_rejected_by_both_configuration_routes(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        assert client.post('/companion-api/translation-config', json={'model': 'deepseek-v4-pro'}).status_code == 422
        assert client.post('/companion-api/llm-config', json={'provider': 'deepseek', 'model': 'deepseek-v4-pro'}).status_code == 422


@pytest.mark.parametrize('active, checkpoint, expected', [
    (True, 'translating', 'translating'),
    (True, 'not_started', 'not_started'),
    (False, 'translating', 'interrupted'),
])
def test_live_translation_status_distinguishes_work_from_interruption(tmp_path, active, checkpoint, expected):
    from app.arctime.companion_manager import JobManager
    manager = JobManager(tmp_path, tmp_path / 'model.bin', 4)
    identity = 'abcdef012345'
    directory = tmp_path / identity
    directory.mkdir()
    (directory / 'job.json').write_text(json.dumps({'state': 'recording', 'live': True,
        'llm_provider': 'chatgpt', 'llm_model': 'chatgpt:test-model'}))
    (directory / 'translation.json').write_text(json.dumps({'state': checkpoint}))
    if active:
        manager.active = {'id': identity, 'state': 'recording', 'live': True, 'message': '正在补齐中日双语'}
    try:
        projected = manager.detail(identity)['translation']
        assert projected['state'] == expected
        if expected == 'translating':
            assert projected['message'] == '正在补齐中日双语'
    finally:
        manager.executor.shutdown()
        manager.chatgpt.close()


@pytest.fixture
def subscription_pipeline(tmp_path, monkeypatch):
    from app.arctime import chatgpt_provider, live_state, media
    from app.arctime.chatgpt_auth import ChatGPTAuth
    monkeypatch.setattr(ChatGPTAuth, 'status', lambda self: {'connected': True, 'sharing': True,
        'account_label': 'Test', 'error': None, 'manage_url': 'https://chatgpt.com/settings/usage'})
    monkeypatch.setattr(ChatGPTAuth, 'models', lambda self: [{'slug': 'subscription-model', 'display_name': 'Test model'}])
    monkeypatch.setattr(ChatGPTAuth, 'token', lambda self: SecretStr('test-subscription-credential'))
    calls = []

    def wire(request):
        assert request.url == 'https://api.openai.com/v1/responses'
        assert request.headers['authorization'] == 'Bearer test-subscription-credential'
        payload = json.loads(request.content)
        source = json.loads(payload['input'][0]['content'])
        if 'candidates' in source:
            result = {'candidate_id': source['candidates'][0]['id'], 'title': '话题结束', 'reasons': ['完整段落']}
            calls.append('cut')
        else:
            result = {'segments': [{'id': row['id'], 'zh': '你好，段落译文。'} for row in source['segments']]}
            calls.append('translate')
        event = {'type': 'response.completed', 'response': {'status': 'completed', 'output': [
            {'type': 'message', 'role': 'assistant', 'content': [{'type': 'output_text', 'text': json.dumps(result)}]}]}}
        return httpx.Response(200, text='data: ' + json.dumps(event) + '\n\n', headers={'content-type': 'text/event-stream'})

    original_provider = chatgpt_provider.ChatGPTProvider
    monkeypatch.setattr(chatgpt_provider, 'ChatGPTProvider', lambda model, token:
        original_provider(model, token, transport=httpx.MockTransport(wire)))

    class Adapter:
        def identity(self):
            return {'engine': 'subscription-wire-fixture'}

        def transcribe(self, path, directory, duration):
            return [SubtitleSegment(str(i), float(i), min(i + 9.5, duration), 'こんにちは、段落です。')
                    for i in range(0, int(duration), 10)]

    monkeypatch.setattr('app.arctime.companion_manager.LocalASR', lambda *args: Adapter())
    monkeypatch.setattr(media, 'probe_video', lambda path: 75. if path.name.startswith('chunk-') else 150.)

    def export(source, target, start, end, cues):
        target.write_bytes(b'video-clip')
        target.with_suffix('.srt').write_text(render_srt(media.clip_subtitles(cues, start, end)))

    monkeypatch.setattr(media, 'export_clip', export)
    monkeypatch.setattr(live_state, 'concatenate', lambda directory, chunks, target: target.write_bytes(b'joined-recording'))
    with TestClient(create_app(tmp_path)) as client:
        assert client.post('/companion-api/llm-config', json={'provider': 'chatgpt', 'model': 'subscription-model'}).status_code == 200
        yield client, calls


def await_job(client, identity, predicate):
    for _ in range(300):
        job = client.get('/companion-api/jobs/' + identity).json()
        if predicate(job):
            return job
        time.sleep(.01)
    pytest.fail('subscription pipeline did not reach expected state')


def test_subscription_upload_selects_cuts_and_publishes_bilingual_without_deepseek_key(subscription_pipeline, tmp_path):
    client, calls = subscription_pipeline
    response = client.post('/companion-api/saozi/upload?language=ja', content=b'local-recording')
    assert response.status_code == 202
    identity = response.json()['id']
    job = await_job(client, identity, lambda j: j['translation']['state'] in {'completed', 'failed'})
    assert job['translation']['state'] == 'completed', job
    assert job['llm_provider'] == 'chatgpt'
    assert job['saozi_model'] == job['translation']['model'] == 'chatgpt:subscription-model'
    assert len(job['clips']) == 2
    assert calls == ['cut', 'translate']
    assert all(60 <= clip['end'] - clip['start'] <= 120 for clip in job['clips'])
    for clip in job['clips']:
        subtitle = client.get('/companion-api/jobs/' + identity + '/files/' + clip['bilingual_subtitles'])
        assert 'こんにちは' in subtitle.text and '段落译文' in subtitle.text
        assert subtitle.content == (tmp_path / identity / clip['bilingual_subtitles']).read_bytes()
    assert (tmp_path / identity / 'source.mp4').read_bytes() == b'local-recording'
    assert 'test-subscription-credential' not in json.dumps(job)
    assert 'test-subscription-credential' not in (tmp_path / identity / 'translation.json').read_text()


def test_subscription_live_publishes_downloadable_bilingual_before_stop(subscription_pipeline, monkeypatch):
    client, calls = subscription_pipeline

    class Capture:
        error = None

        def __init__(self, url, directory, stop):
            self.directory, self.stop = directory, stop

        def chunks(self):
            folder = self.directory / 'capture-0000'
            folder.mkdir()
            for index in range(2):
                path = folder / f'chunk-{index:05d}.mp4'
                path.write_bytes(b'closed-chunk')
                yield path
            assert self.stop.wait(5)

        def close(self):
            self.stop.set()

        @staticmethod
        def recorded(directory):
            return list(directory.glob('capture-*/*.mp4'))

    monkeypatch.setattr('app.arctime.saozi_live.LiveCapture', Capture)
    response = client.post('/companion-api/jobs', json={'url': 'https://live.bilibili.com/545068',
                                                       'saozi': True, 'live': True, 'language': 'ja'})
    assert response.status_code == 202
    identity = response.json()['id']
    early = await_job(client, identity, lambda j: bool(j['clips']) and bool(j['clips'][0]['bilingual_subtitles']))
    assert early['state'] == 'recording' and early['can_stop']
    name = early['clips'][0]['bilingual_subtitles']
    assert '段落译文' in client.get('/companion-api/jobs/' + identity + '/files/' + name).text
    assert client.post('/companion-api/chatgpt/logout').status_code == 409
    assert client.post('/companion-api/jobs/' + identity + '/stop').status_code == 202
    final = await_job(client, identity, lambda j: j['state'] == 'completed' and j['translation']['state'] == 'completed')
    assert len(final['clips']) == 2
    assert all(clip['bilingual_subtitles'] for clip in final['clips'])
    assert calls == ['cut', 'translate']


@pytest.fixture
def legacy_manager(tmp_path, monkeypatch):
    from app.arctime.companion_manager import JobManager
    manager = JobManager(tmp_path, tmp_path / 'unused-model', 1)
    manager.llm_provider = 'chatgpt'
    manager.chatgpt_model = 'new-default'
    manager.api_key = SecretStr('synthetic-flash-key')
    monkeypatch.setattr(manager.chatgpt, 'status', lambda: {'connected': True, 'sharing': True})
    submitted = []
    monkeypatch.setattr(manager.executor, 'submit', lambda fn, *args: submitted.append((fn, args)))
    identity = 'abcdef012345'
    directory = tmp_path / identity
    directory.mkdir()
    (directory / 'job.json').write_text(json.dumps({'state': 'completed', 'video': 'source.mp4',
                                                  'saozi': True, 'completed_clips': []}))
    yield manager, identity, directory, submitted
    manager.executor.shutdown(wait=True)
    manager.chatgpt.close()


def test_legacy_projection_ignores_current_subscription_default(legacy_manager):
    manager, identity, _, _ = legacy_manager
    detail = manager.detail(identity)
    assert detail['translation']['model'] == 'deepseek-flash'
    assert detail['llm_provider'] == 'deepseek'


@pytest.mark.parametrize('saved', [{}, {'llm_model': 'chatgpt:saved-model'}, {'saozi_model': 'chatgpt:saved-model'}])
def test_resume_uses_saved_identity_or_legacy_flash(legacy_manager, monkeypatch, saved):
    from app.arctime import saozi_translation, workflow
    manager, identity, directory, submitted = legacy_manager
    job = json.loads((directory / 'job.json').read_text())
    job.update(saved)
    (directory / 'job.json').write_text(json.dumps(job))
    expected = 'chatgpt:saved-model' if saved else 'deepseek-flash'
    manager.submit(None, identity)
    _, args = submitted.pop()
    assert args[-1] == expected
    seen = []
    monkeypatch.setattr(workflow, 'resume_run', lambda path, adapter, *, progress, selector:
                        (seen.append(selector.model) or job))
    monkeypatch.setattr(saozi_translation, 'translate', lambda path, key, **kwargs: seen.append(kwargs['model']))
    manager.run(*args)
    assert seen == [expected, expected]


@pytest.mark.parametrize('saved,checkpoint,expected', [
    ({}, {}, 'deepseek-flash'),
    ({'llm_model': 'chatgpt:saved-model'}, {}, 'chatgpt:saved-model'),
    ({'saozi_model': 'chatgpt:saved-model'}, {}, 'chatgpt:saved-model'),
    ({}, {'state': 'failed', 'identity': {'model': 'chatgpt:checkpoint-model'}}, 'chatgpt:checkpoint-model'),
])
def test_translation_uses_saved_identity_or_checkpoint_or_legacy_flash(legacy_manager, monkeypatch, saved, checkpoint, expected):
    from app.arctime import saozi_translation
    manager, identity, directory, submitted = legacy_manager
    job = json.loads((directory / 'job.json').read_text()); job.update(saved)
    (directory / 'job.json').write_text(json.dumps(job))
    if checkpoint:
        (directory / 'translation.json').write_text(json.dumps(checkpoint))
    manager.submit_translation(identity)
    _, args = submitted.pop()
    assert args[-1] == expected
    seen = []
    monkeypatch.setattr(saozi_translation, 'translate', lambda path, key, **kwargs: seen.append(kwargs['model']))
    manager.run_translation(*args)
    assert seen == [expected]


def test_new_request_keeps_current_subscription_default(legacy_manager):
    from app.arctime.companion_models import JobInput
    manager, _, _, submitted = legacy_manager
    identity = manager.submit(JobInput(url='https://example.test/video', saozi=True))
    assert identity != 'abcdef012345'
    _, args = submitted.pop()
    assert args[-1] == 'chatgpt:new-default'
