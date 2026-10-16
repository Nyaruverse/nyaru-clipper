import json
import subprocess
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.arctime import media
from app.arctime.subtitle_style import TextStyle
from test_subtitle_api import finished, payload, wait_export

URL = '/companion-api/jobs/abcdef123456/subtitle-document'


@pytest.fixture
def document_job(finished, monkeypatch):
    from app.arctime import subtitle_encoding
    client, directory = finished
    monkeypatch.setattr(subtitle_encoding, 'video_metadata', lambda path: (640, 360, 25.0), raising=False)
    return client, directory


def test_document_get_save_cas_and_immutable_sources(document_job):
    client, directory = document_job
    before = {p.name: media.fingerprint(p) for p in directory.iterdir() if p.is_file()}
    response = client.get(URL)
    assert response.status_code == 200, response.text
    doc = response.json()
    assert doc['revision'] == 0 and doc['width'] == 640 and doc['fps'] == 25
    assert [cue['id'] for cue in doc['cues']] == ['cue-000001', 'cue-000002']
    assert not (directory / 'subtitle-document.json').exists()
    doc['cues'][0]['text'] = 'Edited 😀'
    saved = client.post(URL, json=doc)
    assert saved.status_code == 200, saved.text
    assert saved.json()['revision'] == 1
    assert client.get(URL).json() == saved.json()
    assert client.post(URL, json=doc).status_code == 409
    assert all(media.fingerprint(directory / name) == digest for name, digest in before.items())


def test_source_change_and_symlink_rejected(document_job):
    client, directory = document_job
    doc = client.get(URL).json()
    outside = directory.parent / 'private.json'
    outside.write_text('do not replace')
    (directory / 'subtitle-document.json').symlink_to(outside)
    assert client.post(URL, json=doc).status_code == 409
    assert outside.read_text() == 'do not replace'
    (directory / 'subtitle-document.json').unlink()
    job = json.loads((directory / 'job.json').read_bytes())
    job['ranges'] = [[0, 5]]
    media.write_json(directory / 'job.json', job)
    assert client.post(URL, json=doc).status_code == 409


@pytest.mark.parametrize('change', [
    {'end_seconds': 0}, {'start_seconds': -1}, {'end_seconds': 9},
    {'original_emphasis': [{'start': 0, 'end': 99, 'color': '#FF0000', 'bold': True}]},
    {'text': 'bad\x00text'},
])
def test_invalid_cues_are_rejected(document_job, change):
    client, _ = document_job
    doc = client.get(URL).json()
    doc['cues'][0].update(change)
    assert client.post(URL, json=doc).status_code == 422


def test_duplicate_ids_and_changed_geometry_rejected(document_job):
    client, _ = document_job
    doc = client.get(URL).json()
    doc['cues'][1]['id'] = doc['cues'][0]['id']
    assert client.post(URL, json=doc).status_code == 422
    doc = client.get(URL).json()
    doc['width'] = 1920
    assert client.post(URL, json=doc).status_code == 409


def test_edited_export_clamps_absolute_cues_and_packages_document(document_job, monkeypatch):
    from app.arctime import subtitle_exports
    client, directory = document_job
    monkeypatch.setattr(subtitle_exports, 'video_dimensions', lambda path: (640, 360))
    doc = client.get(URL).json()
    doc['cues'][0].update(start_seconds=0.5, end_seconds=2, text='edited start')
    doc['cues'][1].update(start_seconds=4, end_seconds=5.5, text='edited end')
    request = payload(client, document=doc, kind='arctime')
    assert client.post(URL.replace('subtitle-document', 'subtitle-export'), json=request).status_code == 202
    snapshot = wait_export(client)
    assert snapshot['active']['state'] == 'completed', snapshot
    import zipfile
    with zipfile.ZipFile(directory / snapshot['outputs'][0]['filename']) as archive:
        ass = archive.read('clip.ass').decode()
        assert '0:00:00.00,0:00:01.00' in ass and '0:00:03.00,0:00:04.00' in ass
        assert 'edited start' in ass and 'edited end' in ass
        assert json.loads(archive.read('subtitle-document.json')) == doc
        assert json.loads(archive.read('manifest.json'))['time_origin_seconds'] == 1
    assert snapshot['outputs'][0]['document'] == doc
    request['style']['original']['size'] += 1
    assert client.post(URL.replace('subtitle-document', 'subtitle-export'), json=request).status_code == 422


