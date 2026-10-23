from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
from fastapi import HTTPException
from pydantic import SecretStr

from app.arctime import cli, saozi_translation, workflow
from app.arctime.chatgpt_auth import ChatGPTAuth
from app.arctime.chatgpt_provider import ChatGPTProvider
from app.arctime.companion_manager import JobManager
from app.arctime.companion_models import JobInput
from app.arctime.local_asr import LocalASR
from app.services.subtitles import SubtitleSegment, render_srt


@pytest.fixture
def provider_root(tmp_path, monkeypatch):
    (tmp_path / 'config.json').write_text(json.dumps({
        'deepseek_api_key': 'synthetic-residual-key', 'deepseek_model': 'deepseek-flash',
        'llm_provider': 'chatgpt', 'chatgpt_model': 'current-model',
    }))
    monkeypatch.setattr(ChatGPTAuth, 'status', lambda self: {'connected': True, 'sharing': True})
    monkeypatch.setattr(ChatGPTAuth, 'token', lambda self: SecretStr('synthetic-token'))
    monkeypatch.setattr(LocalASR, 'identity', lambda self: {
        'model': 'synthetic.bin', 'language': 'ja', 'threads': 1,
    })
    return tmp_path


@pytest.mark.parametrize(('current', 'saved_model', 'expected'), [
    ('chatgpt', {}, 'chatgpt:current-model'),
    ('chatgpt', {'saozi_model': 'deepseek-flash'}, 'deepseek-flash'),
    ('chatgpt', {'saozi_model': 'chatgpt:old-model'}, 'chatgpt:old-model'),
    ('chatgpt', {'llm_model': 'chatgpt:other-model'}, 'chatgpt:other-model'),
    ('deepseek', {'saozi_model': 'chatgpt:old-model'}, 'chatgpt:old-model'),
])
def test_cli_gui_resume_select_same_pinned_or_current_model(provider_root, monkeypatch, current, saved_model, expected):
    config = json.loads((provider_root / 'config.json').read_text())
    config['llm_provider'] = current
    (provider_root / 'config.json').write_text(json.dumps(config))
    directory = provider_root / 'aaaaaaaaaaaa'
    directory.mkdir()
    saved = {'saozi': True, 'state': 'completed', 'completed_clips': [], **saved_model}
    workflow.write_manifest(directory, saved)
    original = (directory / 'job.json').read_bytes()
    selected = []

    def resume(path, *, selector, **kwargs):
        selected.append(selector.model)
        assert bool(selector.request_json) == expected.startswith('chatgpt:')
        return saved

    monkeypatch.setattr(workflow, 'resume_run', resume)
    monkeypatch.setattr(saozi_translation, 'translate', lambda *args, **kwargs: None)
    manager = JobManager(provider_root, Path('synthetic.bin'), 1)
    try:
        manager.submit(None, directory.name, deferred=True)
        assert cli.main(['resume', str(directory)]) == 0
        assert selected == [manager.active['model']] == [expected]
        assert (directory / 'job.json').read_bytes() == original
    finally:
        manager.executor.shutdown()
        manager.chatgpt.close()


@pytest.mark.parametrize('failure', ['disconnected', 'no-sharing', 'unsupported-config', 'unsupported-task'])
def test_cli_gui_reject_unavailable_provider_without_old_key_fallback(provider_root, monkeypatch, capsys, failure):
    directory = provider_root / 'aaaaaaaaaaaa'
    directory.mkdir()
    saved = {'saozi': True}
    if failure == 'unsupported-task':
        saved['saozi_model'] = 'unknown:model'
    elif failure == 'unsupported-config':
        config = json.loads((provider_root / 'config.json').read_text())
        config['llm_provider'] = 'unsupported'
        (provider_root / 'config.json').write_text(json.dumps(config))
    else:
        monkeypatch.setattr(ChatGPTAuth, 'status', lambda self: {
            'connected': failure != 'disconnected', 'sharing': failure != 'no-sharing',
        })
    workflow.write_manifest(directory, saved)
    original = (directory / 'job.json').read_bytes()
    monkeypatch.setattr(workflow, 'resume_run', lambda *args, **kwargs: pytest.fail('processing started'))
    manager = JobManager(provider_root, Path('synthetic.bin'), 1)
    try:
        with pytest.raises(HTTPException) as error:
            manager.submit(None, directory.name, deferred=True)
        assert error.value.status_code == 409
        assert cli.main(['resume', str(directory)]) == 1
        assert (directory / 'job.json').read_bytes() == original
        assert 'synthetic-residual-key' not in capsys.readouterr().err
    finally:
        manager.executor.shutdown()
        manager.chatgpt.close()


