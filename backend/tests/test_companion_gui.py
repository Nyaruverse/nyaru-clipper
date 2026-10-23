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


@pytest.mark.parametrize("selection,mode", [
    ({"ranges": json.dumps([["1", "4"]])}, "ranges"),
    ({"highlights": 2}, "highlights"),
])
def test_local_video_supports_slicing_without_ai(client, tmp_path, selection, mode):
    response = client.post("/companion-api/jobs/upload", params={"saozi": "false", **selection}, content=b"local-video")
    assert response.status_code == 202
    job = completed(client, response.json()["id"])
    assert job["state"] == "completed" and job["mode"] == mode
    assert len(job["clips"]) == 1
    assert client.get(f"/companion-api/jobs/{job['id']}/files/source.mp4").content == b"local-video"
    assert not list(tmp_path.glob(".saozi-upload-*"))


@pytest.mark.parametrize("selection", [
    {"ranges": "bad-json"}, {"ranges": "null"}, {"ranges": "[]"},
    {"ranges": json.dumps([["4", "1"]])},
    {"ranges": json.dumps([["1", "4"]]), "highlights": 2},
    {"highlights": 0}, {"highlights": 2, "language": "--bad"},
])
def test_invalid_local_selection_does_not_reserve_job(client, selection):
    response = client.post("/companion-api/jobs/upload", params={"saozi": "false", **selection}, content=b"video")
    assert response.status_code == 422
    assert client.get("/companion-api/jobs").json() == []


def test_empty_local_upload_can_be_retried_without_ai(client):
    params = {"saozi": "false", "ranges": json.dumps([["1", "4"]])}
    assert client.post("/companion-api/jobs/upload", params=params, content=b"").status_code == 422
    retry = client.post("/companion-api/jobs/upload", params=params, content=b"video")
    assert retry.status_code == 202
    assert completed(client, retry.json()["id"])["state"] == "completed"


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


@pytest.mark.parametrize('state', ['completed', 'failed'])
def test_room_end_is_visible_without_overriding_processing_state(client, tmp_path, state):
    job_id = 'aabbccddeeff'
    directory = tmp_path / job_id
    directory.mkdir()
    (directory / 'job.json').write_text(json.dumps({
        'state': 'completed' if state == 'completed' else 'live_failed',
        'live': True, 'capture_end_reason': 'live_ended'}))
    error = 'Local ASR timestamps exceed chunk duration' if state == 'failed' else None
    (directory / 'gui.json').write_text(json.dumps({'id': job_id, 'state': state,
        'message': '处理失败' if error else '处理完成', 'error': error}))
    for response in (client.get(f'/companion-api/jobs/{job_id}'), client.get('/companion-api/jobs')):
        job = response.json()
        if isinstance(job, list):
            job = next(row for row in job if row['id'] == job_id)
        assert job['capture_end_reason'] == 'live_ended'
        assert '直播已结束' in job['message']
        assert job['state'] == state and job['error'] == error


def translation_finished(client, job_id):
    for _ in range(200):
        result = client.get(f"/companion-api/jobs/{job_id}").json()
        if result.get("translation", {}).get("state") in {"completed", "failed"}:
            return result
        time.sleep(.01)
    pytest.fail("translation did not finish")


def test_bilingual_endpoint_reuses_only_subtitles_and_never_persists_key_in_tasks(client, tmp_path, monkeypatch):
    from app.arctime import gui, translation
    job_id = start(client).json()["id"]
    assert completed(client, job_id)["state"] == "completed"
    directory = tmp_path / job_id
    original = {p.name: workflow.fingerprint(p) for p in directory.iterdir()}
    def forbidden(*args, **kwargs):
        pytest.fail("translation must not download, recognize or encode video")
    for name in ("download_video", "export_clip"):
        monkeypatch.setattr(workflow.media, name, forbidden)
    monkeypatch.setattr(gui.LocalASR, "transcribe", forbidden)
    monkeypatch.setattr(translation, "_request", lambda client, key, cues, start, model: [{"id": start + i + 1, "zh": "中文译文"} for i, cue in enumerate(cues)])
    assert client.post(f"/companion-api/jobs/{job_id}/translate").status_code == 409
    assert client.post("/companion-api/translation-config", json={"api_key": "private-key"}).status_code == 200
    assert client.get("/companion-api/config").json()["translation_configured"] is True
    assert client.post(f"/companion-api/jobs/{job_id}/translate").status_code == 202
    result = translation_finished(client, job_id)
    assert result["state"] == "completed"
    assert result["translation"]["state"] == "completed"
    assert "中文译文" in result["bilingual_segments"][0]["text"]
    base = f"/companion-api/jobs/{job_id}/files/"
    assert "中文译文" in client.get(base + "subtitles.ja-zh.vtt").text
    assert client.get(base + "clip-001.ja-zh.srt?download=true").status_code == 200
    assert client.get(base + "translation.json").status_code == 404
    for name, digest in original.items():
        assert workflow.fingerprint(directory / name) == digest
    assert "private-key" not in json.dumps(result)
    assert all("private-key" not in p.read_text() for p in directory.glob("*.json"))
    restarted = TestClient(create_app(tmp_path))
    assert restarted.get("/companion-api/config").json()["translation_configured"] is True
    restarted.close()


