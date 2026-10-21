import json

import pytest

from app.arctime import media, subtitle_api, subtitle_document
from test_subtitle_api import finished
from test_subtitle_document import document_job, URL

PREVIEW = URL.replace('subtitle-document', 'subtitle-preview')


def test_frame_and_legacy_render_identical_png_without_persisting(document_job, tmp_path):
    client, directory = document_job
    doc = client.get(URL).json()
    doc['cues'][0]['text'] = 'unsaved edit'
    frame = {**doc, 'cues': doc['cues'][:1]}
    full = client.post(PREVIEW, json={'document': doc, 'time': 2})
    local = client.post(PREVIEW, json={'frame': frame, 'time': 2})
    assert local.status_code == full.status_code == 200, local.text
    assert local.content == full.content and local.content.startswith(b'\x89PNG')
    (tmp_path / 'active-frame.png').write_bytes(local.content)
    assert not (directory / 'subtitle-document.json').exists()


@pytest.mark.parametrize('cue_count', [2, 5000])
def test_frame_cache_builds_source_once_then_rejects_changed_source(document_job, monkeypatch, tmp_path, cue_count):
    client, directory = document_job
    from app.services.subtitles import SubtitleSegment, render_srt
    cues = [SubtitleSegment(str(index + 1), 1 if index == 0 else 4, 3 if index == 0 else 5, 'same text')
            for index in range(cue_count)]
    (directory / 'subtitles.srt').write_text(render_srt(cues))
    job = json.loads((directory / 'job.json').read_bytes())
    job['artifacts']['subtitles.srt'] = media.fingerprint(directory / 'subtitles.srt')
    media.write_json(directory / 'job.json', job)
    build = subtitle_document.base_document
    calls = []
    def counted(*args):
        calls.append(1)
        return build(*args)
    monkeypatch.setattr(subtitle_document, 'base_document', counted)
    doc = client.get(URL).json()
    assert len(doc['cues']) == cue_count
    monkeypatch.setattr(subtitle_api, 'preview_png', lambda *args: b'png')
    body = json.dumps({'frame': {**doc, 'cues': doc['cues'][:1]}, 'time': 2})
    for _ in range(3):
        assert client.post(PREVIEW, json={'frame': {**doc, 'cues': doc['cues'][:1]}, 'time': 2}).status_code == 200
    assert len(calls) == 1
    (tmp_path / 'counts.json').write_text(json.dumps({'source_cues': cue_count, 'frame_cues': 1,
        'request_bytes': len(body.encode()), 'cold_builds': 1, 'hot_builds': len(calls) - 1}))
    (directory / 'source.mp4').write_bytes(b'changed')
    assert client.post(PREVIEW, json={'frame': doc, 'time': 2}).status_code == 409
    assert len(calls) == 2


@pytest.mark.parametrize('field,value,status', [('source_fingerprint', 'b' * 64, 409), ('width', 641, 409),
    ('duration', 7, 409), ('fps', 26, 409), ('height', 0, 422), ('revision', True, 422)])
def test_frame_source_and_numeric_boundaries(document_job, field, value, status):
    client, _ = document_job
    doc = client.get(URL).json()
    doc[field] = value
    assert client.post(PREVIEW, json={'frame': doc, 'time': 2}).status_code == status


@pytest.mark.parametrize('field', ['document', 'frame'])
def test_source_change_during_render_rejects_pixels(document_job, monkeypatch, field):
    client, directory = document_job
    doc = client.get(URL).json()
    def changed(*args):
        (directory / 'source.mp4').write_bytes(b'changed-during-render')
        return b'png'
    monkeypatch.setattr(subtitle_api, 'preview_png', changed)
    assert client.post(PREVIEW, json={field: doc, 'time': 2}).status_code == 409


def test_frame_rejects_ambiguous_body_and_limits(document_job):
    client, _ = document_job
    doc = client.get(URL).json()
    assert client.post(PREVIEW, json={'frame': doc, 'document': doc, 'time': 2}).status_code == 422
    assert client.post(PREVIEW, content=b' ' * (20 * 1024 * 1024 + 1)).status_code == 413
    doc['cues'] = [doc['cues'][0]] * 50001
    assert client.post(PREVIEW, json={'frame': doc, 'time': 2}).status_code == 422


@pytest.mark.parametrize('change', ['nan', 'negative', 'beyond_duration', 'color', 'emphasis', 'duplicate'])
def test_frame_retains_document_validation(document_job, change):
    client, _ = document_job
    doc = client.get(URL).json()
    time = 2
    if change == 'nan':
        time = float('nan')
    elif change == 'negative':
        time = -1
    elif change == 'beyond_duration':
        time = 7
    elif change == 'color':
        doc['style']['original']['color'] = '#invalid'
    elif change == 'emphasis':
        doc['cues'][0]['original_emphasis'] = [{'start': 0, 'end': 1000, 'color': '#FFFFFF', 'bold': False}]
    else:
        doc['cues'].append(doc['cues'][0])
    response = client.post(PREVIEW, content=json.dumps({'frame': doc, 'time': time}))
    assert response.status_code == (409 if change == 'beyond_duration' else 422)


@pytest.mark.parametrize('time', [2.004, 2.006, 2.02, 3.0])
def test_frame_overlap_centiseconds_styles_match_full_pixels(document_job, tmp_path, time):
    from app.arctime.subtitle_style import centiseconds
    client, _ = document_job
    doc = client.get(URL).json()
    doc['cues'][1].update(start_seconds=2.005, end_seconds=3.005, translation='translation',
        original_style={**doc['style']['original'], 'color': '#FF0000', 'size': 28},
        original_emphasis=[{'start': 0, 'end': 1, 'color': '#00FF00', 'bold': True}])
    active = [cue for cue in doc['cues'] if centiseconds(cue['start_seconds']) <= time * 100 < centiseconds(cue['end_seconds'])]
    response = client.post(PREVIEW, json={'frame': {**doc, 'cues': active}, 'time': time, 'bilingual': True})
    full = client.post(PREVIEW, json={'document': doc, 'time': time, 'bilingual': True})
    assert response.status_code == full.status_code == 200, response.text
    assert response.content == full.content
    (tmp_path / 'overlap-frame.png').write_bytes(response.content)


def test_frame_accepts_proven_legacy_but_rejects_changed_content(document_job):
    from app.arctime.subtitle_style import SubtitleStyle
    from test_subtitle_identity import legacy_document
    client, directory = document_job
    old = legacy_document(directory, SubtitleStyle())
    subtitle_document.preserve_legacy_source(directory)
    job = json.loads((directory / 'job.json').read_bytes())
    job['subtitle_style_error'] = 'diagnostic changed'
    media.write_json(directory / 'job.json', job)
    before = (directory / 'subtitle-document.json').read_bytes()
    assert client.post(PREVIEW, json={'frame': old, 'time': 2}).status_code == 200
    job['ranges'] = [[0, 5]]
    media.write_json(directory / 'job.json', job)
    assert client.post(PREVIEW, json={'frame': old, 'time': 2}).status_code == 409
    assert (directory / 'subtitle-document.json').read_bytes() == before