def test_cli_run_uses_subscription_for_selection_and_translation(provider_root, monkeypatch):
    selected = []
    translated = []

    def download(url, directory):
        saved = json.loads((directory / 'job.json').read_text())
        assert saved['llm_model'] == 'chatgpt:current-model'
        path = directory / 'source.mp4'
        path.write_bytes(b'synthetic-video')
        return path

    def resume(directory, *, selector, **kwargs):
        selected.append(selector)
        return {'saozi': True, 'state': 'completed', 'completed_clips': []}

    def translate(directory, key, *, model, request_json, **kwargs):
        assert key.get_secret_value() == ''
        assert model == 'chatgpt:current-model'
        assert request_json is selected[0].request_json
        assert isinstance(request_json, ChatGPTProvider)
        def response(request):
            assert json.loads(request.content)['model'] == 'current-model'
            event = {'type': 'response.completed', 'response': {'status': 'completed', 'output': [
                {'type': 'message', 'role': 'assistant', 'content': [
                    {'type': 'output_text', 'text': '{"translated":true}'},
                ]},
            ]}}
            return httpx.Response(200, text='data: ' + json.dumps(event) + '\n\n')
        request_json.transport = httpx.MockTransport(response)
        translated.append(json.loads(request_json('synthetic instructions', '{}')))

    monkeypatch.setattr(workflow.media, 'download_video', download)
    monkeypatch.setattr(workflow.media, 'probe_video', lambda path: 10.0)
    monkeypatch.setattr(workflow, 'resume_run', resume)
    monkeypatch.setattr(saozi_translation, 'translate', translate)
    assert cli.main(['run', 'https://example.org/video', '--saozi', '--output-dir', str(provider_root)]) == 0
    assert len(selected) == 1
    assert translated == [{'translated': True}]


@pytest.mark.parametrize('surface', ['cli', 'gui'])
def test_download_failure_keeps_selected_model_before_preferences_change(provider_root, monkeypatch, surface):
    def fail_download(url, directory):
        raise OSError('synthetic download failure')

    monkeypatch.setattr(workflow.media, 'download_video', fail_download)
    manager = JobManager(provider_root, Path('synthetic.bin'), 1)
    try:
        if surface == 'cli':
            assert cli.main(['run', 'https://example.org/video', '--saozi', '--output-dir', str(provider_root)]) == 1
        else:
            request = JobInput(url='https://example.org/video', saozi=True)
            job_id = manager.submit(request, deferred=True)
            manager.run(job_id, request, SecretStr(''), manager.active['model'])
        directory = next(path.parent for path in provider_root.glob('*/job.json'))
        saved = json.loads((directory / 'job.json').read_text())
        assert saved['state'] == 'download_failed'
        assert saved['llm_model'] == 'chatgpt:current-model'
        assert saved['llm_provider'] == 'chatgpt'
        config = json.loads((provider_root / 'config.json').read_text())
        config.update(llm_provider='deepseek', chatgpt_model='different-model')
        (provider_root / 'config.json').write_text(json.dumps(config))
        observed = []
        def resume(path, *, selector, **kwargs):
            observed.append(selector.model)
            return {'state': 'completed', 'completed_clips': []}
        monkeypatch.setattr(workflow, 'resume_run', resume)
        assert cli.main(['resume', str(directory)]) == 0
        assert observed == ['chatgpt:current-model']
        assert json.loads((directory / 'job.json').read_text()) == saved
    finally:
        manager.executor.shutdown()
        manager.chatgpt.close()


