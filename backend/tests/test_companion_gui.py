import json
import subprocess
import threading
import time

import pytest
from fastapi.testclient import TestClient

from app.arctime import workflow
from app.arctime.gui import create_app
from app.services.subtitles import SubtitleSegment, render_srt


@pytest.fixture
def client(tmp_path, monkeypatch):
    from app.arctime import gui

    monkeypatch.setattr(gui.LocalASR, "identity", lambda self: {"engine": "local-test", "model": str(self.model), "language": self.language, "threads": self.threads})
    monkeypatch.setattr(gui.LocalASR, "transcribe", lambda *args: [SubtitleSegment("1", 1, 3, "哈哈！太强了！哈哈！")])

    def download(url, directory):
        path = directory / "source.mp4"
        path.write_bytes(b"source-video")
        return path

    def export(source, target, start, end, cues):
        target.write_bytes(b"clip-video")
        target.with_suffix(".srt").write_text(render_srt(workflow.media.clip_subtitles(cues, start, end)))

    monkeypatch.setattr(workflow.media, "download_video", download)
    monkeypatch.setattr(workflow.media, "probe_video", lambda path: 10.0)
    monkeypatch.setattr(workflow.media, "export_clip", export)
    with TestClient(create_app(tmp_path)) as value:
        yield value


def start(client, **kwargs):
    return client.post("/companion-api/jobs", json={"url": "https://example.org/video.mp4", "ranges": [["1", "4"]], **kwargs})


def completed(client, job_id):
    for _ in range(200):
        job = client.get(f"/companion-api/jobs/{job_id}").json()
        if job["state"] in {"completed", "failed"}:
            return job
        time.sleep(.01)
    pytest.fail("background job did not finish")


def test_ranges_progress_preview_download_and_history(client, tmp_path):
    response = start(client, ranges=[["00:01", "00:04"], ["5", "8"]])
    assert response.status_code == 202
    job_id = response.json()["id"]
    job = completed(client, job_id)
    assert job["state"] == "completed"
    assert len(job["clips"]) == 2
    assert job["segments"][0]["text"] == "哈哈！太强了！哈哈！"
    assert job["clips"][0]["start"] == 1
    assert client.get("/companion-api/jobs").json()[0]["id"] == job_id
    base = f"/companion-api/jobs/{job_id}/files/"
    assert client.get(base + "clip-001.mp4", headers={"Range": "bytes=0-3"}).status_code == 206
    download = client.get(base + "clip-001.srt?download=true")
    assert "attachment" in download.headers["content-disposition"]
    assert "00:00:00,000" in download.text
    assert "WEBVTT" in client.get(base + "clip-001.vtt").text
    assert "example.org" not in (tmp_path / job_id / "job.json").read_text()
    assert "example.org" not in (tmp_path / job_id / "gui.json").read_text()


def test_highlights_are_selected_from_local_transcript(client):
    response = start(client, ranges=[], highlights=2)
    job = completed(client, response.json()["id"])
    assert job["state"] == "completed"
    assert len(job["clips"]) == 1
    assert job["clips"][0]["score"] >= .55


@pytest.mark.parametrize("payload", [
    {"url": "file:///etc/passwd"},
    {"url": "https://user:password@example.org/v.mp4"},
    {"ranges": [["4", "1"]]},
    {"ranges": []},
    {"highlights": 2},
    {"ranges": [], "highlights": 0},
    {"ranges": [["NaN", "4"]]},
    {"language": "--bad"},
])
def test_invalid_input_is_rejected_before_download(client, payload):
    assert start(client, **payload).status_code == 422


def test_single_active_job_and_real_stage(client, monkeypatch):
    entered, release = threading.Event(), threading.Event()
    original = workflow.media.download_video

    def blocked(url, directory):
        entered.set()
        assert release.wait(5)
        return original(url, directory)

    monkeypatch.setattr(workflow.media, "download_video", blocked)
    first = start(client)
    try:
        assert entered.wait(2)
        job_id = first.json()["id"]
        assert client.get(f"/companion-api/jobs/{job_id}").json()["state"] == "downloading"
        assert start(client).status_code == 409
    finally:
        release.set()
    assert completed(client, job_id)["state"] == "completed"


def test_failure_is_visible_and_can_resume(client, monkeypatch):
    from app.arctime import gui

    original = gui.LocalASR.transcribe
    monkeypatch.setattr(gui.LocalASR, "transcribe", lambda *args: (_ for _ in ()).throw(RuntimeError("识别失败")))
    job_id = start(client).json()["id"]
    failed = completed(client, job_id)
    assert failed["error"] == "识别失败"
    assert failed["can_resume"] is True
    monkeypatch.setattr(gui.LocalASR, "transcribe", original)
    assert client.post(f"/companion-api/jobs/{job_id}/resume").status_code == 202
    assert completed(client, job_id)["state"] == "completed"


