from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.db import get_engine, reset_db_runtime
from app.services.task_operations import bind_task


def test_operation_http_queue_is_paused_revisioned_and_never_exposes_snapshots(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("APP_DATA_DIR", str(tmp_path / "runtime"))
    monkeypatch.setenv("APP_DATABASE_URL", f"sqlite:///{tmp_path / 'state.sqlite3'}")
    reset_db_runtime()
    from app.main import app
    try:
        with TestClient(app) as client:
            with Session(get_engine()) as session:
                binding = bind_task(session, uuid4(), "new", "g", origin="native")
                task_id = binding.task_id
                session.commit()
            request = {"task_id": task_id, "kind": "process_recording", "engine": "whisper.cpp",
                "request": {"url": "https://example.invalid/video", "ranges": [["0", "1"]]}}
            first = client.post("/api/v2/operations", json=request)
            assert first.status_code == 202, first.text
            second = client.post("/api/v2/operations", json=request)
            assert second.status_code == 202
            snapshot = client.get("/api/v2/operations").json()
            assert snapshot["paused"] is True
            assert len(snapshot["operations"]) == 2
            assert "execution_token" not in str(snapshot) and "example.invalid" not in str(snapshot)
            ids = [second.json()["id"], first.json()["id"]]
            reordered = client.post("/api/v2/operations/reorder", json={"ordered_ids": ids, "expected_revision": snapshot["revision"]})
            assert reordered.status_code == 200
            assert [item["id"] for item in reordered.json()["operations"]] == ids
            stale = client.post("/api/v2/operations/reorder", json={"ordered_ids": ids, "expected_revision": snapshot["revision"]})
            assert stale.status_code == 409
            resumed = client.post("/api/v2/operations/queue", json={"paused": False, "expected_revision": reordered.json()["revision"]})
            assert resumed.status_code == 200 and resumed.json()["paused"] is False
            cancelled = client.post(f"/api/v2/operations/{ids[0]}/cancel")
            assert cancelled.status_code == 200
            assert next(row for row in cancelled.json()["operations"] if row["id"] == ids[0])["state"] == "cancelled"
            assert client.post('/api/v2/operations', content=b'x' * (20 * 1024 * 1024 + 1)).status_code == 413
    finally:
        reset_db_runtime()