@pytest.mark.parametrize('surface', ['cli', 'gui'])
def test_legacy_resume_pins_current_model_before_asr_failure(provider_root, monkeypatch, surface):
    source = provider_root / 'input.mp4'
    source.write_bytes(b'original-media')
    monkeypatch.setattr(workflow.media, 'probe_video', lambda path: 10.0)
    directory = workflow.create_run('', provider_root, [], None, saozi=True, local_source=source)
    observed = []

    def fail_asr(self, video, directory, duration):
        saved = json.loads((directory / 'job.json').read_text())
        observed.append((saved.get('llm_model'), saved.get('llm_provider')))
        raise RuntimeError('synthetic ASR failure')

    monkeypatch.setattr(LocalASR, 'transcribe', fail_asr)
    manager = JobManager(provider_root, Path('synthetic.bin'), 1)
    try:
        if surface == 'cli':
            assert cli.main(['resume', str(directory)]) == 1
        else:
            manager.submit(None, directory.name, deferred=True)
            manager.run(directory.name, None, SecretStr(''), manager.active['model'])
        assert observed == [('chatgpt:current-model', 'chatgpt')]
        assert source.read_bytes() == (directory / 'source.mp4').read_bytes() == b'original-media'
    finally:
        manager.executor.shutdown()
        manager.chatgpt.close()


def test_legacy_translation_saves_model_before_scheduling(provider_root, monkeypatch):
    directory = provider_root / 'aaaaaaaaaaaa'
    directory.mkdir()
    workflow.write_manifest(directory, {'state': 'completed', 'completed_clips': []})
    manager = JobManager(provider_root, Path('synthetic.bin'), 1)
    monkeypatch.setattr(manager, 'detail', lambda job_id: {
        'state': 'completed', 'translation': {'state': 'not_started'},
    })
    observed = []
    monkeypatch.setattr(manager.executor, 'submit', lambda *args: observed.append(
        json.loads((directory / 'job.json').read_text()).get('llm_model')))
    try:
        manager.submit_translation(directory.name)
        assert observed == ['chatgpt:current-model']
    finally:
        manager.executor.shutdown()
        manager.chatgpt.close()


@pytest.mark.parametrize('mode', ['ranges', 'highlights'])
@pytest.mark.parametrize('config_text', ['{broken', '{"deepseek_api_key":"synthetic-residual-key","llm_provider":"unsupported"}'],
                         ids=['broken-json', 'unsupported-provider'])
def test_local_modes_ignore_broken_llm_config_but_translation_rejects(provider_root, monkeypatch, mode, config_text):
    (provider_root / 'config.json').write_text(config_text)
    source = provider_root / 'input.mp4'
    source.write_bytes(b'original-video')
    monkeypatch.setattr(workflow.media, 'probe_video', lambda path: 10.0)
    monkeypatch.setattr(LocalASR, 'transcribe', lambda *args: [SubtitleSegment('1', 0, 3, '哈哈！太强了！哈哈！')])
    monkeypatch.setattr(ChatGPTAuth, 'status', lambda self: pytest.fail('LLM authorization reached'))

    def export(video, target, start, end, cues):
        target.write_bytes(b'synthetic-clip')
        target.with_suffix('.srt').write_text(render_srt(workflow.media.clip_subtitles(cues, start, end)))

    monkeypatch.setattr(workflow.media, 'export_clip', export)
    request = JobInput(url='https://example.org/video', ranges=[('0', '1')]) if mode == 'ranges' else JobInput(
        url='https://example.org/video', highlights=1)
    manager = JobManager(provider_root, Path('synthetic.bin'), 1)
    try:
        assert manager.config_error
        job_id = manager.submit(request, deferred=True)
        manager.run(job_id, request, manager.api_key, manager.active['model'], local_source=source)
        directory = manager.directory(job_id)
        saved = json.loads((directory / 'job.json').read_text())
        assert saved['state'] == 'completed'
        assert 'llm_model' not in saved and 'llm_provider' not in saved
        assert saved['completed_clips']
        manager.submit(None, job_id, deferred=True)
        manager.run(job_id, None, manager.api_key, manager.active['model'])
        assert manager.last['state'] == 'completed'
        original = (directory / 'job.json').read_bytes()
        with pytest.raises(HTTPException) as translation_error:
            manager.submit_translation(job_id)
        assert translation_error.value.status_code == 409
        with pytest.raises(HTTPException) as saozi_error:
            manager.submit(JobInput(url='https://example.org/video', saozi=True), deferred=True)
        assert saozi_error.value.status_code == 409
        assert manager.active is None
        assert (directory / 'job.json').read_bytes() == original
        assert source.read_bytes() == b'original-video'
    finally:
        manager.executor.shutdown()
        manager.chatgpt.close()
