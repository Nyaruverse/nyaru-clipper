from contextlib import contextmanager
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


def _deny_mkdir(*args, **kwargs):
    pytest.fail("Read paths must never call mkdir")


@pytest.fixture
def read_bytes(monkeypatch):
    """Measure actual reads from log handles, including the old text reader."""
    original_open = Path.open
    sizes = []

    @contextmanager
    def measured_open(path, *args, **kwargs):
        with original_open(path, *args, **kwargs) as stream:
            if path.suffix != ".log" or "r" not in stream.mode:
                yield stream
                return

            class Reader:
                def read(self, size=-1):
                    value = stream.read(size)
                    sizes.append(len(value.encode("utf-8") if isinstance(value, str) else value))
                    return value

                def seek(self, *args):
                    return stream.seek(*args)

                def tell(self):
                    return stream.tell()

            yield Reader()

    monkeypatch.setattr(Path, "open", measured_open)
    return sizes


@pytest.mark.parametrize("configured", [False, True])
def test_path_lookups_never_create_missing_directories(tmp_path, monkeypatch, configured):
    from app import paths
    from app.db import get_database_url
    from app.services.storage import get_task_root, get_tasks_root, resolve_task_artifact_path, summarize_stage_log

    data_dir = tmp_path / "missing-data"
    monkeypatch.setattr(paths, "_default_data_dir", data_dir, raising=False)
    monkeypatch.setattr(paths, "Path", lambda value: data_dir if value == "/data" else Path(value))
    if configured:
        monkeypatch.setenv("APP_DATA_DIR", str(data_dir))
    else:
        monkeypatch.delenv("APP_DATA_DIR", raising=False)
    monkeypatch.setenv("APP_DATABASE_URL", "sqlite:///explicit.sqlite")
    monkeypatch.setattr(Path, "mkdir", _deny_mkdir)

    assert paths.get_data_dir() == data_dir
    assert get_database_url() == "sqlite:///explicit.sqlite"
    assert get_tasks_root() == data_dir / "tasks"
    assert get_task_root("absent") == data_dir / "tasks" / "absent"
    artifact = data_dir / "tasks" / "absent" / "reports" / "task-report.md"
    assert resolve_task_artifact_path("absent", artifact) == artifact.resolve()
    assert summarize_stage_log("absent", "asr") is None
    assert not data_dir.exists()


@pytest.mark.parametrize("payload,expected", [
    (b"", None),
    (b" \n\t\r\n", None),
    (b"first\nlast\n \n\t\r\n", "last"),
    ("first\n字幕完了".encode(), "字幕完了"),
    (b"token=" + b"s" * (64 * 1024 + 5), None),
    (b"token=" + b"s" * (64 * 1024 + 5) + b"\n", None),
    (b"earlier\n" + b"\n" * (64 * 1024 + 5), None),
    (b"prefix\n" + "密".encode() * 23000 + "\n字幕完了\n".encode(), "字幕完了"),
    (b"first\ninvalid \xff", "invalid \ufffd"),
], ids=["empty", "whitespace", "trailing-blanks", "utf8", "overlong", "overlong-newline", "blank-window", "utf8-cut", "invalid-utf8"])
def test_log_tail_boundaries(tmp_path, monkeypatch, payload, expected):
    from app.services.storage import log_file_for_stage, summarize_stage_log

    monkeypatch.setenv("APP_DATA_DIR", str(tmp_path / "data"))
    log_file_for_stage("one", "asr").write_bytes(payload)
    monkeypatch.setattr(Path, "mkdir", _deny_mkdir)
    assert summarize_stage_log("one", "asr") == expected