def test_advanced_styles_emphasis_and_pixel_coordinates():
    from app.arctime.subtitle_document import SubtitleDocument, Cue, Emphasis
    from app.arctime.subtitle_render import render_document_ass
    from app.arctime.subtitle_style import SubtitleStyle
    style = TextStyle(bold=True, italic=True, underline=True, opacity=.5, spacing=3,
        line_height=1.5, align=7, x=50, y=80, rotation=12, scale_x=120, scale_y=80,
        shadow=2, shadow_color='#112233', padding=5, max_width=80)
    cue = Cue(id='cue-000001', start_seconds=0, end_seconds=1, text='😀{\\pos(0,0)}',
        original_style=style, original_emphasis=[Emphasis(start=0, end=1, color='#FF0000', bold=False)])
    doc = SubtitleDocument(source_fingerprint='a'*64, revision=0, style=SubtitleStyle(), cues=[cue], width=640, height=360, duration=2, fps=25)
    ass = render_document_ass(doc, False)
    assert 'PlayResX: 640\nPlayResY: 360' in ass
    assert r'\pos(50,80)' in ass and r'\an7' in ass
    assert r'\frz12' in ass and r'\fscx120' in ass and r'\fscy80' in ass
    assert r'\1c&H0000FF&\b0' in ass
    assert '\\\u2060pos' in ass


def test_preview_png_has_transparent_and_visible_pixels(document_job, tmp_path):
    from app.arctime.subtitle_encoding import subtitle_ffmpeg
    client, directory = document_job
    doc = client.get(URL).json()
    response = client.post(URL.replace('subtitle-document', 'subtitle-preview'), json={'document': doc, 'time': 2, 'bilingual': False})
    assert response.status_code == 200, response.text
    assert response.headers['content-type'] == 'image/png'
    png = tmp_path / 'preview.png'
    png.write_bytes(response.content)
    raw = subprocess.run([subtitle_ffmpeg(), '-v', 'error', '-i', str(png), '-f', 'rawvideo', '-pix_fmt', 'rgba', '-'], capture_output=True, check=True).stdout
    assert len(raw) == 640 * 360 * 4
    assert min(raw[3::4]) == 0 and max(raw[3::4]) > 0
    assert not list(directory.glob('*preview*'))


def test_new_translation_and_split_merge_export_without_translation_task(document_job, monkeypatch):
    from app.arctime import subtitle_exports
    client, _ = document_job
    monkeypatch.setattr(subtitle_exports, 'video_dimensions', lambda path: (640, 360))
    doc = client.get(URL).json()
    original = doc['cues'][0]
    original.update(end_seconds=2, translation='新しい訳')
    doc['cues'].insert(1, {**original, 'id': 'edit-00000000-0000-4000-8000-000000000001', 'start_seconds': 2, 'end_seconds': 3})
    saved = client.post(URL, json=doc)
    assert saved.status_code == 200
    request = payload(client, document=saved.json(), bilingual=True)
    assert client.post(URL.replace('subtitle-document', 'subtitle-export'), json=request).status_code == 202
    assert wait_export(client)['active']['state'] == 'completed'
    merged = saved.json()
    merged['cues'][0]['end_seconds'] = merged['cues'].pop(1)['end_seconds']
    assert client.post(URL, json=merged).status_code == 200


