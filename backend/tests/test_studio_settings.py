import json
import stat

import pytest
from fastapi.testclient import TestClient
from app.arctime.gui import create_app
from app.arctime.subtitle_style import SubtitleStyle
from app.arctime.subtitle_templates import TemplateStore


def test_template_revision_metadata_and_legacy(tmp_path):
    store = TemplateStore(tmp_path)
    with TestClient(create_app(tmp_path)) as client:
        payload = {'name': 'Streamer', 'style': SubtitleStyle().model_dump(), 'streamer': '猫雷',
                   'workflow': {'language': 'ja', 'mode': 'saozi', 'highlights': 5, 'export_format': 'mp4', 'bilingual': True}}
        response = client.post('/companion-api/style-templates', json=payload)
        assert response.status_code == 200
        first = response.json()
        assert first.get('revision') == 1 and first.get('streamer') == '猫雷'
        renamed = client.post('/companion-api/style-templates', json={
            'id': first['id'], 'name': 'Renamed', 'style': first['style'], 'expected_revision': 1})
        assert renamed.status_code == 200
        second = renamed.json()
        assert second['id'] == first['id'] and second['revision'] == 2
        assert second['workflow'] == first['workflow'] and second['streamer'] == first['streamer']
        assert client.post('/companion-api/style-templates', json={
            'id': first['id'], 'name': 'Stale', 'style': first['style'], 'expected_revision': 1}).status_code == 409
    assert TemplateStore(tmp_path).list_styles()[-1].revision == 2
    portable = json.loads(store.download_style(first['id']))
    portable['name'] = 'Imported'
    imported = store.import_style(json.dumps(portable).encode())
    assert imported.streamer == '猫雷' and imported.workflow.language == 'ja'
    legacy = store.save_style('Legacy', SubtitleStyle())
    path = tmp_path / 'templates/styles' / f'{legacy.id}.json'
    data = json.loads(path.read_text())
    for key in ('revision', 'streamer', 'workflow'):
        data.pop(key)
    path.write_text(json.dumps(data))
    loaded = next(t for t in store.list_styles() if t.id == legacy.id)
    assert loaded.revision == 1 and loaded.workflow.language == 'auto'


def test_studio_settings_persist_validate_and_preserve_other_files(tmp_path):
    unrelated = tmp_path / 'config.json'
    unrelated.write_text('{"deepseek_api_key":""}')
    before = unrelated.read_bytes()
    with TestClient(create_app(tmp_path)) as client:
        response = client.get('/companion-api/studio-settings')
        assert response.status_code == 200
        settings = response.json()
        assert settings['default_template_id'] == 'nyaru'
        settings.update(language='ja', highlights=7, default_template_id=None)
        assert client.post('/companion-api/studio-settings', json=settings).json() == settings
        for changes in ({'highlights': 0}, {'highlights': '4'}, {'bilingual': 'yes'}, {'extra': True}, {'language': 'xx'}):
            assert client.post('/companion-api/studio-settings', json={**settings, **changes}).status_code == 422
        assert client.post('/companion-api/studio-settings', json={**settings, 'default_template_id': 'missing'}).status_code == 409
    with TestClient(create_app(tmp_path)) as client:
        assert client.get('/companion-api/studio-settings').json() == settings
    assert unrelated.read_bytes() == before
    path = tmp_path / 'templates/studio-settings.json'
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    path.write_text('{}broken')
    with TestClient(create_app(tmp_path)) as client:
        assert client.get('/companion-api/studio-settings').status_code == 422
    path.unlink()
    path.symlink_to(unrelated)
    with TestClient(create_app(tmp_path)) as client:
        assert client.get('/companion-api/studio-settings').status_code == 409
        assert client.post('/companion-api/studio-settings', json=settings).status_code == 409
    assert unrelated.read_bytes() == before


def test_nonlive_template_snapshot_and_retry(tmp_path, monkeypatch):
    from app.arctime import companion_manager as module, media
    from app.arctime.companion_models import JobInput
    store = TemplateStore(tmp_path)
    template = store.save_style('Pinned', SubtitleStyle())
    manager = module.JobManager(tmp_path, tmp_path / 'unused', 1)
    queued = []
    monkeypatch.setattr(manager.executor, 'submit', lambda *a, **kw: queued.append((a, kw)))
    monkeypatch.setattr(module, 'burn_available', lambda: False)
    def create(url, root, ranges, highlights, adapter, **kwargs):
        directory = root / kwargs['run_id']
        directory.mkdir()
        media.write_json(directory / 'job.json', {'state': 'completed', 'completed_clips': []})
        return directory
    monkeypatch.setattr(module.workflow, 'create_run', create)
    monkeypatch.setattr(module.workflow, 'resume_run', lambda directory, *a, **kw: manager.read_json(directory / 'job.json'))
    try:
        request = JobInput(url='https://example.com/video', ranges=[('0', '3')], subtitle_template_id=template.id)
        job_id = manager.submit(request, deferred=True)
        store.save_style('Changed', template.style, template_id=template.id)
        manager.run(job_id, request)
        path = manager.directory(job_id) / 'job.json'
        saved = json.loads(path.read_text())
        assert saved['subtitle_template']['revision'] == 1
        assert saved['subtitle_template']['name'] == 'Pinned'
        store.delete_style(template.id)
        manager.submit(None, job_id)
        manager.run(job_id, None)
        assert json.loads(path.read_text())['subtitle_template'] == saved['subtitle_template']
    finally:
        manager.executor.shutdown(wait=True)


