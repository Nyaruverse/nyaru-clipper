import json
import os
import threading
from pathlib import Path

import pytest

from app.arctime import live_state, media, subtitle_exports
from app.arctime.companion_manager import JobManager
from app.arctime.saozi_live import run_live
from app.arctime.subtitle_exports import SubtitleExports, read_exports
from app.arctime.subtitle_style import SubtitleStyle
from app.arctime.subtitle_templates import StyleTemplate
from app.services.subtitles import SubtitleSegment, render_srt


class Adapter:
    def identity(self):
        return {'engine': 'count-fixture'}

    def transcribe(self, source, directory, duration):
        return [SubtitleSegment('1', 0, duration, '原文')]


class Selector:
    model = 'count-fixture'

    def choose(self, cues, start, duration, final=True):
        return {'start': start, 'end': min(start + 60, duration)}


class Capture:
    error = None

    def __init__(self, paths):
        self.paths = paths

    def chunks(self):
        yield from self.paths

    def close(self):
        pass


@pytest.fixture
def counted(tmp_path, monkeypatch):
    directory = tmp_path / 'job'
    directory.mkdir()
    manager = JobManager(tmp_path, tmp_path / 'unused', 1)
    exports = SubtitleExports(manager)
    counts = {'checks': 0, 'input_calls': 0, 'input_bytes': 0,
              'product_calls': 0, 'product_bytes': 0, 'encodes': 0,
              'hash_visits': [], 'encoded_videos': []}
    measuring = False
    original_hash = media.fingerprint
    original_run = exports._run_locked

    def fingerprint(path):
        if measuring:
            category = 'product' if path.name.startswith('styled-') or path.parent.name.startswith('.subtitle-export-') else 'input'
            counts[category + '_calls'] += 1
            counts[category + '_bytes'] += path.stat().st_size
            counts['hash_visits'].append({'category': category, 'path': str(path), 'bytes': path.stat().st_size})
        return original_hash(path)

    def checked(*args, **kwargs):
        counts['checks'] += 1
        return original_run(*args, **kwargs)

    def styled(*args):
        nonlocal measuring
        measuring = True
        try:
            return exports.export_live(*args)
        finally:
            measuring = False

    def concatenate(directory, chunks, target):
        target.write_bytes(b'fixture-video')

    def export(source, target, start, end, cues):
        target.write_bytes(b'fixture-video')
        target.with_suffix('.srt').write_text(render_srt(media.clip_subtitles(cues, start, end)))

    def burn(source, working, duration, notify):
        counts['encodes'] += 1
        counts['encoded_videos'].append(source.name)
        output = working / 'burn.mp4'
        output.write_bytes(b'fixture-burn')
        return output

    monkeypatch.setattr(media, 'fingerprint', fingerprint)
    monkeypatch.setattr(exports, '_run_locked', checked)
    monkeypatch.setattr(live_state, 'concatenate', concatenate)
    monkeypatch.setattr(media, 'export_clip', export)
    monkeypatch.setattr(media, 'probe_video', lambda path: 60.)
    monkeypatch.setattr(live_state.video_integrity, 'validate_video_decode', lambda *args: None)
    monkeypatch.setattr(subtitle_exports, 'video_dimensions', lambda path: (64, 64))
    monkeypatch.setattr(subtitle_exports, 'burn_clip', burn)
    template = StyleTemplate(id='count', name='Count', style=SubtitleStyle())
    yield directory, exports, counts, styled, template
    manager.executor.shutdown(wait=True)
    manager.chatgpt.close()


