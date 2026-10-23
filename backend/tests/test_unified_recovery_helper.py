from __future__ import annotations

import importlib
import json
import os
import subprocess
import time
from pathlib import Path

import pytest
import httpx



from test_unified_recovery import recovery_fixture, release_fixture, scripts


def test_archived_helper_uses_separate_working_copy_and_blocks_online_or_processing_actions(tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch) -> None:
    from app.arctime import workflow
    from app.services.subtitles import SubtitleSegment
    storage = scripts(monkeypatch)
    builder = importlib.import_module('build_unified_recovery')
    recipe, roots, saved = recovery_fixture(tmp_path, monkeypatch)
    legacy = tmp_path / 'legacy-snapshot'
    (legacy / 'runs').mkdir(parents=True)
    source = tmp_path / 'input.mp4'
    subprocess.run(['/opt/homebrew/opt/ffmpeg@7/bin/ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'color=s=640x360:r=25',
        '-t', '3', '-c:v', 'libx264', '-y', str(source)], check=True, capture_output=True, timeout=30)

    class Adapter:
        def identity(self):
            return {'engine': 'frozen-fixture', 'language': 'ja'}
        def transcribe(self, *args):
            return [SubtitleSegment('1', .5, 2., '旧格式的本地字幕')]

    directory = workflow.create_run('https://example.invalid', legacy / 'runs', [(0., 3.)], None, Adapter(), local_source=source)
    workflow.resume_run(directory, Adapter())
    before = storage.inventory(legacy)
    bundle = builder.freeze(tmp_path / 'archived-helper', legacy_helper=True)
    recipe['reader_bundle'] = {'path': str(bundle), 'sha256': storage.sha(bundle)}
    recipe['legacy'] = {'snapshot': str(legacy), 'files': before}
    launcher = None
    try:
        manifest = storage.snapshot(recipe, tmp_path / 'snapshot', install_seal=True)
        output = tmp_path / 'legacy-recovery'
        launcher = subprocess.Popen([str(bundle.parent / 'runtime/bin/python3.11'), '-I', '-S', '-B',
            str(bundle.parent / 'reader.py'), '--mode', 'legacy-browser', '--manifest', str(manifest), '--output-root', str(output)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, start_new_session=True)
        deadline = time.monotonic() + 45
        ready = output / 'ready.json'
        while not ready.exists() and launcher.poll() is None and time.monotonic() < deadline:
            time.sleep(.1)
        assert ready.exists(), (output / 'helper.log').read_text() if (output / 'helper.log').exists() else launcher.communicate(timeout=2)
        status = json.loads(ready.read_bytes())
        with httpx.Client(base_url=status['url'], timeout=10) as client:
            for _ in range(100):
                response = client.get('/companion-api/jobs')
                if response.status_code == 200:
                    break
                time.sleep(.1)
            assert response.status_code == 200, response.text
            assert response.json()[0]['id'] == directory.name
            base_url = '/companion-api/jobs/' + directory.name
            document = client.get(base_url + '/subtitle-document')
            assert document.status_code == 200, document.text
            draft = document.json()
            draft['cues'][0]['text'] = '旧界面副本中的编辑'
            changed = client.post(base_url + '/subtitle-document', json=draft)
            assert changed.status_code == 200 and changed.json()['revision'] == 1, changed.text
            assert client.get(base_url + '/subtitle-document').json()['cues'][0]['text'] == '旧界面副本中的编辑'
            assert client.get('/').status_code == 200
            for endpoint in ['/companion-api/jobs', base_url + '/translate', base_url + '/resume', '/companion-api/chatgpt/login']:
                assert client.post(endpoint, json={}).status_code == 403
            assert client.get('/companion-api/chatgpt').status_code == 403
        assert storage.inventory(legacy) == before
        assert (output / 'working/runs' / directory.name / 'subtitle-document.json').is_file()
    finally:
        if launcher is not None and launcher.poll() is None:
            launcher.terminate()
            launcher.wait(timeout=25)
        try:
            if 'ready' in locals():
                assert not ready.exists()
                with pytest.raises(ProcessLookupError):
                    os.kill(status['pid'], 0)
        finally:
            release_fixture(tmp_path)