def test_ten_megabyte_log_reads_at_most_64_kib(tmp_path, monkeypatch, read_bytes):
    from app.services.storage import log_file_for_stage, summarize_stage_log

    monkeypatch.setenv("APP_DATA_DIR", str(tmp_path / "data"))
    path = log_file_for_stage("one", "asr")
    payload = b"older line\n" * 1_000_000 + b"token=synthetic-secret\n\n"
    path.write_bytes(payload)
    assert path.stat().st_size >= 10_000_000
    assert summarize_stage_log("one", "asr") == "token=synthetic-secret"
    assert 0 < sum(read_bytes) <= 64 * 1024
    print({"file_bytes": path.stat().st_size, "read_bytes": sum(read_bytes)})


@pytest.mark.parametrize("error", [PermissionError, FileNotFoundError, IsADirectoryError])
def test_unavailable_log_returns_no_summary(tmp_path, monkeypatch, error):
    from app.services.storage import log_file_for_stage, summarize_stage_log

    monkeypatch.setenv("APP_DATA_DIR", str(tmp_path / "data"))
    log_file_for_stage("one", "asr").write_text("previous")

    def fail_open(*args, **kwargs):
        raise error("synthetic unavailable log")

    monkeypatch.setattr(Path, "open", fail_open)
    assert summarize_stage_log("one", "asr") is None


@pytest.mark.parametrize("configured", [False, True])
@pytest.mark.parametrize("missing", [False, True])
def test_actual_api_reads_do_not_mkdir_and_keep_readiness_redaction_and_reports(
    tmp_path, monkeypatch, configured, missing, read_bytes,
):
    from app import paths
    from app.db import reset_db_runtime, session_scope
    from app.main import app
    from app.models import Artifact, PipelineRun, Task, TaskStage, utc_now
    from app.services.storage import ensure_task_dirs

    data_dir = tmp_path / "data"
    monkeypatch.setenv("APP_DATA_DIR", str(data_dir))
    monkeypatch.setenv("APP_DATABASE_URL", f"sqlite:///{tmp_path / 'db.sqlite'}")
    reset_db_runtime()
    with TestClient(app) as client:
        report = data_dir / "tasks" / "one" / "reports" / "task-report.md"
        if not missing:
            dirs = ensure_task_dirs("one")
            (dirs["logs"] / "asr.log").write_bytes(
                b"old line\n" * 1_200_000 + b"token=synthetic-secret /tmp/private\n\n"
            )
            report.write_text("terminal report")
        with session_scope() as session:
            session.add(Task(id="one", source_url="fixture", normalized_source_url="fixture", status="success"))
            session.add(PipelineRun(id="run-one", task_id="one", status="success", started_at=utc_now()))
            session.add(TaskStage(task_id="one", name="asr", status="success", summary="DB fallback"))
            session.add(TaskStage(task_id="one", name="report", status="success"))
            artifact = Artifact(task_id="one", stage_name="report", kind="task_report_markdown", path=str(report))
            session.add(artifact)
            session.flush()
            artifact_id = artifact.id
        if not configured:
            monkeypatch.delenv("APP_DATA_DIR")
            monkeypatch.setattr(paths, "_default_data_dir", data_dir, raising=False)
            monkeypatch.setattr(paths, "Path", lambda value: data_dir if value == "/data" else Path(value))
        before = sorted(str(p.relative_to(data_dir)) for p in data_dir.rglob("*"))
        data_dir.chmod(0o555)
        try:
            with monkeypatch.context() as guarded:
                guarded.setattr(Path, "mkdir", _deny_mkdir)
                for url in ("/api/tasks/one", "/api/tasks/one/logs", "/api/v2/tasks/one", "/api/tasks/one/artifacts"):
                    read_bytes.clear()
                    response = client.get(url)
                    assert response.status_code == 200
                    assert sum(read_bytes) <= 64 * 1024
                    body = response.json()
                    if url.endswith("/logs"):
                        safe_summary = body[0]["safe_summary"]
                        assert safe_summary == ("DB fallback" if missing else "token [redacted] [path]")
                        assert body[0]["summary"] == ("DB fallback" if missing else "token=synthetic-secret /tmp/private")
                    if url == "/api/v2/tasks/one":
                        assert body["safe_logs"][0]["summary"] == ("DB fallback" if missing else "token [redacted] [path]")
                        report_readiness = next(item for item in body["artifact_readiness"] if item["stage_name"] == "report")
                        assert report_readiness["status"] == ("missing" if missing else "ready")
                    print({"url": url, "missing": missing, "configured": configured, "status": response.status_code, "read_bytes": sum(read_bytes)})
                download = client.get(f"/api/tasks/one/artifacts/{artifact_id}/content/task-report.md")
                assert download.status_code == (404 if missing else 200)
                if not missing:
                    assert download.text == "terminal report"
                assert client.get("/api/tasks/absent").status_code == 404
                assert client.get("/api/v2/tasks/absent").status_code == 404
                assert client.get("/api/health").status_code == 200
            after = sorted(str(p.relative_to(data_dir)) for p in data_dir.rglob("*"))
            assert before == after
            assert (data_dir / "tasks" / "one").exists() is not missing
            print({"tree_before": before, "tree_after": after, "mkdir_calls": 0})
        finally:
            data_dir.chmod(0o755)
    reset_db_runtime()


