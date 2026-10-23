import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.arctime import media


def test_clean_video_passes_full_decode(tmp_path):
    from app.arctime.video_integrity import validate_video_decode
    path = tmp_path / 'clean.mp4'
    subprocess.run([media.tool_path('ffmpeg'), '-v', 'error', '-f', 'lavfi', '-i',
                    'color=blue:s=64x64:r=24:d=1', '-c:v', 'libx264', str(path)],
                   check=True, capture_output=True)
    before = media.fingerprint(path)

    validate_video_decode(path, media.probe_video(path))

    assert media.fingerprint(path) == before


@pytest.mark.parametrize('exit_code,diagnostic', [(0, b'Could not find ref with POC 28\n'),
                                               (0, b'Error constructing the frame RPS.\n'),
                                               (1, b'')])
def test_decode_errors_are_rejected_even_with_zero_exit(tmp_path, monkeypatch, exit_code, diagnostic):
    from app.arctime import video_integrity
    path = tmp_path / 'recorded.mp4'
    path.write_bytes(b'preserved')

    def run(args, **kwargs):
        kwargs['stderr'].write(diagnostic + (b'https://private.example/?token=secret\n' if diagnostic else b''))
        return SimpleNamespace(returncode=exit_code)

    monkeypatch.setattr(video_integrity.subprocess, 'run', run)
    with pytest.raises(video_integrity.VideoDecodeError) as caught:
        video_integrity.validate_video_decode(path, 20)
    assert 'private' not in str(caught.value) and 'secret' not in str(caught.value)
    assert path.read_bytes() == b'preserved'


def test_decode_timeout_is_not_reported_as_healthy(tmp_path, monkeypatch):
    from app.arctime import video_integrity

    def timeout(args, **kwargs):
        raise subprocess.TimeoutExpired(['private-command'], 60)

    monkeypatch.setattr(video_integrity.subprocess, 'run', timeout)
    with pytest.raises(video_integrity.VideoDecodeError):
        video_integrity.validate_video_decode(tmp_path / 'source.mp4', 20)