@pytest.mark.parametrize('count', [20, 40, 80])
def test_production_append_has_linear_styled_checks_and_hash_bytes(counted, count):
    directory, exports, counts, styled, template = counted
    session = directory / 'capture-0000'
    session.mkdir()
    paths = [session / f'chunk-{i:05d}.ts' for i in range(count)]
    for path in paths:
        path.write_bytes(b'fixture-capture')
    published = 0
    revisits = []
    boundaries = []

    def observe_append(*args):
        nonlocal published
        current = args[1]['completed_clips']
        added = current[published:]
        allowed_inputs = {str(directory / clip[key]) for clip in added for key in ('video', 'subtitles')}
        old_products = {str(directory / output.filename) for output in read_exports(directory).outputs}
        start = len(counts['hash_visits'])
        styled(*args)
        visits = counts['hash_visits'][start:]
        revisits.extend(visit for visit in visits if (
            visit['category'] == 'input' and visit['path'] not in allowed_inputs
            or visit['category'] == 'product' and visit['path'] in old_products))
        boundaries.append({'new_videos': [clip['video'] for clip in added],
                           'hash_calls': len(visits), 'hash_bytes': sum(visit['bytes'] for visit in visits)})
        published = len(current)

    job = run_live(directory, Selector(), Adapter(), threading.Event(), None,
                   capture=Capture(paths), style_template=template, styled=observe_append)
    outputs = read_exports(directory).outputs
    result = {'n': count, **counts, 'outputs': len(read_exports(directory).outputs),
              'historical_revisits': revisits, 'append_boundaries': boundaries,
              'substitutes': 'capture, ASR, selector, concatenate, clip encoder, probe/decode and burn encoder; production run_live/export_pending/export_live/_run_locked and fingerprint retained'}
    evidence = Path(os.environ.get('LIVE_STYLE_EVIDENCE', str(directory)))
    evidence.mkdir(parents=True, exist_ok=True)
    (evidence / f'counts-{count}.json').write_text(json.dumps(result, indent=2))
    print(json.dumps({key: result[key] for key in (
        'n', 'checks', 'input_calls', 'input_bytes', 'product_calls', 'product_bytes', 'encodes', 'outputs')}))
    assert not job.get('subtitle_style_error')
    assert revisits == []
    assert {(output.video, output.kind) for output in outputs} == {
        (clip['video'], kind) for clip in job['completed_clips'] for kind in ('ass', 'burn')}
    assert counts['checks'] <= 2 * count
    assert counts['encodes'] <= count
    assert len(counts['encoded_videos']) == len(set(counts['encoded_videos']))
    inputs = [directory / clip[key] for clip in job['completed_clips'] for key in ('video', 'subtitles')]
    assert counts['input_calls'] <= 4 * len(inputs)
    assert counts['product_calls'] <= 2 * len(outputs)
    assert counts['input_bytes'] <= 4 * sum(path.stat().st_size for path in inputs)
    assert counts['product_bytes'] <= 2 * sum((directory / output.filename).stat().st_size for output in outputs)


def run_counted(counted, count=2):
    directory, exports, counts, styled, template = counted
    session = directory / 'capture-0000'
    session.mkdir()
    paths = [session / f'chunk-{i:05d}.ts' for i in range(count)]
    for path in paths:
        path.write_bytes(b'fixture-capture')
    return run_live(directory, Selector(), Adapter(), threading.Event(), None,
                    capture=Capture(paths), style_template=template, styled=styled)


def test_changed_translation_only_rechecks_affected_old_clip(counted):
    from app.arctime import saozi_translation
    directory, exports, counts, styled, template = counted
    job = run_counted(counted)
    protected = {output.filename: (directory / output.filename).read_bytes()
                 for output in read_exports(directory).outputs}
    changed = []
    state = {'state': 'partial', 'artifacts': {}}
    cues = media.read_subtitles(directory / 'subtitles.srt')
    saozi_translation._publish(directory, job, cues, ['訳文'], state, changed.append)
    media.write_json(directory / 'translation.json', state)
    assert set(changed) == {'subtitles.ja-zh.srt', 'clip-001.ja-zh.srt'}
    styled(directory, job, [job['completed_clips'][0]])
    assert counts['checks'] == 6 and counts['encodes'] == 3
    bilingual = [output for output in read_exports(directory).outputs if output.bilingual]
    assert len(bilingual) == 2 and all(output.video == 'clip-001.mp4' for output in bilingual)
    ass = next(output for output in bilingual if output.kind == 'ass')
    assert '訳文' in (directory / ass.filename).read_text()
    assert all((directory / name).read_bytes() == content for name, content in protected.items())
    changed.clear()
    saozi_translation._publish(directory, job, cues, ['訳文'], state, changed.append)
    assert changed == []


