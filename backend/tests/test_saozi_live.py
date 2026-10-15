import json
import shutil
import subprocess
import threading
from pathlib import Path

import pytest

from app.arctime import media
from app.arctime.saozi_live import run_live
from app.services.subtitles import SubtitleSegment


class Adapter:
    def identity(self):
        return {'engine': 'fixture'}

    def transcribe(self, source, directory, duration):
        return [SubtitleSegment('1', 0, duration, '段落。')]


class Selector:
    model = 'fixture'

    def choose(self, cues, start, duration, final=True):
        if not final and duration - start < 140:
            return None
        return {'start': start, 'end': min(start + 60, duration), 'score': None,
                'reasons': ['fixture'], 'title': '段落'}


@pytest.fixture
def recording(tmp_path):
    session = tmp_path / 'capture-0000'
    session.mkdir()
    source = session / 'chunk-00000.ts'
    subprocess.run([media.tool_path('ffmpeg'), '-v', 'error', '-f', 'lavfi', '-i',
                    'color=c=blue:s=64x64:r=5', '-f', 'lavfi', '-i', 'anullsrc=r=16000:cl=mono',
                    '-t', '20', '-c:v', 'libx264', '-preset', 'ultrafast', '-g', '5', '-c:a', 'aac',
                    '-f', 'mpegts', str(source)], check=True, capture_output=True)
    for i in range(1, 15):
        shutil.copyfile(source, session / f'chunk-{i:05d}.ts')
    paths = sorted(session.glob('*.ts'))
    (session / 'closed.csv').write_text(''.join(f'{p.name},0,20\n' for p in paths))
    return tmp_path, paths


class Capture:
    error = None

    def __init__(self, paths, directory):
        self.paths, self.directory, self.closed = paths, directory, False
        self.early = []

    def chunks(self):
        for path in self.paths:
            yield path
            count = len(list(self.directory.glob('clip-*.mp4')))
            self.early.append(count)
            if count:
                job = json.loads((self.directory / 'job.json').read_text())
                assert job['subtitles'] == 'subtitles.srt'
                assert (self.directory / job['subtitles']).is_file()
                if any(chunk['cues'] for chunk in job['chunks']):
                    assert media.read_subtitles(self.directory / job['subtitles'])

    def close(self):
        self.closed = True


def test_exports_while_source_active_stops_tail_and_recovers(recording):
    directory, paths = recording
    capture = Capture(paths, directory)
    job = run_live(directory, Selector(), Adapter(), threading.Event(), None, capture=capture)
    assert capture.closed and max(capture.early[:-1]) >= 2
    assert job['state'] == 'completed'
    assert job['selection'][0]['start'] == 0
    assert job['selection'][-1]['end'] == job['duration']
    assert all(a['end'] == b['start'] for a, b in zip(job['selection'], job['selection'][1:]))
    hashes = [c['video_sha256'] for c in job['completed_clips']]
    resumed = run_live(directory, Selector(), Adapter(), threading.Event(), None)
    assert hashes == [c['video_sha256'] for c in resumed['completed_clips']]
    assert media.probe_video(directory / 'source.mp4') > 299
    assert media.read_subtitles(directory / 'clip-001.srt')[0].start_seconds == 0
    (directory / 'observations.json').write_text(json.dumps({'exports_during_input': capture.early,
        'source_closed': capture.closed, 'completed': job['state'], 'hashes_unchanged': hashes ==
        [c['video_sha256'] for c in resumed['completed_clips']]}))


def test_live_invokes_bilingual_publication_before_capture_finishes(recording):
    directory, paths = recording
    capture = Capture(paths, directory)
    observed = []
    def publish(path, final):
        job = json.loads((path / 'job.json').read_text())
        observed.append((len(job['completed_clips']), final, capture.closed))
    run_live(directory, Selector(), Adapter(), threading.Event(), None,
             capture=capture, bilingual=publish)
    assert any(count > 0 and not final and not closed for count, final, closed in observed)
    assert observed[-1][1:] == (True, True)


def test_failure_retains_chunks_and_recovery_never_reselects(recording):
    directory, paths = recording
    class Broken(Selector):
        def choose(self, *args, **kwargs):
            raise ValueError('API unavailable')
    capture = Capture(paths, directory)
    with pytest.raises(ValueError, match='API unavailable'):
        run_live(directory, Broken(), Adapter(), threading.Event(), None, capture=capture)
    assert capture.closed
    failed = json.loads((directory / 'job.json').read_text())
    assert failed['state'] == 'live_failed' and failed['chunks']
    job = run_live(directory, Selector(), Adapter(), threading.Event(), None)
    assert job['state'] == 'completed' and len(job['chunks']) == 15
    (directory / job['completed_clips'][0]['video']).write_bytes(b'changed')
    with pytest.raises(ValueError, match='变化'):
        run_live(directory, Selector(), Adapter(), threading.Event(), None)