def test_source_reload_is_read_only_and_reset_is_explicit_cas(document_job):
    client, directory = document_job
    doc = client.get(URL).json()
    assert client.post(URL, json=doc).status_code == 200
    before = (directory / 'subtitle-document.json').read_bytes()
    job = json.loads((directory / 'job.json').read_bytes())
    job['ranges'] = [[0, 5]]
    media.write_json(directory / 'job.json', job)
    assert client.get(URL).status_code == 409
    fresh = client.get(URL + '?source=true')
    assert fresh.status_code == 200
    assert fresh.json()['revision'] == 1
    assert (directory / 'subtitle-document.json').read_bytes() == before
    saved = client.post(URL, json=fresh.json())
    assert saved.status_code == 200 and saved.json()['revision'] == 2
    assert next(directory.glob('subtitle-document-*-r1.json')).read_bytes() == before
    assert client.post(URL, json=doc).status_code == 409


def test_document_save_rejected_while_export_busy(document_job, monkeypatch):
    import threading
    from app.arctime import subtitle_exports
    client, _ = document_job
    entered, release = threading.Event(), threading.Event()
    doc = client.get(URL).json()
    monkeypatch.setattr(subtitle_exports, 'video_dimensions', lambda path: (640, 360))
    monkeypatch.setattr(subtitle_exports, 'burn_available', lambda: True)
    def burn(source, working, duration, notify):
        entered.set()
        assert release.wait(5)
        product = working / 'burn.mp4'
        product.write_bytes(b'burned')
        return product
    monkeypatch.setattr(subtitle_exports, 'burn_clip', burn)
    try:
        assert client.post(URL.replace('subtitle-document', 'subtitle-export'), json=payload(client, kind='burn')).status_code == 202
        assert entered.wait(2)
        assert client.post(URL, json=doc).status_code == 409
    finally:
        release.set()
    assert wait_export(client)['active']['state'] == 'completed'


def test_line_height_padding_hidden_and_language_inheritance():
    from app.arctime.subtitle_document import SubtitleDocument, Cue
    from app.arctime.subtitle_render import render_document_ass
    from app.arctime.subtitle_style import SubtitleStyle
    style = SubtitleStyle(original=TextStyle(size=60, line_height=2, x=100, y=100, align=7, background_opacity=1, padding=10),
                          translation=TextStyle(hidden=True))
    cue = Cue(id='cue-000001', start_seconds=0, end_seconds=1, text='line1\nline2', translation='hidden')
    doc = SubtitleDocument(source_fingerprint='a'*64, revision=0, style=style, cues=[cue], width=640, height=360, duration=2, fps=25)
    result = render_document_ass(doc, True)
    assert r'\pos(100,100)' in result and r'\pos(100,140)' in result
    assert 'hidden' not in result
    assert ',3,4,0,7,0,0,0,1' in result


@pytest.mark.parametrize('values', [{'align': True}, {'opacity': -1}, {'line_height': 0}, {'scale_y': 401}, {'x': float('inf')}, {'shadow_color': 'red'}])
def test_advanced_invalid_style(values):
    with pytest.raises(ValidationError):
        TextStyle(**values)


def test_global_advanced_style_without_document_uses_shared_renderer():
    from app.arctime.subtitle_style import SubtitleStyle, render_ass
    from app.services.subtitles import SubtitleSegment
    result = render_ass([SubtitleSegment('1', 0, 1, 'global')], None,
        SubtitleStyle(original=TextStyle(x=30, y=40, rotation=15, bold=True)), 640, 360, video_canvas=True)
    assert r'\pos(30,40)' in result and r'\frz15' in result


