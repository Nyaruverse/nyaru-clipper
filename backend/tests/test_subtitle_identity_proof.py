import json

import pytest

from app.arctime import media
from app.arctime.subtitle_document import base_document, save_document
from app.arctime.subtitle_style import SubtitleStyle
from test_subtitle_api import finished
from test_subtitle_document import URL, document_job
from test_subtitle_identity import legacy_document


def test_proof_is_bound_to_content_and_cannot_bypass_changed_source(document_job):
    from app.arctime.subtitle_document import preserve_legacy_source
    from app.arctime import workflow
    client, directory = document_job
    old = legacy_document(directory, SubtitleStyle())
    before = (directory / 'subtitle-document.json').read_bytes()
    with workflow.exclusive_lock(directory / '.lock'):
        preserve_legacy_source(directory)
    job = json.loads((directory / 'job.json').read_bytes())
    job['subtitle_style_error'] = 'changed diagnosis'
    media.write_json(directory / 'job.json', job)
    assert client.get(URL).status_code == 200
    job['ranges'] = [[0, 5]]
    media.write_json(directory / 'job.json', job)
    assert client.get(URL).status_code == 409
    assert client.post(URL, json=old).status_code == 409
    assert (directory / 'subtitle-document.json').read_bytes() == before


@pytest.mark.parametrize('failure', ['symlink', 'write'])
def test_proof_failure_preserves_old_document_and_manifest(document_job, monkeypatch, failure):
    from app.arctime.subtitle_document import preserve_legacy_source
    _, directory = document_job
    legacy_document(directory, SubtitleStyle())
    before = {name: (directory / name).read_bytes() for name in ('job.json', 'subtitle-document.json')}
    proof = directory / 'subtitle-source-proof.json'
    if failure == 'symlink':
        proof.symlink_to(directory / 'job.json')
        with pytest.raises(ValueError, match='Invalid job artifact path'):
            preserve_legacy_source(directory)
    else:
        write = media.write_json
        def fail(path, value):
            if path == proof:
                raise OSError('controlled proof write failure')
            write(path, value)
        monkeypatch.setattr(media, 'write_json', fail)
        with pytest.raises(OSError, match='controlled proof write failure'):
            preserve_legacy_source(directory)
        assert not proof.exists()
    assert all((directory / name).read_bytes() == content for name, content in before.items())


def test_direct_base_rejects_proof_read_toctou(document_job, monkeypatch):
    from app.arctime.subtitle_document import SourceProof, preserve_legacy_source
    _, directory = document_job
    legacy_document(directory, SubtitleStyle())
    preserve_legacy_source(directory)
    parse = SourceProof.model_validate_json
    def changed(content):
        proof = parse(content)
        job = json.loads((directory / 'job.json').read_bytes())
        job['ranges'] = [[0, 5]]
        media.write_json(directory / 'job.json', job)
        return proof
    monkeypatch.setattr(SourceProof, 'model_validate_json', changed)
    with pytest.raises(ValueError, match='校验期间改变'):
        base_document(directory, SubtitleStyle())


def test_save_rechecks_cached_base_inside_lock(document_job):
    _, directory = document_job
    base = base_document(directory, SubtitleStyle())
    job = json.loads((directory / 'job.json').read_bytes())
    job['ranges'] = [[0, 5]]
    media.write_json(directory / 'job.json', job)
    with pytest.raises(ValueError, match='字幕来源已改变'):
        save_document(directory, base, base=base)
    assert not (directory / 'subtitle-document.json').exists()
