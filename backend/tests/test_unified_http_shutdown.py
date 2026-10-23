from __future__ import annotations

import json
import signal
import subprocess
import sys
import time
from pathlib import Path

import httpx

from app.services.unified_runtime import initialize


def test_sigterm_closes_a_real_event_stream_before_draining_host(tmp_path: Path) -> None:
    model = tmp_path / 'model.bin'
    model.write_bytes(b'fixture; inference forbidden')
    manifest = initialize(tmp_path / 'runtime', tmp_path / 'credentials', model)
    ready = tmp_path / 'ready.json'
    process = subprocess.Popen([sys.executable, '-m', 'app.arctime.unified_cli', 'serve',
        '--runtime', str(manifest), '--ready', str(ready)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        deadline = time.monotonic() + 20
        while not ready.exists() and process.poll() is None and time.monotonic() < deadline:
            time.sleep(.05)
        assert ready.exists(), process.communicate(timeout=5)
        url = json.loads(ready.read_bytes())['url']
        with httpx.stream('GET', url + '/api/v2/events', timeout=5, trust_env=False) as response:
            assert response.status_code == 200
            process.terminate()
            output, errors = process.communicate(timeout=8)
            assert process.returncode == -signal.SIGTERM, (output, errors)
            assert 'CancelledError' not in errors
    finally:
        if process.poll() is None:
            process.kill()
            process.communicate(timeout=5)