@pytest.mark.parametrize('dimensions', [(360, 640), (641, 361)])
def test_real_preview_canvas_and_composite_matches_ass(tmp_path, dimensions):
    from app.arctime.subtitle_document import SubtitleDocument, Cue
    from app.arctime.subtitle_render import preview_png, render_document_ass
    from app.arctime.subtitle_encoding import subtitle_ffmpeg
    from app.arctime.subtitle_style import SubtitleStyle
    width, height = dimensions
    doc = SubtitleDocument(source_fingerprint='a'*64, revision=0, width=width, height=height,
        duration=2, fps=25, style=SubtitleStyle(original=TextStyle(size=100, opacity=.6, color='#FF8000', x=50, y=100, align=7)),
        cues=[Cue(id='cue-000001', start_seconds=0, end_seconds=1, text='Visible text')])
    image = tmp_path / 'preview.png'
    image.write_bytes(preview_png(doc, .5, False))
    (tmp_path / 'subtitle.ass').write_text(render_document_ass(doc, False))
    binary = subtitle_ffmpeg()
    rgba = subprocess.run([binary, '-v', 'error', '-i', str(image), '-f', 'rawvideo', '-pix_fmt', 'rgba', '-'], check=True, capture_output=True).stdout
    assert len(rgba) == width * height * 4
    direct = subprocess.run([binary, '-v', 'error', '-f', 'lavfi', '-i', f'color=black:s={width}x{height},format=rgba',
        '-vf', 'ass=filename=subtitle.ass', '-frames:v', '1', '-pix_fmt', 'rgb24', '-f', 'rawvideo', '-'], cwd=tmp_path, check=True, capture_output=True).stdout
    errors = []
    for pixel in range(width * height):
        alpha = rgba[pixel * 4 + 3] / 255
        if alpha:
            errors.extend(abs(round(rgba[pixel * 4 + channel] * alpha) - direct[pixel * 3 + channel]) for channel in range(3))
    assert errors and max(errors) <= 3, (max(errors), sum(errors) / len(errors))


def test_preview_uses_ass_centisecond_boundary(tmp_path):
    from app.arctime.subtitle_document import SubtitleDocument, Cue
    from app.arctime.subtitle_render import preview_png
    from app.arctime.subtitle_encoding import subtitle_ffmpeg
    from app.arctime.subtitle_style import SubtitleStyle
    doc = SubtitleDocument(source_fingerprint='a'*64, revision=0, width=320, height=180, duration=2, fps=25,
        style=SubtitleStyle(), cues=[Cue(id='cue-000001', start_seconds=1.235, end_seconds=1.5, text='Boundary')])
    for time, visible in [(1.237, False), (1.24, True), (1.5, False)]:
        path = tmp_path / f'frame-{time}.png'
        path.write_bytes(preview_png(doc, time, False))
        rgba = subprocess.run([subtitle_ffmpeg(), '-v', 'error', '-i', str(path), '-f', 'rawvideo', '-pix_fmt', 'rgba', '-'], capture_output=True, check=True).stdout
        assert bool(max(rgba[3::4])) is visible


