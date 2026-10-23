import hashlib
import json
import subprocess
import sys

import pytest
from fastapi.testclient import TestClient

from app.arctime import media
from app.arctime.gui import create_app
from app.arctime.subtitle_document import (
    DocumentStore, SubtitleDocument, base_document, load_document, save_document, validate_source,
)
from app.arctime.subtitle_inputs import ExportRequest, load_inputs
from app.arctime.subtitle_style import SubtitleStyle
from test_subtitle_api import finished, payload, wait_export
from test_subtitle_document import URL, document_job


def legacy_document(directory, style):
    translation = directory / 'translation.json'
    bilingual = translation.is_file() and json.loads(translation.read_bytes())['state'] == 'completed'
    inputs = load_inputs(directory, ExportRequest(kind='ass', video='source.mp4', style=style, bilingual=bilingual))
    source = {'job': media.fingerprint(directory / 'job.json'), 'artifacts': inputs.digests,
              'translation': media.fingerprint(translation) if translation.is_file() else None,
              'width': 640, 'height': 360, 'fps': 25.0}
    old = base_document(directory, style).model_dump()
    old.update(source_fingerprint=hashlib.sha256(json.dumps(source, sort_keys=True).encode()).hexdigest(), revision=7)
    old['cues'][0]['text'] = 'Legacy user edit'
    media.write_json(directory / 'subtitle-document.json', old)
    return old


def test_verified_legacy_v1_read_only_upgrade_and_backup(document_job, monkeypatch):
    from app.arctime import subtitle_exports
    monkeypatch.setattr(subtitle_exports, 'video_dimensions', lambda path: (640, 360))
    client, directory = document_job
    old = legacy_document(directory, SubtitleStyle())
    before = (directory / 'subtitle-document.json').read_bytes()
    response = client.get(URL)
    assert response.status_code == 200, response.text
    current = response.json()
    assert current['source_fingerprint'] != old['source_fingerprint']
    assert current['revision'] == 7 and current['cues'] == old['cues']
    assert (directory / 'subtitle-document.json').read_bytes() == before
    validate_source(SubtitleDocument.model_validate(old), base_document(directory, SubtitleStyle()))
    inputs = load_inputs(directory, ExportRequest.model_validate(payload(client, document=old, style=old['style'])))
    assert inputs.document.cues[0].text == 'Legacy user edit'
    preview = client.post(URL.replace('subtitle-document', 'subtitle-preview'),
                          json={'document': old, 'time': 2, 'bilingual': False})
    assert preview.status_code == 200, preview.text
    assert client.post(URL.replace('subtitle-document', 'subtitle-export'),
                       json=payload(client, document=old, style=old['style'])).status_code == 202
    result = wait_export(client)
    assert result['active']['state'] == 'completed'
    output = result['outputs'][0]['filename']
    receipt = (directory / output.replace('.ass', '.receipt.json')).read_bytes()
    saved = client.post(URL, json=old)
    assert saved.status_code == 200, saved.text
    assert saved.json()['source_fingerprint'] == current['source_fingerprint']
    assert saved.json()['revision'] == 8
    assert next(directory.glob('subtitle-document-*-r7.json')).read_bytes() == before
    assert client.post(URL, json=old).status_code == 409
    assert client.get('/companion-api/jobs/abcdef123456/files/' + output + '?download=true').status_code == 200
    assert (directory / output.replace('.ass', '.receipt.json')).read_bytes() == receipt