def test_nonlive_document_uses_snapshot_and_preserves_edits(finished, monkeypatch):
    from app.arctime import subtitle_encoding
    monkeypatch.setattr(subtitle_encoding, "video_metadata", lambda path: (1920, 1080, 30.0))
    from app.arctime import media
    client, directory = finished
    template = client.get('/companion-api/subtitle-settings').json()['templates'][0]
    template['style']['original']['size'] = 79
    path = directory / 'job.json'
    job = json.loads(path.read_text())
    job['subtitle_template'] = template
    media.write_json(path, job)
    original = {p.name: p.read_bytes() for p in directory.iterdir() if p.is_file()}
    endpoint = '/companion-api/jobs/abcdef123456/subtitle-document'
    document = client.get(endpoint).json()
    assert document['style']['original']['size'] == 79
    document['style']['original']['size'] = 61
    assert client.post(endpoint, json=document).status_code == 200
    settings = client.get('/companion-api/studio-settings').json()
    assert client.post('/companion-api/studio-settings', json={**settings, 'language': 'en'}).status_code == 200
    assert client.get(endpoint).json()['style']['original']['size'] == 61
    for name, content in original.items():
        assert (directory / name).read_bytes() == content


from test_subtitle_api import finished


def test_sample_preview_without_jobs(tmp_path, monkeypatch):
    from app.arctime import subtitle_api
    seen = []
    def render(document, time, bilingual):
        seen.append((document, time, bilingual))
        return b'\x89PNG\r\n\x1a\npreview'
    monkeypatch.setattr(subtitle_api, 'preview_png', render)
    with TestClient(create_app(tmp_path)) as client:
        payload = {'style': SubtitleStyle().model_dump(), 'original': 'Sample', 'translation': '字幕'}
        response = client.post('/companion-api/template-preview', json=payload)
        assert response.status_code == 200
        assert response.headers['content-type'] == 'image/png'
        assert response.content.startswith(b'\x89PNG')
        document, time, bilingual = seen[0]
        assert (document.width, document.height, time, bilingual) == (1920, 1080, 1, True)
        assert document.cues[0].text == 'Sample' and document.cues[0].translation == '字幕'
        for changes in ({'original': 'a' * 501}, {'bilingual': 'yes'}, {'extra': True}):
            assert client.post('/companion-api/template-preview', json={**payload, **changes}).status_code == 422
        assert client.post('/companion-api/template-preview', content=b'a' * 16385).status_code == 413
    assert not list(tmp_path.glob('*/job.json'))


from test_companion_gui import client, completed


def test_upload_pins_selected_template(client, tmp_path, monkeypatch):
    from app.arctime import companion_manager
    monkeypatch.setattr(companion_manager, 'burn_available', lambda: False)
    result = client.post('/companion-api/jobs/upload', params={
        'saozi': 'false', 'ranges': '[["1","4"]]', 'subtitle_template_id': 'nyaru'}, content=b'local-video')
    assert result.status_code == 202
    job = completed(client, result.json()['id'])
    assert job['state'] == 'completed'
    saved = json.loads((tmp_path / job['id'] / 'job.json').read_text())
    assert saved['subtitle_template']['id'] == 'nyaru'
    assert saved['subtitle_template']['revision'] == 1


def test_cannot_delete_configured_default_template(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        first = client.post('/companion-api/style-templates', json={
            'name': 'Default custom', 'style': SubtitleStyle().model_dump()}).json()
        settings = client.get('/companion-api/studio-settings').json()
        settings['default_template_id'] = first['id']
        assert client.post('/companion-api/studio-settings', json=settings).status_code == 200
        endpoint = f"/companion-api/style-templates/{first['id']}/delete"
        response = client.post(endpoint)
        assert response.status_code == 409
        assert '默认模板' in response.json()['detail']
        assert client.get('/companion-api/studio-settings').json()['default_template_id'] == first['id']
        assert any(item['id'] == first['id'] for item in client.get('/companion-api/subtitle-settings').json()['templates'])
        settings['default_template_id'] = None
        assert client.post('/companion-api/studio-settings', json=settings).status_code == 200
        assert client.post(endpoint).status_code == 200
        assert client.get('/companion-api/studio-settings').json()['default_template_id'] is None
        assert all(item['id'] != first['id'] for item in client.get('/companion-api/subtitle-settings').json()['templates'])
        assert client.post('/companion-api/style-templates/nyaru/delete').status_code == 409