def test_real_http_document_preview_ass_and_burn_preserve_sources(tmp_path):
    from fastapi.testclient import TestClient
    from app.arctime.gui import create_app
    from app.arctime.subtitle_encoding import subtitle_ffmpeg
    from app.services.subtitles import SubtitleSegment, render_srt
    binary = subtitle_ffmpeg()
    directory = tmp_path / 'abcdef123456'
    directory.mkdir()
    subprocess.run([binary, '-v', 'error', '-f', 'lavfi', '-i', 'color=black:s=320x180:r=25:d=2',
                    '-c:v', 'libx264', '-pix_fmt', 'yuv420p', str(directory / 'source.mp4')], check=True)
    subprocess.run([binary, '-v', 'error', '-ss', '0.5', '-i', str(directory / 'source.mp4'), '-t', '1',
                    '-c:v', 'libx264', str(directory / 'clip-001.mp4')], check=True)
    cues = [SubtitleSegment('1', .25, .75, 'Original'), SubtitleSegment('2', 1.25, 1.75, 'Second')]
    (directory / 'subtitles.srt').write_text(render_srt(cues))
    (directory / 'clip-001.srt').write_text(render_srt(media.clip_subtitles(cues, .5, 1.5)))
    digest = lambda name: media.fingerprint(directory / name)
    media.write_json(directory / 'job.json', {'version': 2, 'state': 'completed', 'duration': 2,
        'video': 'source.mp4', 'video_sha256': digest('source.mp4'), 'subtitles': 'subtitles.srt',
        'ranges': [[.5, 1.5]], 'highlight_count': None, 'asr': {'language': 'ja'},
        'artifacts': {'subtitles.srt': digest('subtitles.srt')},
        'selection': [{'start': .5, 'end': 1.5, 'score': None, 'reasons': ['manual']}],
        'completed_clips': [{'video': 'clip-001.mp4', 'subtitles': 'clip-001.srt', 'video_sha256': digest('clip-001.mp4'), 'subtitles_sha256': digest('clip-001.srt')}]})
    before = {p.name: media.fingerprint(p) for p in directory.iterdir()}
    with TestClient(create_app(tmp_path)) as client:
        doc = client.get(URL).json()
        assert (doc['width'], doc['height'], doc['fps']) == (320, 180, 25)
        doc['cues'][0]['text'] = 'Edited'
        doc['cues'][0]['original_style'] = {**doc['style']['original'], 'x': 80, 'y': 90, 'align': 5, 'color': '#FF8000', 'opacity': .6}
        doc = client.post(URL, json=doc).json()
        png = client.post(URL.replace('subtitle-document', 'subtitle-preview'), json={'document': doc, 'time': .6, 'bilingual': False})
        assert png.status_code == 200
        (tmp_path / 'http-preview.png').write_bytes(png.content)
        for kind in ('ass', 'burn'):
            response = client.post(URL.replace('subtitle-document', 'subtitle-export'), json=payload(client, kind=kind, document=doc))
            assert response.status_code == 202, response.text
            result = wait_export(client)
            assert result['active']['state'] == 'completed', result
        ass_output = next(item for item in result['outputs'] if item['kind'] == 'ass')
        assert '0:00:00.00,0:00:00.25' in (directory / ass_output['filename']).read_text()
        old_hashes = {item['filename']: digest(item['filename']) for item in result['outputs']}
        assert all(digest(name) == value for name, value in before.items())
        doc['cues'][0]['text'] = 'Next edit'
        saved = client.post(URL, json=doc)
        assert saved.status_code == 200
        assert all(digest(name) == value for name, value in old_hashes.items())
        media.write_json(tmp_path / 'hash-verification.json', {'sources_before': before,
            'sources_after': {name: digest(name) for name in before}, 'exports_before': old_hashes,
            'exports_after': {name: digest(name) for name in old_hashes}})


def test_verified_source_cache_reuses_hashes_and_invalidates_stat_or_symlink(document_job, monkeypatch):
    client, directory = document_job
    fingerprint = media.fingerprint
    calls = []
    def observed(path):
        calls.append(path.name)
        return fingerprint(path)
    monkeypatch.setattr(media, 'fingerprint', observed)
    initial = client.get(URL)
    assert initial.status_code == 200
    count = len(calls)
    assert count > 0
    assert client.get(URL).json() == initial.json()
    assert len(calls) == count
    job = json.loads((directory / 'job.json').read_bytes())
    job['ranges'] = [[0, 5]]
    media.write_json(directory / 'job.json', job)
    changed = client.get(URL)
    assert changed.status_code == 200 and changed.json()['source_fingerprint'] != initial.json()['source_fingerprint']
    assert len(calls) > count
    source = directory / 'source.mp4'
    source.rename(directory / 'backup.mp4')
    source.symlink_to(directory / 'backup.mp4')
    assert client.get(URL).status_code == 409


