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
    monkeypatch.setattr(cap, '_is_offline', lambda: None)
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


def test_resolve_chooses_highest_quality_avc_flv_instead_of_hevc_hls(tmp_path, monkeypatch):
    from types import SimpleNamespace
    import yt_dlp
    import app.arctime.live_capture as module
    formats = [
        {'format_id': 'avc-low', 'vcodec': 'avc', 'ext': 'flv', 'protocol': 'https', 'quality': 1},
        {'format_id': 'avc-live', 'vcodec': 'avc', 'ext': 'flv', 'protocol': 'https', 'quality': 2},
        {'format_id': 'avc-hls', 'vcodec': 'avc', 'ext': 'fmp4', 'protocol': 'm3u8_native', 'quality': 2},
        {'format_id': 'hevc-hls', 'vcodec': 'hevc', 'ext': 'fmp4', 'protocol': 'm3u8_native', 'quality': 2},
    ]
    formats = [{**item, 'acodec': 'aac', 'url': f"https://fixture.invalid/{item['format_id']}"}
               for item in formats]
    def resolve(args, **kwargs):
        with yt_dlp.YoutubeDL({'quiet': True}) as downloader:
            select = downloader.build_format_selector(args[args.index('-f') + 1])
            chosen = list(select({'formats': formats, 'incomplete_formats': False, 'has_merged_format': False}))
        return SimpleNamespace(returncode=0 if chosen else 1,
                               stdout=chosen[0]['url'] + '\n' if chosen else '')
    monkeypatch.setattr(module.subprocess, 'run', resolve)
    cap = LiveCapture('https://live.bilibili.com/123', tmp_path, threading.Event())
    assert cap._resolve() == 'https://fixture.invalid/avc-live'


@pytest.mark.parametrize('codec,protocol,extension', [
    ('hevc', 'https', 'flv'), ('hevc', 'm3u8_native', 'fmp4'), ('avc', 'm3u8_native', 'fmp4')])
def test_resolve_does_not_fall_back_to_incompatible_live_variant(tmp_path, monkeypatch, codec, protocol, extension):
    from types import SimpleNamespace
    import yt_dlp
    import app.arctime.live_capture as module
    formats = [{'format_id': 'unsupported', 'vcodec': codec, 'acodec': 'aac', 'ext': extension,
                'protocol': protocol, 'url': 'https://fixture.invalid/unsupported'}]
    def resolve(args, **kwargs):
        with yt_dlp.YoutubeDL({'quiet': True}) as downloader:
            selected = list(downloader.build_format_selector(args[args.index('-f') + 1])(
                {'formats': formats, 'incomplete_formats': False, 'has_merged_format': False}))
        return SimpleNamespace(returncode=0 if selected else 1,
                               stdout=selected[0]['url'] + '\n' if selected else '')
    monkeypatch.setattr(module.subprocess, 'run', resolve)
    with pytest.raises(ValueError, match='AVC'):
        LiveCapture('https://live.bilibili.com/123', tmp_path, threading.Event())._resolve()


@pytest.mark.parametrize('status,expected', [(0, True), (1, False), (2, True), (None, None), ('0', None)])
def test_room_end_requires_explicit_platform_status(tmp_path, monkeypatch, status, expected):
    import httpx
    import app.arctime.live_capture as module
    def lookup(url, **kwargs):
        assert url == 'https://api.live.bilibili.com/room/v1/Room/get_info'
        assert kwargs['params'] == {'id': '123'}
        assert kwargs['timeout'] <= 10 and kwargs['trust_env'] is False
        return httpx.Response(200, json={'code': 0, 'data': {'live_status': status}},
                              request=httpx.Request('GET', url))
    monkeypatch.setattr(module.httpx, 'get', lookup)
    cap = LiveCapture('https://live.bilibili.com/123', tmp_path, threading.Event())
    assert cap._is_offline() is expected


@pytest.mark.parametrize('payload', [{'code': -1, 'data': {'live_status': 0}},
                                    {'code': 0, 'data': None}, {'code': 0}, []])
def test_invalid_room_response_does_not_claim_live_ended(tmp_path, monkeypatch, payload):
    import httpx
    import app.arctime.live_capture as module
    monkeypatch.setattr(module.httpx, 'get', lambda url, **kwargs: httpx.Response(
        200, json=payload, request=httpx.Request('GET', url)))
    assert LiveCapture('https://live.bilibili.com/123', tmp_path, threading.Event())._is_offline() is None


