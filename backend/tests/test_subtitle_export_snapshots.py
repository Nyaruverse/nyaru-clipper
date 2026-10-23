import json

import pytest

from app.arctime import media, subtitle_exports
from app.arctime.subtitle_document import SubtitleDocument
from test_subtitle_api import finished, payload, wait_export
from test_subtitle_document import URL, document_job
from test_subtitle_format_identity import rendering


def export(client, document, kind='ass'):
    response = client.post(URL.replace('subtitle-document', 'subtitle-export'),
                           json=payload(client, kind=kind, document=document))
    assert response.status_code == 202
    result = wait_export(client)
    assert result['active']['state'] == 'completed', result
    return result['outputs'][-1]


def test_formats_share_full_snapshot_and_unsaved_drafts_do_not(document_job, rendering):
    client, directory = document_job
    document = client.get(URL).json()
    outputs = [export(client, document, kind) for kind in ('ass', 'burn', 'arctime')]
    assert all(output.get('document') is None for output in outputs)
    assert len({output['document_ref'] for output in outputs}) == 1
    for output in subtitle_exports.read_exports(directory).outputs:
        assert subtitle_exports.resolve_export_document(directory, output).model_dump() == document
    before = {path.name: path.read_bytes() for path in directory.glob('styled-*')}
    changed = json.loads(json.dumps(document))
    changed['cues'][0]['text'] = 'unsaved change at same revision'
    draft = export(client, changed)
    assert draft['document_ref'] != outputs[0]['document_ref']
    assert all((directory / name).read_bytes() == content for name, content in before.items())
    snapshots = list(directory.glob('subtitle-export-document-*.json'))
    assert len(snapshots) == 2
    assert {SubtitleDocument.model_validate_json(path.read_bytes()).cues[0].text for path in snapshots} == {
        document['cues'][0]['text'], changed['cues'][0]['text']}


def test_legacy_document_registry_and_receipt_are_read_without_rewrite(document_job, rendering):
    client, directory = document_job
    document = client.get(URL).json()
    output = export(client, document)
    legacy = {key: value for key, value in output.items() if key != 'document_ref'}
    legacy['document'] = document
    registry = directory / 'subtitle-exports.json'
    receipt = directory / f"styled-{output['id']}.receipt.json"
    media.write_json(registry, {'outputs': [legacy]})
    media.write_json(receipt, legacy)
    before = {path.name: path.read_bytes() for path in (registry, receipt, directory / output['filename'])}
    assert client.get(URL.replace('subtitle-document', 'subtitle-exports')).json()['outputs'][0]['document'] is None
    assert subtitle_exports.resolve_export_document(directory, subtitle_exports.read_exports(directory).outputs[0]).model_dump() == document
    export(client, document)
    assert all((directory / name).read_bytes() == content for name, content in before.items())


def test_auto_export_busy_is_visible_even_after_parent_completed(document_job):
    from app.arctime.companion_manager import JobManager
    _, directory = document_job
    manager = JobManager(directory.parent, directory / 'unused', 1)
    try:
        manager.active = {'id': directory.name, 'state': 'completed', 'auto_subtitle_export': True}
        assert manager.detail(directory.name, include_segments=False)['subtitle_export_busy'] is True
    finally:
        manager.active = None
        manager.executor.shutdown(wait=True)
        manager.chatgpt.close()


def test_document_receipt_recovers_publication_gap_without_rerender(document_job, rendering, monkeypatch):
    client, directory = document_job
    document = client.get(URL).json()
    link = subtitle_exports.os.link
    def interrupted(source, target):
        link(source, target)
        if target.suffix == '.ass':
            raise RuntimeError('simulated publication interruption')
    monkeypatch.setattr(subtitle_exports.os, 'link', interrupted)
    assert client.post(URL.replace('subtitle-document', 'subtitle-export'),
                       json=payload(client, document=document)).status_code == 202
    assert wait_export(client)['active']['state'] == 'failed'
    protected = {path.name: path.read_bytes() for path in directory.glob('styled-*')}
    monkeypatch.setattr(subtitle_exports.os, 'link', link)
    monkeypatch.setattr(subtitle_exports, 'video_dimensions', lambda path: pytest.fail('must recover without rendering'))
    output = export(client, document)
    assert subtitle_exports.resolve_export_document(directory, subtitle_exports.read_exports(directory).outputs[0]).model_dump() == document
    assert all((directory / name).read_bytes() == content for name, content in protected.items())
    assert client.get(f"/companion-api/jobs/{directory.name}/files/{output['filename']}").status_code == 200


@pytest.mark.parametrize('damage', ['missing', 'corrupt', 'digest', 'symlink'])
def test_snapshot_damage_rejects_recovery_preserving_products(document_job, rendering, damage):
    client, directory = document_job
    document = client.get(URL).json()
    output = export(client, document)
    saved = directory / f"subtitle-export-document-{output['document_ref']}.json"
    protected = {path.name: path.read_bytes() for path in directory.glob('styled-*')}
    if damage == 'missing':
        saved.unlink()
    elif damage == 'corrupt':
        saved.write_text('{')
    elif damage == 'digest':
        changed = json.loads(saved.read_bytes())
        changed['cues'][0]['text'] = 'tampered'
        saved.write_text(json.dumps(changed))
    else:
        outside = directory.parent / 'outside.json'
        outside.write_bytes(saved.read_bytes())
        saved.unlink()
        saved.symlink_to(outside)
    assert client.post(URL.replace('subtitle-document', 'subtitle-export'),
                       json=payload(client, document=document)).status_code == 202
    assert wait_export(client)['active']['state'] == 'failed'
    assert all((directory / name).read_bytes() == content for name, content in protected.items())


def test_progress_writes_only_small_activity_with_5000_cues_20_outputs(document_job, rendering, monkeypatch):
    client, directory = document_job
    document = client.get(URL).json()
    document['cues'] = [{**document['cues'][0], 'id': f'cue-{index:06d}'} for index in range(5000)]
    for index in range(20):
        document['cues'][0]['text'] = f'draft {index}'
        export(client, document)
    writes = []
    write = media.write_json
    def measured(path, value):
        write(path, value)
        writes.append((path.name, path.stat().st_size))
    monkeypatch.setattr(media, 'write_json', measured)
    def burn(source, working, duration, notify):
        for index in range(10):
            notify(f'progress {index}')
        return source
    monkeypatch.setattr(subtitle_exports, 'burn_clip', burn)
    export(client, document, 'burn')
    registry_writes = [size for name, size in writes if name == 'subtitle-exports.json']
    activity_writes = [size for name, size in writes if name == 'subtitle-export-activity.json']
    print(json.dumps({'registry_writes': len(registry_writes), 'registry_bytes': sum(registry_writes),
                      'activity_writes': len(activity_writes), 'activity_bytes': sum(activity_writes)}))
    assert len(registry_writes) == 1
    assert len(activity_writes) == 12
    assert max(activity_writes) < 1024
    assert max(registry_writes) < 100000