@pytest.mark.parametrize('style_values, expected', [
    ({'position': 'top', 'align': 2, 'x': 80, 'y': 90}, r'\an2\pos(80,90)'),
    ({'align': 5}, r'\an5\pos(320,180)'),
    ({'align': 8}, r'\an8\pos(320,32)'),
])
def test_anchor_grid_respects_explicit_alignment_and_auto_row(style_values, expected):
    from app.arctime.subtitle_document import SubtitleDocument, Cue
    from app.arctime.subtitle_render import render_document_ass
    from app.arctime.subtitle_style import SubtitleStyle
    doc = SubtitleDocument(source_fingerprint='a'*64, revision=0, width=640, height=360, duration=2, fps=25,
        style=SubtitleStyle(original=TextStyle(**style_values)), cues=[Cue(id='cue-000001', start_seconds=0, end_seconds=1, text='Anchor')])
    assert expected in render_document_ass(doc, False)


def test_background_emphasis_has_metrics_without_color_override():
    from app.arctime.subtitle_document import SubtitleDocument, Cue, Emphasis
    from app.arctime.subtitle_render import render_document_ass
    from app.arctime.subtitle_style import SubtitleStyle
    doc = SubtitleDocument(source_fingerprint='a'*64, revision=0, width=640, height=360, duration=2, fps=25,
        style=SubtitleStyle(original=TextStyle(background_opacity=.5, opacity=.6)),
        cues=[Cue(id='cue-000001', start_seconds=0, end_seconds=1, text='Bold text', original_emphasis=[Emphasis(start=0,end=4,color='#FF0000',bold=True)])])
    ass = render_document_ass(doc, False)
    background = next(line for line in ass.splitlines() if line.startswith('Dialogue: 0'))
    assert r'\b1' in background and r'\1c' not in background
    assert r'\1c&H0000FF&\b1' in ass


def test_line_height_is_font_size_multiplier():
    from app.arctime.subtitle_document import SubtitleDocument, Cue
    from app.arctime.subtitle_render import render_document_ass
    from app.arctime.subtitle_style import SubtitleStyle
    style = TextStyle(size=60, x=100, y=100, align=7)
    doc = SubtitleDocument(source_fingerprint='a'*64, revision=0, width=640, height=360, duration=2, fps=25,
        style=SubtitleStyle(original=style), cues=[Cue(id='cue-000001', start_seconds=0, end_seconds=1, text='first\nsecond')])
    ass = render_document_ass(doc, False)
    assert style.line_height == 1.2
    assert r'\pos(100,100)' in ass and r'\pos(100,124)' in ass
    assert r'\pos(100,128.8)' not in ass


def test_document_cache_is_bounded_to_32_tasks(document_job):
    import shutil
    from app.arctime.subtitle_document import DocumentStore
    from app.arctime.subtitle_style import SubtitleStyle
    _, directory = document_job
    store = DocumentStore()
    for index in range(33):
        target = directory.parent / f'{index:012x}'
        shutil.copytree(directory, target)
        store.base(target, SubtitleStyle())
    assert len(store.bases) == 32
    assert directory.parent / '000000000000' not in store.bases


def test_translation_added_or_changed_invalidates_source_cache(document_job):
    from app.services.subtitles import render_bilingual_srt
    client, directory = document_job
    before = client.get(URL).json()
    cues = media.read_subtitles(directory / 'subtitles.srt')
    bilingual = directory / 'subtitles.ja-zh.srt'
    bilingual.write_text(render_bilingual_srt(cues, ['Translation one', 'Translation two']))
    media.write_json(directory / 'translation.json', {'state': 'completed', 'artifacts': {bilingual.name: media.fingerprint(bilingual)}})
    updated = client.get(URL)
    assert updated.status_code == 200
    assert updated.json()['source_fingerprint'] != before['source_fingerprint']
    assert updated.json()['cues'][0]['translation'] == 'Translation one'
    bilingual.write_text('changed')
    assert client.get(URL).status_code == 409