def test_reconnect_flushes_separate_tail(recording):
    directory, paths = recording
    second = directory / 'capture-0001'
    second.mkdir()
    other = second / 'chunk-00000.ts'
    shutil.copyfile(paths[0], other)
    capture = Capture([paths[0], other], directory)
    job = run_live(directory, Selector(), Adapter(), threading.Event(), None, capture=capture)
    assert len(job['selection']) == 2
    assert job['discontinuities'] == [job['selection'][0]['end']]


def test_publication_gap_reuses_selected_cut(recording, monkeypatch):
    from app.arctime import live_state
    directory, paths = recording
    original = live_state.save
    def fail_after_publication(directory, job):
        if job['completed_clips']:
            raise RuntimeError('checkpoint interrupted')
        original(directory, job)
    monkeypatch.setattr(live_state, 'save', fail_after_publication)
    with pytest.raises(RuntimeError):
        run_live(directory, Selector(), Adapter(), threading.Event(), None, capture=Capture(paths, directory))
    before = media.fingerprint(directory / 'clip-001.mp4')
    monkeypatch.setattr(live_state, 'save', original)
    run_live(directory, Selector(), Adapter(), threading.Event(), None)
    assert media.fingerprint(directory / 'clip-001.mp4') == before

def test_changed_prompt_cannot_resume(recording, monkeypatch):
    import app.arctime.saozi as semantic
    directory, paths = recording
    run_live(directory, Selector(), Adapter(), threading.Event(), None, capture=Capture(paths[:1], directory))
    monkeypatch.setattr(semantic, 'PROMPT', semantic.PROMPT + 'changed')
    with pytest.raises(ValueError, match='配置'):
        run_live(directory, Selector(), Adapter(), threading.Event(), None)


def test_no_speech_preserves_media(recording):
    directory, paths = recording
    class Silence(Adapter):
        def transcribe(self, *args):
            raise ValueError('No speech was recognized; check the source audio and language')
    job = run_live(directory, Selector(), Silence(), threading.Event(), None, capture=Capture(paths[:1], directory))
    assert job['state'] == 'completed' and not (directory / 'subtitles.srt').read_text().strip()
    assert job['completed_clips'] and media.probe_video(directory / 'clip-001.mp4') > 19


def test_export_uses_only_overlapping_chunks_with_local_offsets(recording, monkeypatch):
    from app.arctime import live_state
    directory, paths = recording
    original = live_state.concatenate
    batches = []
    def track(directory, chunks, target):
        if target.name == '.live-buffer.mp4':
            batches.append([c['start'] for c in chunks])
        return original(directory, chunks, target)
    monkeypatch.setattr(live_state, 'concatenate', track)
    job = run_live(directory, Selector(), Adapter(), threading.Event(), None, capture=Capture(paths, directory))
    (directory / 'offset-observations.json').write_text(json.dumps({'export_chunk_starts': batches}))
    assert batches[1][0] > 0
    assert len(batches[1]) <= 4
    assert media.read_subtitles(directory / 'clip-002.srt')[0].start_seconds == 0
    second = job['selection'][1]
    assert abs(media.probe_video(directory / 'clip-002.mp4') - (second['end'] - second['start'])) < .5


def test_global_subtitle_publication_gap_recovers(recording, monkeypatch):
    from app.arctime import live_state
    directory, paths = recording
    publish = live_state._publish_text
    calls = []
    def interrupted(path, content):
        if path.name == 'transcript.txt':
            calls.append(1)
            if len(calls) == 2:
                raise RuntimeError('transcript interrupted')
        publish(path, content)
    monkeypatch.setattr(live_state, '_publish_text', interrupted)
    with pytest.raises(RuntimeError, match='transcript interrupted'):
        run_live(directory, Selector(), Adapter(), threading.Event(), None, capture=Capture(paths, directory))
    failed = json.loads((directory / 'job.json').read_text())
    assert len(failed['chunks']) == 2
    assert media.fingerprint(directory / 'subtitles.srt') != failed['artifacts']['subtitles.srt']
    monkeypatch.setattr(live_state, '_publish_text', publish)
    job = run_live(directory, Selector(), Adapter(), threading.Event(), None)
    assert job['state'] == 'completed'
    assert media.fingerprint(directory / 'subtitles.srt') == job['artifacts']['subtitles.srt']
