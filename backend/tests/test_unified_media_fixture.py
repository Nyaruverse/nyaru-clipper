from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from app.arctime import media
from app.arctime.subtitle_document import DocumentStore
from app.arctime.subtitle_style import SubtitleStyle
from unification_media import build_media


@pytest.mark.skipif(sys.platform != 'darwin', reason='P0 speech fixture uses installed macOS voices; reuse its pinned bundle on Linux/WSL')
def test_real_media_and_old_reader_fixture(tmp_path: Path) -> None:
    root = build_media(tmp_path / 'unified-p0')
    manifest = json.loads((root / 'manifest.json').read_bytes())
    assert manifest['status'] == 'prepared_fixture'
    probe = subprocess.run([media.tool_path('ffprobe'), '-v', 'error', '-select_streams', 'v:0',
        '-show_entries', 'stream=width,height,nb_frames,avg_frame_rate,duration', '-of', 'json', str(root / 'source.mp4')],
        capture_output=True, text=True, check=True, timeout=30)
    stream = json.loads(probe.stdout)['streams'][0]
    assert (stream['width'], stream['height'], stream['nb_frames'], stream['avg_frame_rate']) == (1280, 720, '4501', '30/1')
    assert abs(float(stream['duration']) - 4501 / 30) < 1 / 30
    for name, digest in manifest['files'].items():
        assert media.fingerprint(root / name) == digest
    for level in ['R0', 'R1', 'R2']:
        directory = root / 'state/rollback' / level / 'tasks/abcdef123456'
        before = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in directory.iterdir()}
        document = DocumentStore().load(directory, SubtitleStyle())
        assert document.revision == (1 if level == 'R2' else 0)
        assert len(document.cues) == (5000 if level == 'R2' else 2)
        after = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in directory.iterdir()}
        assert after == before
    assert len(list((root / 'live').glob('chunk-*.mp4'))) == 8
    assert [round(media.probe_video(path), 3) for path in sorted((root / 'live').glob('chunk-*.mp4'))] == [20.] * 7 + [7.]
    assert (root / 'expected/preview.png').read_bytes().startswith(b'\x89PNG\r\n\x1a\n')
    assert len(list((root / 'expected').glob('frame-*.png'))) == 7
    import cv2
    import numpy as np
    background = cv2.imread(str(root / 'expected/frame-0029.png'))
    assert background is not None
    for frame in [29, 30, 31, 60, 88, 89, 90]:
        pixels = cv2.imread(str(root / f'expected/frame-{frame:04d}.png'))
        assert pixels is not None
        difference = cv2.absdiff(pixels, background)
        assert bool(np.any(difference[480:720, :1280])) == (frame in {30, 31, 60, 88, 89})
        assert not np.any(difference[:480])
    print(f'P0_FIXTURE_BUNDLE={root}')