@pytest.mark.parametrize('change', ['diagnostic', 'timeline'])
def test_unprovable_legacy_recovery_preserves_edits_and_cas(document_job, change):
    client, directory = document_job
    old = legacy_document(directory, SubtitleStyle())
    before = (directory / 'subtitle-document.json').read_bytes()
    job = json.loads((directory / 'job.json').read_bytes())
    job.update({'subtitle_style_error': 'failed'} if change == 'diagnostic' else {'ranges': [[0, 5]]})
    media.write_json(directory / 'job.json', job)
    assert client.get(URL).status_code == 409
    assert client.post(URL, json=old).status_code == 409
    fresh = client.get(URL + '?source=true')
    assert fresh.status_code == 200 and fresh.json()['revision'] == 7
    assert (directory / 'subtitle-document.json').read_bytes() == before
    restored = fresh.json()
    restored['cues'] = old['cues']
    assert client.post(URL, json=restored).json()['revision'] == 8
    assert next(directory.glob('subtitle-document-*-r7.json')).read_bytes() == before


def test_diagnostic_translation_outputs_and_template_do_not_change_identity(document_job):
    client, directory = document_job
    from app.services.subtitles import render_bilingual_srt
    cues = media.read_subtitles(directory / 'subtitles.srt')
    bilingual = directory / 'subtitles.ja-zh.srt'
    bilingual.write_text(render_bilingual_srt(cues, ['one', 'two']))
    translation = {'state': 'completed', 'artifacts': {bilingual.name: media.fingerprint(bilingual)}}
    media.write_json(directory / 'translation.json', translation)
    doc = client.get(URL).json()
    doc['cues'][0]['text'] = 'User revision'
    doc = client.post(URL, json=doc).json()
    job = json.loads((directory / 'job.json').read_bytes())
    job.update(subtitle_style_error='export failed', progress={'done': 4}, output='unused.ass',
               subtitle_template=client.get('/companion-api/subtitle-settings').json()['templates'][0])
    job['selection'][0].update(score=99, reasons=['diagnostic'])
    media.write_json(directory / 'job.json', job)
    translation.update(error='old retry', progress=100, outputs=['unused.ass'])
    translation['artifacts']['unused.srt'] = 'a' * 64
    media.write_json(directory / 'translation.json', translation)
    response = client.get(URL)
    assert response.status_code == 200, response.text
    assert response.json() == doc
    assert load_document(directory, SubtitleStyle()).source_fingerprint == doc['source_fingerprint']
    assert DocumentStore().load(directory, SubtitleStyle()).source_fingerprint == doc['source_fingerprint']
    assert save_document(directory, SubtitleDocument.model_validate(doc)).revision == 2