def test_translation_config_persists_updates_privately_and_loads_after_restart(tmp_path):
    path = tmp_path / "config.json"
    with TestClient(create_app(tmp_path)) as client:
        for key in ("test-first-key", "test-updated-key"):
            response = client.post("/companion-api/translation-config", json={"api_key": key})
            assert response.status_code == 200
            assert key not in response.text
            assert json.loads(path.read_text()) == {"deepseek_api_key": key, "deepseek_model": "deepseek-flash",
                                                    'llm_provider': 'deepseek', 'chatgpt_model': ''}
            assert path.stat().st_mode & 0o777 == 0o600
        assert client.get("/companion-api/jobs").json() == []
        assert client.get("/companion-api/jobs/aaaaaaaaaaaa/files/config.json").status_code == 404
    with TestClient(create_app(tmp_path)) as restarted:
        result = restarted.get("/companion-api/config")
        assert result.json()["translation_configured"] is True
        assert "test-updated-key" not in result.text


@pytest.mark.parametrize("content", ['{"deepseek_api_key": "bad key"}', '[]', '{broken'])
def test_invalid_translation_config_is_visible_and_can_be_repaired(tmp_path, content):
    path = tmp_path / "config.json"
    path.write_text(content)
    with TestClient(create_app(tmp_path)) as client:
        result = client.get("/companion-api/config").json()
        assert result["translation_configured"] is False
        assert result["translation_config_error"]
        assert "bad key" not in json.dumps(result)
        assert client.post("/companion-api/translation-config", json={"api_key": "test-fixed-key"}).status_code == 200
        assert client.get("/companion-api/config").json()["translation_config_error"] is None


def test_empty_translation_config_disables_key_on_restart(tmp_path):
    (tmp_path / "config.json").write_text('{"deepseek_api_key": ""}')
    with TestClient(create_app(tmp_path)) as client:
        result = client.get("/companion-api/config").json()
        assert result["translation_configured"] is False
        assert result["translation_config_error"] is None


