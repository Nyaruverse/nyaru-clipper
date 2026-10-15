import json
import time

import pytest
from fastapi.testclient import TestClient

from app.arctime import workflow
from app.arctime.gui import create_app
from test_companion_gui import completed


@pytest.fixture
def saozi_client(tmp_path, monkeypatch):
    from app.arctime import translation
    from test_arctime_workflow import FakeASR
    monkeypatch.setattr("app.arctime.companion_manager.LocalASR", lambda *args: FakeASR())
    monkeypatch.setattr(workflow.media, "probe_video", lambda path: 10.0)
    def export(source, target, start, end, cues):
        target.write_bytes(b"export")
        target.with_suffix(".srt").write_text(workflow.render_srt(workflow.media.clip_subtitles(cues, start, end)))
    monkeypatch.setattr(workflow.media, "export_clip", export)
    monkeypatch.setattr(translation, "_request", lambda client, key, cues, start, model, **kwargs:
                        [{"id": start + i + 1, "zh": "字幕译文"} for i, cue in enumerate(cues)])
    (tmp_path / "config.json").write_text(json.dumps({"deepseek_api_key": "test-key"}))
    with TestClient(create_app(tmp_path)) as client:
        yield client


def test_local_upload_creates_saozi_and_returns_preview(saozi_client):
    response = saozi_client.post("/companion-api/saozi/upload?language=zh", content=b"local-video")
    assert response.status_code == 202
    job = completed(saozi_client, response.json()["id"])
    assert job["state"] == "completed"
    assert job["mode"] == "saozi"
    assert len(job["clips"]) == 1
    assert saozi_client.get(f"/companion-api/jobs/{job['id']}/files/source.mp4").content == b"local-video"


def test_local_saozi_automatically_publishes_bilingual_srt(saozi_client):
    response = saozi_client.post("/companion-api/saozi/upload?language=ja", content=b"local-video")
    job_id = response.json()["id"]
    for _ in range(100):
        job = saozi_client.get(f"/companion-api/jobs/{job_id}").json()
        if job["translation"]["state"] in {"completed", "failed"}:
            break
        time.sleep(.01)
    assert job["translation"]["state"] == "completed"
    assert job["bilingual_segments"]
    result = saozi_client.get(f"/companion-api/jobs/{job_id}/files/clip-001.ja-zh.srt")
    assert result.status_code == 200 and "字幕译文" in result.text


def test_empty_upload_releases_single_job_reservation(saozi_client):
    response = saozi_client.post("/companion-api/saozi/upload", content=b"")
    assert response.status_code == 422
    assert saozi_client.post("/companion-api/saozi/upload", content=b"video").status_code == 202


def test_saozi_cannot_start_without_key(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        response = client.post("/companion-api/jobs", json={"url": "https://example.org/replay", "saozi": True})
        assert response.status_code == 409
        assert "DeepSeek" in response.json()["detail"]


def test_stop_rejects_ordinary_jobs(saozi_client):
    assert saozi_client.post("/companion-api/jobs/000000000000/stop").status_code == 409


def test_failed_auto_translation_preserves_video_and_manual_retry(saozi_client, monkeypatch):
    from app.arctime import translation
    def fail(*args, **kwargs):
        raise ValueError("DeepSeek 请求失败（HTTP 401）")
    monkeypatch.setattr(translation, "_request", fail)
    response = saozi_client.post("/companion-api/saozi/upload?language=ja", content=b"video")
    identity = response.json()["id"]
    for _ in range(100):
        job = saozi_client.get(f"/companion-api/jobs/{identity}").json()
        if job["translation"]["state"] == "failed" and "未完成" in job["message"]:
            break
        time.sleep(.01)
    assert job["state"] == "completed" and job["translation"]["state"] == "failed"
    assert saozi_client.get(f"/companion-api/jobs/{identity}/files/clip-001.mp4").status_code == 200
    monkeypatch.setattr(translation, "_request", lambda client, key, cues, start, model, **kwargs:
                        [{"id": start + i + 1, "zh": "恢复译文"} for i, cue in enumerate(cues)])
    assert saozi_client.post(f"/companion-api/jobs/{identity}/translate").status_code == 202
    for _ in range(100):
        job = saozi_client.get(f"/companion-api/jobs/{identity}").json()
        if job["translation"]["state"] == "completed":
            break
        time.sleep(.01)
    assert job["translation"]["state"] == "completed"


def test_partial_bilingual_outputs_are_readable_and_tamper_is_rejected(saozi_client, tmp_path):
    response = saozi_client.post("/companion-api/saozi/upload?language=ja", content=b"video")
    identity = response.json()["id"]
    directory = tmp_path / identity
    for _ in range(100):
        job = saozi_client.get(f"/companion-api/jobs/{identity}").json()
        if job["translation"]["state"] == "completed":
            break
        time.sleep(.01)
    checkpoint = directory / "translation.json"
    state = json.loads(checkpoint.read_text())
    state["state"] = "partial"
    checkpoint.write_text(json.dumps(state))
    job = saozi_client.get(f"/companion-api/jobs/{identity}").json()
    assert job["clips"][0]["bilingual_subtitles"] == "clip-001.ja-zh.srt"
    assert job["bilingual_segments"]
    url = f"/companion-api/jobs/{identity}/files/clip-001.ja-zh.srt"
    assert saozi_client.get(url).status_code == 200
    (directory / "clip-001.ja-zh.srt").write_text("modified")
    assert saozi_client.get(url).status_code == 409
    assert saozi_client.get(f"/companion-api/jobs/{identity}").json()["translation"]["state"] == "failed"
