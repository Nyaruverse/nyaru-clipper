#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/_release_smoke_common.sh"
export SMOKE_PATH_LABEL="companion"

if [[ $# -lt 1 || $# -gt 2 || ! -d "$1" ]]; then
  printf 'usage: %s TEMP_PARENT [FROZEN_BACKEND]\n' "$0" >&2
  exit 2
fi
python="${BACKEND_PYTHON:-${BACKEND_PYTHON_PATH}}"
owned_root="$(mktemp -d "${1%/}/companion-smoke.XXXXXX")"
child_pid=""
cleanup() {
  local status="$?"
  trap - EXIT
  if [[ -n "${child_pid}" ]]; then
    kill "${child_pid}" >/dev/null 2>&1 || true
    wait "${child_pid}" >/dev/null 2>&1 || true
  fi
  cat "${owned_root}/backend.log" 2>/dev/null || true
  rm -rf "${owned_root}"
  exit "${status}"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

export APP_DATA_DIR="${owned_root}/data"
export PYTHONPATH="${ROOT_DIR}/backend${PYTHONPATH:+:${PYTHONPATH}}"
url=""
if [[ $# -eq 2 ]]; then
  "$2" --data "${APP_DATA_DIR}" --ready "${owned_root}/ready.json" --parent-pid "$$" >"${owned_root}/backend.log" 2>&1 &
else
  port="$("${python}" - <<'PY'
import socket
with socket.socket() as listener:
    listener.bind(("127.0.0.1", 0))
    print(listener.getsockname()[1])
PY
)"
  url="http://127.0.0.1:${port}"
  "${python}" -m app.arctime.cli gui --output-dir "${owned_root}/runs" --port "${port}" >"${owned_root}/backend.log" 2>&1 &
fi
child_pid="$!"
COMPANION_SMOKE_URL="$("${python}" - "${child_pid}" "${owned_root}/ready.json" "${url}" <<'PY'
import json
import os
from pathlib import Path
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

pid, ready_path, url = sys.argv[1:]
deadline = time.monotonic() + 60
last_error = "no ready response"
while time.monotonic() < deadline:
    try:
        os.kill(int(pid), 0)
    except ProcessLookupError:
        sys.exit("Companion exited before readiness (check backend startup/bind failure)")
    try:
        if not url and Path(ready_path).is_file():
            url = json.loads(Path(ready_path).read_text())["url"]
        if url:
            parsed = urllib.parse.urlsplit(url)
            if parsed.scheme != "http" or parsed.hostname != "127.0.0.1" or not parsed.port:
                sys.exit("Companion ready URL must use a loopback HTTP port")
            with urllib.request.urlopen(url + "/companion-api/jobs", timeout=1) as response:
                if response.status == 200 and json.load(response) == []:
                    print(url)
                    break
                last_error = "jobs endpoint is not an empty workspace"
    except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
        last_error = str(exc)
    time.sleep(0.1)
else:
    sys.exit(f"Companion readiness timed out: {last_error}")
PY
)"
export COMPANION_SMOKE_URL
kill -0 "${child_pid}"
smoke_log "ready at ${COMPANION_SMOKE_URL} with disposable root ${owned_root}"
smoke_pnpm exec playwright test --config playwright.companion.config.ts --reporter=line