def test_room_lookup_timeout_is_unknown(tmp_path, monkeypatch):
    import httpx
    import app.arctime.live_capture as module
    def timeout(*args, **kwargs):
        raise httpx.ReadTimeout('private diagnostics')
    monkeypatch.setattr(module.httpx, 'get', timeout)
    assert LiveCapture('https://live.bilibili.com/123', tmp_path, threading.Event())._is_offline() is None


@pytest.mark.parametrize('offline,attempts,reason', [(True, 1, 'live_ended'),
                                                  (False, 3, 'connection_lost'),
                                                  (None, 3, 'connection_lost')])
def test_eof_is_only_normal_end_after_platform_confirmation(tmp_path, monkeypatch, offline, attempts, reason):
    from types import SimpleNamespace
    import app.arctime.live_capture as module
    cap = LiveCapture('https://live.bilibili.com/123', tmp_path, threading.Event())
    resolved = []
    monkeypatch.setattr(cap, '_resolve', lambda: resolved.append(1) or 'https://fixture.invalid/stream')
    monkeypatch.setattr(cap, '_is_offline', lambda: offline)
    monkeypatch.setattr(cap.stop, 'wait', lambda timeout: False)
    monkeypatch.setattr(module.subprocess, 'Popen', lambda *args, **kwargs: SimpleNamespace(poll=lambda: 0))
    cap._record()
    assert len(resolved) == attempts and cap.done.is_set()
    assert cap.end_reason == reason
    assert bool(cap.error) is (offline is not True)


def test_user_stop_never_becomes_platform_end(tmp_path, monkeypatch):
    stop = threading.Event()
    stop.set()
    cap = LiveCapture('https://live.bilibili.com/123', tmp_path, stop)
    def unexpected():
        pytest.fail('Explicit stop must not make a room request')
    monkeypatch.setattr(cap, '_is_offline', unexpected)
    cap._record()
    assert cap.end_reason == 'stopped' and cap.error is None


def test_stop_during_room_lookup_does_not_claim_platform_end(tmp_path, monkeypatch):
    from types import SimpleNamespace
    import app.arctime.live_capture as module
    cap = LiveCapture('https://live.bilibili.com/123', tmp_path, threading.Event())
    monkeypatch.setattr(cap, '_resolve', lambda: 'https://fixture.invalid/stream')
    monkeypatch.setattr(module.subprocess, 'Popen', lambda *args, **kwargs: SimpleNamespace(poll=lambda: 0))
    def offline():
        cap.stop.set()
        return True
    monkeypatch.setattr(cap, '_is_offline', offline)
    cap._record()
    assert cap.end_reason == 'stopped' and cap.error is None


def test_confirmed_end_preserves_prior_disconnection_warning(tmp_path, monkeypatch):
    from types import SimpleNamespace
    import app.arctime.live_capture as module
    cap = LiveCapture('https://live.bilibili.com/123', tmp_path, threading.Event())
    statuses = iter([False, True])
    monkeypatch.setattr(cap, '_resolve', lambda: 'https://fixture.invalid/stream')
    monkeypatch.setattr(cap, '_is_offline', lambda: next(statuses))
    monkeypatch.setattr(cap.stop, 'wait', lambda timeout: False)
    monkeypatch.setattr(module.subprocess, 'Popen', lambda *args, **kwargs: SimpleNamespace(poll=lambda: 0))
    cap._record()
    assert cap.end_reason == 'live_ended' and '断流' in cap.error


def test_real_media_eof_is_sealed_without_reconnecting_when_room_ended(tmp_path, monkeypatch):
    import subprocess
    from app.arctime import media
    source = tmp_path / 'fixture.mp4'
    subprocess.run([media.tool_path('ffmpeg'), '-v', 'error', '-f', 'lavfi', '-i',
                    'color=c=green:s=64x64:r=5', '-t', '2', '-c:v', 'libx264',
                    '-preset', 'ultrafast', str(source)], capture_output=True, check=True)
    cap = LiveCapture('https://live.bilibili.com/123', tmp_path, threading.Event())
    monkeypatch.setattr(cap, '_resolve', lambda: str(source))
    monkeypatch.setattr(cap, '_is_offline', lambda: True)
    paths = list(cap.chunks())
    cap.close()
    assert len(paths) == 1 and len(list(tmp_path.glob('capture-*'))) == 1
    assert media.probe_video(paths[0]) == 2
    assert cap.end_reason == 'live_ended' and cap.error is None
    assert not cap.thread.is_alive()
