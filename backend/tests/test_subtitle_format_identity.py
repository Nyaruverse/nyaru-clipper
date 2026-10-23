import hashlib
import json
from io import BytesIO
from zipfile import ZipFile

import pytest

from app.arctime import media, subtitle_exports
from app.arctime.companion_manager import JobManager
from app.arctime.subtitle_exports import ExportOutput, ExportSnapshot, SubtitleExports, read_exports
from app.arctime.subtitle_inputs import ExportRequest, load_inputs
from app.arctime.subtitle_templates import TemplateStore
from test_subtitle_api import finished, payload, wait_export


@pytest.fixture
def rendering(monkeypatch):
    calls = []
    monkeypatch.setattr(subtitle_exports, 'video_dimensions', lambda path: (640, 360))
    monkeypatch.setattr(subtitle_exports, 'burn_available', lambda: True)

    def burn(source, working, duration, notify):
        calls.append(source.name)
        return source

    monkeypatch.setattr(subtitle_exports, 'burn_clip', burn)
    return calls


@pytest.mark.parametrize('kind', ['ass', 'burn'])
def test_http_template_switch_delete_and_auto_share_current_identity(finished, rendering, kind):
    client, directory = finished
    store = TemplateStore(directory.parent)
    first = store.save_project('First', 'first.atpj', b'first-project')
    second = store.save_project('Second', 'second.atpj', b'second-project')
    request = payload(client, kind=kind)
    endpoint = '/companion-api/jobs/abcdef123456/subtitle-export'
    assert client.post(endpoint, json=request).status_code == 202
    baseline = wait_export(client)['outputs'][0]
    for project_id in [first.id, second.id]:
        assert client.post(endpoint, json={**request, 'arctime_template_id': project_id}).status_code == 202
        assert wait_export(client)['outputs'] == [baseline]
    store.delete_project(second.id)
    assert client.post(endpoint, json={**request, 'arctime_template_id': second.id}).status_code == 202
    assert wait_export(client)['outputs'] == [baseline]
    assert client.get(f"/companion-api/jobs/abcdef123456/files/{baseline['filename']}").status_code == 200
    job = json.loads((directory / 'job.json').read_bytes())
    job['subtitle_template'] = {'id': 'snapshot', 'name': 'Pinned', 'style': request['style'],
                                'arctime_template_id': second.id}
    manager = JobManager(directory.parent, directory / 'unused-model', 1)
    try:
        SubtitleExports(manager).export_live(directory, job)
        assert 'subtitle_style_error' not in job
        assert [output.model_dump() for output in read_exports(directory).outputs if output.kind == kind] == [baseline]
        assert len(rendering) == 1
    finally:
        manager.executor.shutdown(wait=True)
        manager.chatgpt.close()


@pytest.mark.parametrize('kind', ['ass', 'burn'])
def test_first_http_export_ignores_stale_project_but_checks_source(finished, rendering, kind):
    client, directory = finished
    request = payload(client, kind=kind, arctime_template_id='missing-project')
    endpoint = '/companion-api/jobs/abcdef123456/subtitle-export'
    assert client.post(endpoint, json=request).status_code == 202
    assert wait_export(client)['active']['state'] == 'completed'
    (directory / 'clip-001.mp4').write_bytes(b'tampered')
    assert client.post(endpoint, json=request).status_code == 409


@pytest.mark.parametrize('damage', ['wrong_id', 'deleted', 'corrupt'])
def test_arctime_retains_template_integrity_checks(finished, rendering, damage):
    client, directory = finished
    store = TemplateStore(directory.parent)
    project = store.save_project('Project', 'project.atpj', b'valid-project')
    request = payload(client, kind='arctime', arctime_template_id=project.id)
    endpoint = '/companion-api/jobs/abcdef123456/subtitle-export'
    assert client.post(endpoint, json=request).status_code == 202
    output = wait_export(client)['outputs'][0]
    with ZipFile(BytesIO(client.get(f"/companion-api/jobs/abcdef123456/files/{output['filename']}").content)) as bundle:
        assert bundle.read('template.atpj') == b'valid-project'
    if damage == 'wrong_id':
        request['arctime_template_id'] = '../project'
    elif damage == 'deleted':
        store.delete_project(project.id)
    else:
        store._path('projects', project.id, 'atpj').write_bytes(b'corrupt')
    assert client.post(endpoint, json=request).status_code == 409


def test_arctime_optional_project_and_distinct_project_bytes(finished, rendering):
    client, directory = finished
    store = TemplateStore(directory.parent)
    endpoint = '/companion-api/jobs/abcdef123456/subtitle-export'
    for content in [None, b'first-project', b'second-project']:
        template_id = store.save_project(content.decode(), 'project.atpj', content).id if content else None
        assert client.post(endpoint, json=payload(client, kind='arctime', arctime_template_id=template_id)).status_code == 202
        assert wait_export(client)['active']['state'] == 'completed'
    outputs = wait_export(client)['outputs']
    assert len({output['id'] for output in outputs}) == 3
    with ZipFile(directory / outputs[0]['filename']) as bundle:
        assert 'template.atpj' not in bundle.namelist()


@pytest.mark.parametrize('kind', ['ass', 'burn'])
def test_common_runner_ignores_irrelevant_project_bytes(finished, rendering, kind):
    client, directory = finished
    request = ExportRequest.model_validate(payload(client, kind=kind))
    manager = JobManager(directory.parent, directory / 'unused-model', 1)
    snapshot = ExportSnapshot()
    try:
        exports = SubtitleExports(manager)
        exports._run_locked(directory, request, None, snapshot)
        baseline = list(snapshot.outputs)
        exports._run_locked(directory, request, b'irrelevant-project', snapshot)
        assert snapshot.outputs == baseline
    finally:
        manager.executor.shutdown(wait=True)
        manager.chatgpt.close()


@pytest.mark.parametrize('legacy_project', [True, False])
@pytest.mark.parametrize('renderer_revision', [2, 3])
def test_legacy_receipt_remains_downloadable_without_aliasing_unknown_inputs(finished, rendering, legacy_project, renderer_revision):
    client, directory = finished
    store = TemplateStore(directory.parent)
    project = store.save_project('Legacy', 'legacy.atpj', b'legacy-project')
    request = ExportRequest.model_validate(payload(client, kind='burn', arctime_template_id=project.id))
    if not legacy_project:
        request = request.for_format()
    identity = hashlib.sha256(json.dumps({'renderer_revision': renderer_revision, 'package_revision': 1,
        'request': request.model_dump(), 'inputs': load_inputs(directory, request).digests,
        'project': hashlib.sha256(b'legacy-project').hexdigest() if legacy_project else None}, sort_keys=True).encode()).hexdigest()[:20]
    old_file = directory / f'styled-{identity}.mp4'
    old_file.write_bytes(b'unknown-historical-output')
    output = ExportOutput(id=identity, kind='burn', video=request.video, bilingual=False,
        filename=old_file.name, sha256=media.fingerprint(old_file), style=request.style)
    media.write_json(directory / 'subtitle-exports.json', ExportSnapshot(outputs=[output]).model_dump())
    media.write_json(directory / f'styled-{identity}.receipt.json', output.model_dump())
    assert client.post('/companion-api/jobs/abcdef123456/subtitle-export', json=request.model_dump()).status_code == 202
    outputs = wait_export(client)['outputs']
    assert len(outputs) == 2
    assert outputs[1]['id'] != identity and len(rendering) == 1
    assert client.get(f'/companion-api/jobs/abcdef123456/files/{old_file.name}').content == b'unknown-historical-output'
    assert media.fingerprint(old_file) == output.sha256
