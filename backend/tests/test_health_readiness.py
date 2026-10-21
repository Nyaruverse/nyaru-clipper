from collections.abc import Iterator
from contextlib import closing, contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import json
import os
import shutil
import sqlite3
import subprocess
import threading
import time

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import text


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    database_dir = tmp_path / "database"
    database_dir.mkdir()
    monkeypatch.setenv("APP_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("APP_DATABASE_URL", f"sqlite:///{database_dir / 'tasks.sqlite3'}")
    from app.db import get_engine, reset_db_runtime
    from app.main import app

    reset_db_runtime()
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client
    get_engine().dispose()
    reset_db_runtime()


def test_readiness_recovers_after_database_directory_moves(client: TestClient, tmp_path: Path) -> None:
    from app.db import get_engine

    assert client.get("/api/v2/tasks").status_code == 200
    assert client.get("/api/health").status_code == 200
    database_dir = tmp_path / "database"
    parked_dir = tmp_path / "parked"
    database_dir.rename(parked_dir)
    try:
        with get_engine().connect() as connection:
            connection.execute(text("SELECT 1 FROM task LIMIT 1"))
        unavailable = client.get("/api/health")
        get_engine().dispose()
        assert client.get("/api/v2/tasks").status_code == 500
        assert unavailable.status_code == 503
        assert unavailable.json()["status"] == "error"
        assert unavailable.json()["database"] == "error"
        assert unavailable.json()["storage"] == "ok"
        assert str(tmp_path) not in unavailable.text
        assert not database_dir.exists()
    finally:
        parked_dir.rename(database_dir)
    assert client.get("/api/v2/tasks").status_code == 200
    assert client.get("/api/health").status_code == 200


def test_readiness_exclusive_lock_is_bounded(client: TestClient, tmp_path: Path) -> None:
    database_path = tmp_path / "database" / "tasks.sqlite3"
    with closing(sqlite3.connect(database_path)) as lock:
        lock.execute("BEGIN EXCLUSIVE")
        started = time.monotonic()
        response = client.get("/api/health")
        elapsed = time.monotonic() - started
        lock.rollback()
    assert response.status_code == 503
    assert 0.9 <= elapsed < 2.0
    assert client.get("/api/health").status_code == 200


@pytest.mark.parametrize("database_state", ["missing", "empty", "corrupt"])
def test_readiness_rejects_unusable_database_without_creation(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, database_state: str
) -> None:
    database_path = tmp_path / "alternate.sqlite3"
    if database_state == "empty":
        with closing(sqlite3.connect(database_path)):
            pass
    elif database_state == "corrupt":
        database_path.write_text("not a SQLite database", encoding="utf-8")
    monkeypatch.setenv("APP_DATABASE_URL", f"sqlite:///{database_path}")
    response = client.get("/api/health")
    assert response.status_code == 503
    assert response.json()["database"] == "error"
    assert str(database_path) not in response.text
    if database_state == "missing":
        assert not database_path.exists()


@pytest.mark.parametrize("database_url", [
    "malformed-private-path", "postgresql://private:secret@host/database",
    "sqlite://", "sqlite:///:memory:", "sqlite:///file:shared?mode=memory&uri=true",
])
def test_readiness_rejects_unsupported_urls_safely(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, database_url: str
) -> None:
    monkeypatch.setenv("APP_DATABASE_URL", database_url)
    response = client.get("/api/health")
    assert response.status_code == 503
    assert response.json()["database"] == "error"
    assert database_url not in response.text
    assert "private" not in response.text
    assert "secret" not in response.text


@contextmanager
def health_server(http_status: int, payload: dict[str, str]) -> Iterator[int]:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            assert self.path == "/api/health"
            self.send_response(http_status)
            self.end_headers()
            self.wfile.write(json.dumps(payload).encode())

        def log_message(self, format: str, *args: str) -> None:
            return

    with ThreadingHTTPServer(("127.0.0.1", 0), Handler) as server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            yield server.server_port
        finally:
            server.shutdown()
            thread.join(timeout=2)


@pytest.mark.parametrize("case", [
    (200, {"status": "ok", "database": "ok"}, 0),
    (200, {"status": "ok", "database": "error"}, 1),
    (200, {"status": "error", "database": "ok"}, 1),
    (200, {}, 1),
    (503, {"status": "ok", "database": "ok"}, 1),
])
@pytest.mark.parametrize("consumer", ["shared", "smoke"])
def test_shared_readiness_checks_http_and_payload(
    case: tuple[int, dict[str, str], int], consumer: str
) -> None:
    http_status, payload, expected = case
    root = Path(__file__).resolve().parents[2]
    command = (
        'source scripts/_dev_common.sh; wait_for_api_readiness "$1" 1'
        if consumer == "shared" else
        'source scripts/_release_smoke_common.sh; '
        'python3() { TIMEOUT_SECONDS=1 command python3 "$@"; }; '
        'APP_PORT="$2" verify_api_health'
    )
    with health_server(http_status, payload) as port:
        result = subprocess.run(
            ["bash", "-c", command, "readiness-test",
             f"http://127.0.0.1:{port}/api/health", str(port)],
            cwd=root, capture_output=True, text=True, timeout=8, check=False,
        )
    assert result.returncode == expected, result.stdout + result.stderr
    assert "command not found" not in result.stderr


@pytest.mark.parametrize("http_status", [200, 503])
def test_dev_up_readiness_failure_cleans_api_and_blocks_children(tmp_path: Path, http_status: int) -> None:
    root = Path(__file__).resolve().parents[2]
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    for name in ("dev_up.sh", "_dev_common.sh"):
        shutil.copyfile(root / "scripts" / name, scripts / name)
    with (scripts / "_dev_common.sh").open("a") as helper:
        helper.write('\npython3() { TIMEOUT_SECONDS=1 command python3 "$@"; }\n')
    (scripts / "dev_api.sh").write_text(
        '#!/usr/bin/env bash\ntrap \'touch "$ROOT_DIR/api-stopped"; exit 0\' TERM\n'
        'while true; do sleep 0.1; done\n', encoding="utf-8",
    )
    for name in ("dev_worker.sh", "dev_web.sh"):
        (scripts / name).write_text('#!/usr/bin/env bash\ntouch "$ROOT_DIR/child-started"\n', encoding="utf-8")
    for script in scripts.glob("dev_*.sh"):
        script.chmod(0o755)
    commands = tmp_path / ".bin"
    commands.mkdir()
    for name in ("uv", "pnpm"):
        command = commands / name
        command.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
        command.chmod(0o755)
    with health_server(http_status, {"status": "ok", "database": "error"}) as port:
        result = subprocess.run(
            ["bash", str(scripts / "dev_up.sh")], cwd=tmp_path,
            env={**os.environ, "APP_PORT": str(port), "APP_DATA_DIR": str(tmp_path / "data")},
            capture_output=True, text=True, timeout=8, check=False,
        )
    assert result.returncode == 1, result.stdout + result.stderr
    assert "timed out waiting for api readiness" in result.stderr
    assert (tmp_path / "api-stopped").exists()
    assert not (tmp_path / "child-started").exists()