def test_only_managed_files_are_served(client, tmp_path):
    job_id = start(client).json()["id"]
    assert completed(client, job_id)["state"] == "completed"
    directory = tmp_path / job_id
    (directory / "secret.txt").write_text("private")
    base = f"/companion-api/jobs/{job_id}/files/"
    for name in ["secret.txt", "job.json", "gui.json", "clip-001.log"]:
        assert client.get(base + name).status_code == 404
    (directory / "clip-001.mp4").unlink()
    (directory / "clip-001.mp4").symlink_to(directory / "secret.txt")
    assert client.get(base + "clip-001.mp4").status_code == 404
    assert client.get("/companion-api/jobs/unknown").status_code == 404


def test_restart_marks_unfinished_job_interrupted_and_keeps_results(client, tmp_path):
    job_id = start(client).json()["id"]
    assert completed(client, job_id)["state"] == "completed"
    path = tmp_path / job_id / "job.json"
    job = json.loads(path.read_text())
    job["state"] = "exporting"
    workflow.media.write_json(path, job)
    (tmp_path / job_id / "gui.json").unlink()
    restarted = TestClient(create_app(tmp_path))
    snapshot = restarted.get(f"/companion-api/jobs/{job_id}").json()
    restarted.close()
    assert snapshot["state"] == "interrupted"
    assert snapshot["can_resume"] is True
    assert len(snapshot["clips"]) == 1


def test_foreign_websites_cannot_start_local_jobs(client):
    assert client.post("/companion-api/jobs", headers={"Origin": "https://evil.example"}, json={"url": "https://example.org/v", "ranges": [["1", "4"]]}).status_code == 403
    assert client.get("/companion-api/jobs", headers={"Host": "evil.example"}).status_code == 400


def test_broken_or_empty_directory_does_not_break_job_history(client, tmp_path):
    (tmp_path / "abcdef123456").mkdir()
    broken = tmp_path / "abcdef123457"
    broken.mkdir()
    (broken / "job.json").write_text("invalid-json")
    job_id = start(client).json()["id"]
    assert completed(client, job_id)["state"] == "completed"
    history = client.get("/companion-api/jobs")
    assert history.status_code == 200
    assert [job["id"] for job in history.json()] == [job_id]


def test_download_timeout_never_persists_source_url(client, tmp_path, monkeypatch):
    url = "https://example.org/v.mp4?secret=private-value"

    def timeout(url, directory):
        raise subprocess.TimeoutExpired(["yt-dlp", url], 7200)

    monkeypatch.setattr(workflow.media, "download_video", timeout)
    job_id = start(client, url=url).json()["id"]
    job = completed(client, job_id)
    assert job["state"] == "failed"
    assert "private-value" not in json.dumps(job)
    assert "private-value" not in (tmp_path / job_id / "gui.json").read_text()


def test_environment_failure_survives_new_job_and_restart(client, tmp_path, monkeypatch):
    from app.arctime import gui

    identity = gui.LocalASR.identity
    monkeypatch.setattr(gui.LocalASR, "identity", lambda self: (_ for _ in ()).throw(ValueError("invalid model")))
    failed_id = start(client).json()["id"]
    assert completed(client, failed_id)["state"] == "failed"
    monkeypatch.setattr(gui.LocalASR, "identity", identity)
    good_id = start(client).json()["id"]
    assert completed(client, good_id)["state"] == "completed"
    restarted = TestClient(create_app(tmp_path))
    failed = restarted.get(f"/companion-api/jobs/{failed_id}")
    assert failed.status_code == 200
    assert failed.json()["error"] == "invalid model"
    assert failed.json()["can_resume"] is False
    assert len(restarted.get("/companion-api/jobs").json()) == 2
    restarted.close()


def test_cli_recovery_overrides_stale_gui_failure(client, tmp_path, monkeypatch):
    from app.arctime import gui

    original = gui.LocalASR.transcribe
    monkeypatch.setattr(gui.LocalASR, "transcribe", lambda *args: (_ for _ in ()).throw(RuntimeError("old failure")))
    job_id = start(client).json()["id"]
    assert completed(client, job_id)["state"] == "failed"
    monkeypatch.setattr(gui.LocalASR, "transcribe", original)
    workflow.resume_run(tmp_path / job_id)
    snapshot = client.get(f"/companion-api/jobs/{job_id}").json()
    assert snapshot["state"] == "completed"
    assert snapshot["error"] is None
    assert "old failure" not in snapshot["message"]