def test_run_live_routes_late_translation_events_for_old_clips(counted):
    from app.arctime import saozi_translation
    from test_saozi_translation import KEY, api
    directory, exports, counts, styled, template = counted
    session = directory / 'capture-0000'
    session.mkdir()
    paths = [session / f'chunk-{i:05d}.ts' for i in range(2)]
    for path in paths:
        path.write_bytes(b'fixture-capture')
    events = []
    def bilingual(path, final):
        saved = json.loads((path / 'job.json').read_text())
        if len(saved['completed_clips']) < 2:
            return set()
        changed = set()
        with api([]) as client:
            saozi_translation.translate(path, KEY, final=final, client=client, locked=True,
                                         changed_artifact=changed.add)
        videos = {name.removesuffix('.ja-zh.srt') + '.mp4' for name in changed if name.startswith('clip-')}
        events.append(sorted(videos))
        return videos
    job = run_live(directory, Selector(), Adapter(), threading.Event(), None,
                   capture=Capture(paths), style_template=template, styled=styled, bilingual=bilingual)
    assert events == [['clip-001.mp4', 'clip-002.mp4'], []]
    assert counts['checks'] == 6 and counts['encodes'] == 3
    assert not job.get('subtitle_style_error')
    assert len([output for output in read_exports(directory).outputs if output.bilingual]) == 4


def test_template_change_rechecks_history_and_preserves_old_outputs(counted):
    directory, exports, counts, styled, template = counted
    job = run_counted(counted)
    protected = {output.filename: (directory / output.filename).read_bytes()
                 for output in read_exports(directory).outputs}
    job['subtitle_template']['style']['original']['size'] += 1
    styled(directory, job, [])
    assert counts['checks'] == 8 and counts['encodes'] == 4
    assert len(read_exports(directory).outputs) == 8
    assert all((directory / name).read_bytes() == content for name, content in protected.items())


def test_failed_clip_retries_without_rechecking_successful_history(counted, monkeypatch):
    directory, exports, counts, styled, template = counted
    burn = subtitle_exports.burn_clip
    failures = []
    def fail_once(source, *args):
        if source.name == 'clip-001.mp4' and not failures:
            failures.append(source.name)
            raise ValueError('encoder interrupted')
        return burn(source, *args)
    monkeypatch.setattr(subtitle_exports, 'burn_clip', fail_once)
    job = run_counted(counted)
    assert not job.get('subtitle_style_error')
    assert counts['checks'] == 6 and counts['encodes'] == 2
    assert len(read_exports(directory).outputs) == 4


@pytest.mark.parametrize('damage', ['product', 'receipt', 'symlink'])
def test_full_revalidation_preserves_corrupt_products_and_download_checks(counted, damage):
    from fastapi import HTTPException
    directory, exports, counts, styled, template = counted
    job = run_counted(counted, 1)
    output = read_exports(directory).outputs[0]
    product = directory / output.filename
    if damage == 'receipt':
        (directory / f'styled-{output.id}.receipt.json').write_text('invalid')
    elif damage == 'symlink':
        source = directory / job['completed_clips'][0]['video']
        outside = directory.parent / 'outside.mp4'
        source.rename(outside)
        source.symlink_to(outside)
    else:
        product.write_bytes(b'corrupt')
    protected = product.read_bytes()
    styled(directory, job, None)
    assert job.get('subtitle_style_error')
    assert product.read_bytes() == protected and counts['encodes'] == 1
    if damage == 'product':
        with pytest.raises(HTTPException) as error:
            subtitle_exports.export_artifact(directory, output.filename)
        assert error.value.status_code == 409