@pytest.mark.parametrize('position', ['bottom', 'top', 'center'])
@pytest.mark.parametrize('language', ['Original', 'Translation'])
def test_explicit_nudge_preserves_automatic_counterpart_stack(tmp_path, position, language):
    import re
    from app.arctime.subtitle_document import SubtitleDocument, Cue
    from app.arctime.subtitle_render import render_document_ass
    from app.arctime.subtitle_style import SubtitleStyle
    alignment = {'top': 8, 'bottom': 2, 'center': 5}[position]
    style_position = 'top' if position == 'top' else 'bottom'
    style_alignment = 5 if position == 'center' else 2
    styles = SubtitleStyle(original=TextStyle(position=style_position, align=style_alignment, size=48, margin=96),
                           translation=TextStyle(position=style_position, align=style_alignment, size=40, margin=40))
    cue = Cue(id='cue-000001', start_seconds=0, end_seconds=1, text='Original\nsecond', translation='Translated\nsecond')
    document = SubtitleDocument(source_fingerprint='a'*64, revision=0, width=640, height=360, duration=2, fps=25,
                                style=styles, cues=[cue])
    def positions(content, name):
        lines = [line for line in content.splitlines() if line.startswith('Dialogue: 1,') and f',{name}0,' in line]
        return [tuple(map(float, re.search(r'\\pos\(([^,]+),([^)]+)\)', line).groups())) for line in lines]
    def anchor(content, name):
        line = next(line for line in content.splitlines() if line.startswith('Dialogue: 1,') and f',{name}0,' in line)
        return tuple(map(float, re.search(r'\\org\(([^,]+),([^)]+)\)', line).groups()))
    baseline = render_document_ass(document, True)
    other = 'Translation' if language == 'Original' else 'Original'
    x, y = anchor(baseline, language)
    field = 'original_style' if language == 'Original' else 'translation_style'
    inherited = styles.original if language == 'Original' else styles.translation
    edited = cue.model_copy(update={field: inherited.model_copy(update={'x': x + 1, 'y': y, 'align': alignment})})
    changed = render_document_ass(document.model_copy(update={'cues': [edited]}), True)
    (tmp_path / 'before.ass').write_text(baseline)
    (tmp_path / 'after.ass').write_text(changed)
    assert positions(changed, language) == [(x + 1, y) for x, y in positions(baseline, language)]
    assert positions(changed, other) == positions(baseline, other)
    x, y = anchor(changed, other)
    other_field = 'translation_style' if other == 'Translation' else 'original_style'
    other_style = styles.translation if other == 'Translation' else styles.original
    both_explicit = edited.model_copy(update={other_field: other_style.model_copy(update={'x': x + 1, 'y': y, 'align': alignment})})
    final = render_document_ass(document.model_copy(update={'cues': [both_explicit]}), True)
    (tmp_path / 'both-explicit.ass').write_text(final)
    assert positions(final, language) == positions(changed, language)
    assert positions(final, other) == [(x + 1, y) for x, y in positions(changed, other)]


def test_variation_selector_does_not_add_a_wrapped_line(tmp_path):
    from app.arctime.subtitle_document import SubtitleDocument, Cue
    from app.arctime.subtitle_render import render_document_ass
    from app.arctime.subtitle_style import SubtitleStyle
    doc = SubtitleDocument(source_fingerprint='a'*64, revision=0, width=88, height=1080, duration=2, fps=25,
        style=SubtitleStyle(original=TextStyle(size=20)),
        cues=[Cue(id='cue-000001', start_seconds=0, end_seconds=1, text='☀\ufe0fA')])
    rendered = render_document_ass(doc, False)
    (tmp_path / 'variation-selector.ass').write_text(rendered)
    assert rendered.count('Dialogue: 1,') == 1
    assert '☀\ufe0fA' in rendered
