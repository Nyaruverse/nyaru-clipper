from __future__ import annotations

import os
import shutil
import subprocess
import sys
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def executable(path: Path, body: str) -> None:
    path.write_text("#!/usr/bin/env bash\nset -eu\n" + body)
    path.chmod(0o755)


@pytest.mark.parametrize("failure", ["backend", "unit", "build", "browser", "none"])
def test_downstream_preserves_exit_and_stops(tmp_path: Path, failure: str) -> None:
    checkout = tmp_path / "checkout"
    (checkout / "scripts").mkdir(parents=True)
    (checkout / "web").mkdir()
    for name in ("_release_smoke_common.sh", "_dev_common.sh"):
        shutil.copy2(ROOT / "scripts" / name, checkout / "scripts" / name)
    commands = tmp_path / "bin"
    commands.mkdir()
    log = tmp_path / "calls"
    executable(commands / "python", 'echo backend >> "$CALLS"\n[[ "$FAILURE" != backend ]] || exit 37\n')
    executable(commands / "corepack", '''
[[ "$PWD" == */web ]]
[[ "$1" == pnpm ]]
shift
case "$1" in
  test) stage=unit ;;
  build) stage=build ;;
  exec) stage=browser ;;
  *) exit 89 ;;
esac
echo "$stage" >> "$CALLS"
[[ "$FAILURE" != "$stage" ]] || exit 37
''')
    result = subprocess.run(
        ["bash", "-c", 'source "$1"; run_downstream_smoke_suite', "smoke", str(checkout / "scripts/_release_smoke_common.sh")],
        env={**os.environ, "PATH": f"{commands}:{os.environ['PATH']}", "BACKEND_PYTHON": str(commands / "python"), "CALLS": str(log), "FAILURE": failure},
        capture_output=True, text=True, timeout=15,
    )
    stages = ["backend", "unit", "build", "browser"]
    expected = stages if failure == "none" else stages[:stages.index(failure) + 1]
    assert result.returncode == (0 if failure == "none" else 37), result.stdout + result.stderr
    assert log.read_text().splitlines() == expected


@pytest.mark.parametrize("mode,code", [("success", 0), ("browser_failure", 41), ("startup_failure", 1), ("signal", 143)])
def test_companion_cleans_only_owned_resources(tmp_path: Path, mode: str, code: int) -> None:
    parent = tmp_path / "data-parent"
    parent.mkdir()
    sentinel = parent / "existing-data"
    sentinel.write_text("preserve")
    commands = tmp_path / "bin"
    commands.mkdir()
    record = tmp_path / "owned.json"
    backend = commands / "frozen"
    backend.write_text(f"#!{sys.executable}\n" + '''
import argparse, json, os
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
parser = argparse.ArgumentParser()
parser.add_argument('--data')
parser.add_argument('--ready')
parser.add_argument('--parent-pid')
args = parser.parse_args()
Path(os.environ['RECORD']).write_text(json.dumps({'pid': os.getpid(), 'root': str(Path(args.data).parent)}))
if os.environ['MODE'] == 'startup_failure':
    raise SystemExit(29)
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'[]')
server = HTTPServer(('127.0.0.1', 0), Handler)
Path(args.ready).write_text(json.dumps({'url': f'http://127.0.0.1:{server.server_port}'}))
server.serve_forever()
''')
    backend.chmod(0o755)
    executable(commands / "corepack", '''
[[ "$COMPANION_SMOKE_URL" == http://127.0.0.1:* ]]
[[ "$MODE" != browser_failure ]] || exit 41
if [[ "$MODE" == signal ]]; then
  kill -TERM "$SMOKE_OWNER"
fi
''')
    result = subprocess.run(
        ["bash", "-c", 'export SMOKE_OWNER=$$; exec bash "$@"', "test", str(ROOT / "scripts/release_smoke_companion.sh"), str(parent), str(backend)],
        env={**os.environ, "PATH": f"{commands}:{os.environ['PATH']}", "BACKEND_PYTHON": sys.executable, "RECORD": str(record), "MODE": mode},
        capture_output=True, text=True, timeout=20,
    )
    assert result.returncode == code, result.stdout + result.stderr
    owned = json.loads(record.read_text())
    assert not Path(owned["root"]).exists()
    assert list(parent.iterdir()) == [sentinel]
    assert sentinel.read_text() == "preserve"
    with pytest.raises(ProcessLookupError):
        os.kill(owned["pid"], 0)