def test_model_selection_persists_without_reentering_or_replacing_key(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        assert client.get("/companion-api/config").json()["translation_model"] == "deepseek-flash"
        assert client.post("/companion-api/translation-config", json={"model": "deepseek-v4-pro"}).status_code == 422
        assert client.get("/companion-api/config").json()["translation_configured"] is False
        assert client.post("/companion-api/translation-config", json={"api_key": "test-key"}).status_code == 200
        assert client.post("/companion-api/translation-config", json={"model": "deepseek-flash"}).status_code == 200
        assert client.post("/companion-api/translation-config", json={"model": "deepseek-v4-pro"}).status_code == 422
        before = (tmp_path / "config.json").read_bytes()
        assert client.post("/companion-api/translation-config", json={"model": "unknown"}).status_code == 422
        assert client.post("/companion-api/translation-config", json={}).status_code == 422
        assert (tmp_path / "config.json").read_bytes() == before
        assert json.loads(before) == {"deepseek_api_key": "test-key", "deepseek_model": "deepseek-flash",
                                      'llm_provider': 'deepseek', 'chatgpt_model': ''}
    with TestClient(create_app(tmp_path)) as restarted:
        config = restarted.get("/companion-api/config").json()
        assert config["translation_configured"] is True
        assert config["translation_model"] == "deepseek-flash"
        assert config["translation_models"] == ["deepseek-flash"]
        assert "test-key" not in json.dumps(config)


def test_repairing_invalid_model_preserves_saved_key(tmp_path):
    path = tmp_path / "config.json"
    path.write_text('{"deepseek_api_key": "test-preserved-key", "deepseek_model": "invalid"}')
    with TestClient(create_app(tmp_path)) as client:
        config = client.get("/companion-api/config").json()
        assert config["translation_config_error"]
        assert config["translation_configured"] is True
        assert client.post("/companion-api/translation-config", json={"model": "deepseek-flash"}).status_code == 200
        assert json.loads(path.read_text())["deepseek_api_key"] == "test-preserved-key"
        assert client.get("/companion-api/config").json()["translation_config_error"] is None


def test_started_translation_keeps_model_when_global_selection_changes(client, monkeypatch):
    from app.arctime import translation
    from app.arctime.chatgpt_auth import ChatGPTAuth
    monkeypatch.setattr(ChatGPTAuth, 'models', lambda self: [{'slug': 'subscription-model', 'display_name': 'Subscription'}])
    monkeypatch.setattr(ChatGPTAuth, 'status', lambda self: {'connected': True, 'sharing': True, 'account_label': 'Test',
                                                           'error': None, 'manage_url': 'https://chatgpt.com/settings/usage'})
    models = []
    def request(client, key, cues, start, model, **kwargs):
        if model.startswith('chatgpt:'):
            assert kwargs['request_json'] is not None
            assert key.get_secret_value() == ''
        models.append(model)
        if len(models) == 1:
            raise ValueError("temporary failure")
        return [{"id": start + i + 1, "zh": "你好"} for i, cue in enumerate(cues)]
    monkeypatch.setattr(translation, "_request", request)
    job_id = start(client).json()["id"]
    assert completed(client, job_id)["state"] == "completed"
    client.post("/companion-api/translation-config", json={"api_key": "test-key", "model": "deepseek-flash"})
    assert client.post(f"/companion-api/jobs/{job_id}/translate").status_code == 202
    assert translation_finished(client, job_id)["translation"]["state"] == "failed"
    assert client.post('/companion-api/llm-config', json={'provider': 'chatgpt', 'model': 'subscription-model'}).status_code == 200
    assert client.get(f"/companion-api/jobs/{job_id}").json()["translation"]["model"] == "deepseek-flash"
    assert client.post(f"/companion-api/jobs/{job_id}/translate").status_code == 202
    assert translation_finished(client, job_id)["translation"]["state"] == "completed"
    other_id = start(client).json()["id"]
    assert completed(client, other_id)["state"] == "completed"
    assert client.post(f"/companion-api/jobs/{other_id}/translate").status_code == 202
    assert translation_finished(client, other_id)["translation"]["state"] == "completed"
    assert models == ["deepseek-flash", "deepseek-flash", "chatgpt:subscription-model"]


def test_translation_config_symlink_and_write_failure_do_not_activate_key(tmp_path, monkeypatch):
    target = tmp_path / "original.json"
    target.write_text('{"deepseek_api_key": "test-original-key"}')
    path = tmp_path / "config.json"
    path.symlink_to(target)
    with TestClient(create_app(tmp_path)) as client:
        assert client.get("/companion-api/config").json()["translation_configured"] is False
        assert client.post("/companion-api/translation-config", json={"api_key": "test-new-key"}).status_code == 409
        assert "test-original-key" in target.read_text()
        path.unlink()
        def fail(*args):
            raise OSError("private-file-detail")
        monkeypatch.setattr(workflow.media, "write_json", fail)
        result = client.post("/companion-api/translation-config", json={"api_key": "test-new-key"})
        assert result.status_code == 500
        assert "private-file-detail" not in result.text
        assert client.get("/companion-api/config").json()["translation_configured"] is False


def test_translation_failure_keeps_completed_task_and_is_retryable(client, monkeypatch):
    from app.arctime import translation
    job_id = start(client).json()["id"]
    assert completed(client, job_id)["state"] == "completed"
    client.post("/companion-api/translation-config", json={"api_key": "private-key"})
    def fail(*args):
        raise ValueError("DeepSeek API Key 无效")
    monkeypatch.setattr(translation, "_request", fail)
    assert client.post(f"/companion-api/jobs/{job_id}/translate").status_code == 202
    result = translation_finished(client, job_id)
    assert result["state"] == "completed"
    assert "API Key" in result["translation"]["error"]
    assert result["clips"]
    assert client.post(f"/companion-api/jobs/{job_id}/translate").status_code == 202
