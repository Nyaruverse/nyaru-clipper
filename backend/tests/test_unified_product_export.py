from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.arctime import media
from app.arctime.gui import create_app
from app.arctime.subtitle_encoding import subtitle_ffmpeg
from unified_edit_fixture import make_editor_fixture
from unification_media import build_media


@pytest.mark.skipif(sys.platform != 'darwin', reason='Uses the pinned macOS voice/font reference generator')
def test_actual_product_api_burn_matches_frozen_reference(tmp_path: Path) -> None:
    import cv2
    import numpy as np
    bundle = build_media(tmp_path / 'reference')
    fixture = make_editor_fixture(tmp_path / 'candidate', bundle)
    expected = json.loads((bundle / 'expected/document.json').read_bytes())
    calls = []
    recording = [True]

    def capture(event: str, args: tuple) -> None:
        if recording[0] and event == 'subprocess.Popen':
            calls.append(args[1])

    sys.addaudithook(capture)
    try:
        with TestClient(create_app(fixture.editor, artifacts=(fixture.artifacts,))) as client:
            url = f'/companion-api/jobs/{fixture.artifacts.source.task_id}'
            document = client.get(url + '/subtitle-document').json()
            document['style'] = expected['style']
            document['cues'][0]['text'] = 'Unified fixture'
            saved = client.post(url + '/subtitle-document', json=document)
            assert saved.status_code == 200, saved.text
            document = saved.json()
            preview = client.post(url + '/subtitle-preview', json={'document': document, 'time': 3., 'bilingual': False})
            assert preview.status_code == 200 and preview.content.startswith(b'\x89PNG'), preview.text[:100]
            png = cv2.imdecode(np.frombuffer(preview.content, dtype=np.uint8), cv2.IMREAD_UNCHANGED)
            reference_png = cv2.imread(str(bundle / 'expected/preview.png'), cv2.IMREAD_UNCHANGED)
            assert np.array_equal(png, reference_png)
            for kind in ['ass', 'burn']:
                submitted = client.post(url + '/subtitle-export', json={
                    'kind': kind, 'video': 'clip-001.mp4', 'bilingual': False,
                    'style': document['style'], 'document': document})
                assert submitted.status_code == 202, submitted.text
                deadline = time.monotonic() + 60
                while True:
                    state = client.get(url + '/subtitle-exports').json()
                    if state['active']['state'] in {'completed', 'failed'}:
                        break
                    assert time.monotonic() < deadline
                    time.sleep(.02)
                assert state['active']['state'] == 'completed', state
                output = next(output for output in state['outputs'] if output['kind'] == kind)
                response = client.get(url + '/files/' + output['filename'])
                assert response.status_code == 200
                if kind == 'ass':
                    assert '0:00:01.00,0:00:03.00' in response.text
                else:
                    product = tmp_path / 'actual-product.mp4'
                    product.write_bytes(response.content)
                    product_id = output['id']
            repeated = client.post(url + '/subtitle-export', json={
                'kind': 'burn', 'video': 'clip-001.mp4', 'bilingual': False,
                'style': document['style'], 'document': document})
            assert repeated.status_code == 202
            deadline = time.monotonic() + 60
            while client.get(url + '/subtitle-exports').json()['active']['state'] == 'exporting':
                assert time.monotonic() < deadline
                time.sleep(.02)
            outputs = client.get(url + '/subtitle-exports').json()['outputs']
            assert [output['id'] for output in outputs if output['kind'] == 'burn'] == [product_id]
    finally:
        recording[0] = False
    encodes = [command for command in calls if '-progress' in command]
    assert len(encodes) == 1
    command = encodes[0]
    for key, value in {'-c:v': 'libx264', '-preset': 'fast', '-crf': '20', '-c:a': 'aac', '-movflags': '+faststart'}.items():
        assert command[command.index(key) + 1] == value
    probe = subprocess.run([media.tool_path('ffprobe'), '-v', 'error', '-show_streams', '-show_format', '-of', 'json', str(product)],
                           capture_output=True, text=True, check=True, timeout=30)
    metadata = json.loads(probe.stdout)
    assert abs(float(metadata['format']['duration']) - 5.) <= 1 / 30
    assert {stream['codec_type'] for stream in metadata['streams']} == {'audio', 'video'}
    assert all(abs(float(stream.get('start_time', 0))) <= 1 / 30 for stream in metadata['streams'])
    subprocess.run([subtitle_ffmpeg(), '-v', 'error', '-i', str(product), '-f', 'null', '-'], check=True, capture_output=True, timeout=30)
    frames = {}
    for number in [29, 30, 31, 60, 88, 89, 90]:
        path = tmp_path / f'product-{number}.png'
        subprocess.run([subtitle_ffmpeg(), '-v', 'error', '-nostdin', '-n', '-i', str(product),
            '-vf', f'select=eq(n\\,{number}),format=rgb24', '-frames:v', '1', str(path)], check=True, capture_output=True, timeout=30)
        frames[number] = cv2.cvtColor(cv2.imread(str(path)), cv2.COLOR_BGR2RGB)
    measurements = []
    for number, pixels in frames.items():
        expected_pixels = cv2.cvtColor(cv2.imread(str(bundle / f'expected/frame-{number:04d}.png')), cv2.COLOR_BGR2RGB)
        roi = pixels[480:720, :1280].astype(float)
        expected_roi = expected_pixels[480:720, :1280].astype(float)
        rmse = float(np.sqrt(np.mean((roi - expected_roi) ** 2)))
        assert rmse <= 8., (number, rmse)
        actual_mask = np.max(np.abs(pixels.astype(float) - frames[29].astype(float)), axis=2) >= 32
        background = cv2.cvtColor(cv2.imread(str(bundle / 'expected/frame-0029.png')), cv2.COLOR_BGR2RGB)
        expected_mask = np.max(np.abs(expected_pixels.astype(float) - background.astype(float)), axis=2) >= 32
        assert bool(np.any(actual_mask)) == bool(np.any(expected_mask))
        bbox_error = 0
        if np.any(expected_mask):
            ay, ax = np.where(actual_mask)
            ey, ex = np.where(expected_mask)
            bbox_error = max(abs(int(a) - int(b)) for a, b in zip(
                [ax.min(), ay.min(), ax.max(), ay.max()], [ex.min(), ey.min(), ex.max(), ey.max()], strict=True))
            assert bbox_error <= 2, (number, bbox_error)
        measurements.append({'frame': number, 'rgb_rmse': rmse, 'bbox_error': bbox_error})
    assert fixture.source_hashes == fixture.current_source_hashes()
    media.write_json(tmp_path / 'product-evidence.json', {'artifact_id': product_id,
        'command': [part.replace(str(fixture.root), '<candidate>') for part in command],
        'sha256': media.fingerprint(product), 'foreground_delta': 32, 'measurements': measurements})