@pytest.mark.parametrize('legacy_without_save', [False, True])
def test_auto_export_failure_edit_success_restart_and_export(document_job, monkeypatch, legacy_without_save):
    from app.arctime.companion_manager import JobManager
    from app.arctime.subtitle_exports import SubtitleExports, read_exports
    from app.arctime.subtitle_inputs import ExportError
    import app.arctime.subtitle_exports as module
    client, directory = document_job
    job = json.loads((directory / 'job.json').read_bytes())
    job['subtitle_template'] = client.get('/companion-api/subtitle-settings').json()['templates'][0]
    media.write_json(directory / 'job.json', job)
    before = {name: media.fingerprint(directory / name) for name in ('source.mp4', 'subtitles.srt', 'clip-001.mp4', 'clip-001.srt')}
    manager = JobManager(directory.parent, directory / 'unused', 1)
    exports = SubtitleExports(manager)
    from app.arctime.subtitle_encoding import subtitle_ffmpeg
    for name in ('source.mp4', 'clip-001.mp4'):
        subprocess.run([subtitle_ffmpeg(), '-v', 'error', '-y', '-f', 'lavfi', '-i',
                        'color=black:s=640x360:r=25:d=6', '-c:v', 'libx264',
                        str(directory / name)], check=True)
    job['video_sha256'] = media.fingerprint(directory / 'source.mp4')
    job['completed_clips'][0]['video_sha256'] = media.fingerprint(directory / 'clip-001.mp4')
    media.write_json(directory / 'job.json', job)
    before = {name: media.fingerprint(directory / name) for name in before}
    real_burn = module.burn_clip
    if legacy_without_save:
        job['subtitle_style_error'] = 'previous failed export'
        media.write_json(directory / 'job.json', job)
        old = legacy_document(directory, SubtitleStyle.model_validate(job['subtitle_template']['style']))
        old['revision'] = 1
        old['cues'][0]['text'] = 'Saved after failed automatic export'
        media.write_json(directory / 'subtitle-document.json', old)
        old_bytes = (directory / 'subtitle-document.json').read_bytes()
    def fail(source, working, duration, notify):
        raise ExportError('controlled automatic burn failure')
    try:
        monkeypatch.setattr(module, 'burn_clip', fail)
        exports.export_live(directory, job)
        assert read_exports(directory).active.state == 'failed'
        assert 'subtitle_style_error' in job
        if legacy_without_save:
            assert DocumentStore().load(directory, SubtitleStyle()).revision == 1
        if not legacy_without_save:
            document = client.get(URL).json()
            document['cues'][0]['text'] = 'Saved after failed automatic export'
            saved = client.post(URL, json=document)
            assert saved.status_code == 200, saved.text
        monkeypatch.setattr(module, 'burn_clip', real_burn)
        exports.export_live(directory, job)
        assert read_exports(directory).active.state == 'completed'
        assert 'subtitle_style_error' not in job
        if legacy_without_save:
            assert (directory / 'subtitle-document.json').read_bytes() == old_bytes
    finally:
        manager.executor.shutdown(wait=True)
        manager.chatgpt.close()
    client.__exit__(None, None, None)
    script = '''
import sys
from pathlib import Path
sys.path.insert(0, 'tests')
from fastapi.testclient import TestClient
from app.arctime.gui import create_app
from test_subtitle_api import payload, wait_export
url = '/companion-api/jobs/abcdef123456/subtitle-document'
with TestClient(create_app(Path(sys.argv[1]))) as client:
    response = client.get(url)
    assert response.status_code == 200, response.text
    assert response.json()['cues'][0]['text'] == 'Saved after failed automatic export'
    assert response.json()['revision'] == 1
    saved = client.post(url, json=response.json())
    assert saved.status_code == 200 and saved.json()['revision'] == 2, saved.text
    request = payload(client, document=saved.json())
    assert client.post(url.replace('subtitle-document', 'subtitle-export'), json=request).status_code == 202
    result = wait_export(client)
    assert result['active']['state'] == 'completed', result
    print('RESTART_GET_POST_EXPORT_PASS', flush=True)
'''
    reopened = subprocess.run([sys.executable, '-c', script, str(directory.parent)], capture_output=True, text=True)
    (directory / 'restart.log').write_text(reopened.stdout + reopened.stderr)
    assert reopened.returncode == 0, reopened.stdout + reopened.stderr
    assert all(media.fingerprint(directory / name) == digest for name, digest in before.items())


@pytest.mark.parametrize('change', ['duration', 'selection', 'ranges', 'video', 'subtitles', 'canvas'])
def test_real_source_changes_remain_rejected(document_job, monkeypatch, change):
    from app.arctime import subtitle_encoding
    client, directory = document_job
    doc = client.get(URL).json()
    assert client.post(URL, json=doc).status_code == 200
    job = json.loads((directory / 'job.json').read_bytes())
    if change in ('video', 'subtitles'):
        path = directory / job[change]
        path.write_bytes(path.read_bytes() + b'\n')
    elif change == 'canvas':
        monkeypatch.setattr(subtitle_encoding, 'video_metadata', lambda path: (1280, 720, 25.0))
        job['diagnostic'] = 'invalidate cache for metadata oracle'
    elif change == 'selection':
        job['selection'][0]['start'] = 0
    else:
        job.update({'duration': 7} if change == 'duration' else {'ranges': [[0, 5]]})
    media.write_json(directory / 'job.json', job)
    assert client.get(URL).status_code == 409
    assert client.post(URL, json=doc).status_code == 409