@pytest.mark.parametrize("writer", ["dirs", "engine", "migration", "startup"])
@pytest.mark.parametrize("explicit_db", [False, True])
def test_default_writer_initialization_retains_permission_fallback(tmp_path, monkeypatch, writer, explicit_db):
    from app import paths
    from app.db import get_database_url, get_engine, reset_db_runtime
    from app.db_migrations import upgrade_database
    from app.main import app
    from app.services.storage import ensure_task_dirs, get_tasks_root

    container = tmp_path / "denied-data"
    fallback = tmp_path / "project" / "data"
    monkeypatch.delenv("APP_DATA_DIR", raising=False)
    monkeypatch.setattr(paths, "_default_data_dir", container, raising=False)
    monkeypatch.setattr(paths, "Path", lambda value: container if value == "/data" else Path(value))
    monkeypatch.setattr(paths, "__file__", str(tmp_path / "project" / "backend" / "app" / "paths.py"))
    if explicit_db:
        monkeypatch.setenv("APP_DATABASE_URL", f"sqlite:///{tmp_path / 'explicit.sqlite'}")
    else:
        monkeypatch.delenv("APP_DATABASE_URL", raising=False)
    mkdir = Path.mkdir

    def denied_container(path, *args, **kwargs):
        if path == container:
            raise PermissionError("synthetic default-path permission denied")
        return mkdir(path, *args, **kwargs)

    monkeypatch.setattr(Path, "mkdir", denied_container)
    reset_db_runtime()
    match writer:
        case "dirs":
            assert ensure_task_dirs("new")["logs"].is_dir()
        case "engine":
            with get_engine().connect() as connection:
                assert connection.exec_driver_sql("SELECT 1").scalar() == 1
        case "migration":
            upgrade_database()
        case "startup":
            with TestClient(app) as client:
                assert client.get("/api/health").status_code == 200
        case unexpected:
            pytest.fail(f"Unknown writer: {unexpected}")
    assert fallback.is_dir()
    with monkeypatch.context() as guarded:
        guarded.setattr(Path, "mkdir", _deny_mkdir)
        assert paths.get_data_dir() == fallback
        assert get_tasks_root() == fallback / "tasks"
        assert get_database_url() == f"sqlite:///{tmp_path / 'explicit.sqlite' if explicit_db else fallback / 'tasks.sqlite3'}"
    assert not container.exists()
    reset_db_runtime()


def test_database_url_empty_override_remains_explicit(monkeypatch):
    from app.db import get_database_url

    monkeypatch.setenv("APP_DATABASE_URL", "")
    monkeypatch.delenv("APP_DATA_DIR", raising=False)
    monkeypatch.setattr(Path, "mkdir", _deny_mkdir)
    assert get_database_url() == ""
