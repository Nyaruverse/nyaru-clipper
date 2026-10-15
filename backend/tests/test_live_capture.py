import threading
import json
import pytest
from app.arctime.live_capture import LiveCapture

@pytest.mark.parametrize('url', ['https://example.com/123', 'https://live.bilibili.com/x', 'https://u:p@live.bilibili.com/123', 'https://live.bilibili.com/123?token=secret'])
def test_rejects_non_room_urls(tmp_path, url):
    with pytest.raises(ValueError):
        LiveCapture(url, tmp_path, threading.Event())

def test_closed_csv_only(tmp_path):
    cap = LiveCapture('https://live.bilibili.com/123', tmp_path, threading.Event())
    session = tmp_path / 'capture-0000'
    session.mkdir()
    (session / 'closed.csv').write_text('chunk-00000.ts,0,20\nchunk-00001.ts,20,40')
    (session / 'chunk-00000.ts').write_bytes(b'closed')
    (session / 'chunk-00001.ts').write_bytes(b'open')
    assert cap.recorded(tmp_path) == [session / 'chunk-00000.ts']

def test_real_capture_closes_process_and_keeps_recording_while_consumer_waits(tmp_path, monkeypatch):
    import subprocess
    import time
    from app.arctime import media
    import app.arctime.live_capture as module
    source = tmp_path / 'fixture.ts'
    subprocess.run([media.tool_path('ffmpeg'), '-v', 'error', '-f', 'lavfi', '-i',
                    'color=c=red:s=64x64:r=5', '-t', '10', '-c:v', 'libx264', '-preset',
                    'ultrafast', '-g', '5', '-f', 'mpegts', str(source)], check=True, capture_output=True)
    original = subprocess.Popen
    def realtime(args, **kwargs):
        args = list(args)
        if '-segment_time' in args:
            args.insert(args.index('-i'), '-re')
            args[args.index('-segment_time') + 1] = '1'
        return original(args, **kwargs)
    cap = LiveCapture('https://live.bilibili.com/123', tmp_path, threading.Event())
    monkeypatch.setattr(cap, '_resolve', lambda: str(source))
    monkeypatch.setattr(module.subprocess, 'Popen', realtime)
    stream = cap.chunks()
    first = next(stream)
    assert first.is_file() and cap.process.poll() is None
    count = len(cap.recorded(tmp_path))
    time.sleep(2.2)
    backlog_count = len(cap.recorded(tmp_path))
    assert backlog_count > count
    cap.close()
    remaining = list(stream)
    assert remaining and cap.process.poll() is not None and not cap.thread.is_alive()
    assert all(media.probe_video(path) > 0 for path in [first, *remaining])
    (tmp_path / 'observations.json').write_text(json.dumps({'pid': cap.process.pid,
        'exit_code': cap.process.returncode, 'thread_alive': cap.thread.is_alive(),
        'before_consumer_wait': count, 'after_consumer_wait': backlog_count,
        'closed_chunks': len([first, *remaining]), 'all_readable': True}))


def test_resolve_retry_is_bounded_and_does_not_expose_url(tmp_path, monkeypatch):
    cap = LiveCapture('https://live.bilibili.com/123', tmp_path, threading.Event())
    attempts = []
    def fail():
        attempts.append(1)
        raise RuntimeError('https://secret.example/?token=private')
    monkeypatch.setattr(cap, '_resolve', fail)
    assert list(cap.chunks()) == []
    cap.close()
    assert len(attempts) == 3
    assert 'private' not in cap.error and 'https' not in cap.error

@pytest.mark.parametrize('url', ['http://live.bilibili.com/123', 'https://live.bilibili.com/blanc/123/'])
def test_normalizes_room_url(tmp_path, url):
    assert LiveCapture(url, tmp_path, threading.Event()).url == 'https://live.bilibili.com/123'


def test_frozen_downloader_dispatch(tmp_path, monkeypatch):
    from types import SimpleNamespace
    import app.arctime.live_capture as module
    calls = []
    def run(args, **kwargs):
        calls.append(args)
        return SimpleNamespace(returncode=0, stdout='https://fixture.example/stream\n')
    monkeypatch.setattr(module.sys, 'frozen', True, raising=False)
    monkeypatch.setattr(module.media, 'tool_path', lambda name: '/fixture/backend')
    monkeypatch.setattr(module.subprocess, 'run', run)
    cap = LiveCapture('https://live.bilibili.com/123', tmp_path, threading.Event())
    assert cap._resolve() == 'https://fixture.example/stream'
    assert calls[0][:2] == ['/fixture/backend', '--yt-dlp']
