import json
import time
import zipfile
from io import BytesIO

import pytest
from fastapi.testclient import TestClient

from app.arctime import media
from app.arctime.gui import create_app
from app.services.subtitles import SubtitleSegment, render_srt


@pytest.fixture
def finished(tmp_path, monkeypatch):
    directory = tmp_path / "abcdef123456"
    directory.mkdir()
    cues = [SubtitleSegment("1", 1, 3, "こんにちは"), SubtitleSegment("2", 4, 5, "次の字幕")]
    (directory / "source.mp4").write_bytes(b"original-video")
    (directory / "subtitles.srt").write_text(render_srt(cues))
    (directory / "clip-001.mp4").write_bytes(b"original-clip")
    (directory / "clip-001.srt").write_text(render_srt(media.clip_subtitles(cues, 1, 5)))
    digest = lambda name: media.fingerprint(directory / name)
    media.write_json(directory / "job.json", {"version": 2, "state": "completed", "duration": 6,
        "video": "source.mp4", "video_sha256": digest("source.mp4"), "ranges": [[1, 5]], "highlight_count": None,
        "asr": {"language": "ja"}, "subtitles": "subtitles.srt", "artifacts": {"subtitles.srt": digest("subtitles.srt")},
        "selection": [{"start": 1, "end": 5, "score": None, "reasons": ["manual"]}],
        "completed_clips": [{"video": "clip-001.mp4", "subtitles": "clip-001.srt", "video_sha256": digest("clip-001.mp4"), "subtitles_sha256": digest("clip-001.srt")}]})
    monkeypatch.setattr(media, "probe_video", lambda path: 6.0)
    with TestClient(create_app(tmp_path)) as client:
        yield client, directory


def payload(client, **changes):
    return {"kind": "ass", "video": "clip-001.mp4", "bilingual": False,
        "style": client.get("/companion-api/subtitle-settings").json()["style"], **changes}


def wait_export(client):
    for _ in range(300):
        result = client.get("/companion-api/jobs/abcdef123456/subtitle-exports").json()
        if result.get("active") is None or result["active"]["state"] in {"completed", "failed"}:
            return result
        time.sleep(.01)
    pytest.fail("export did not finish")


def test_style_template_routes_and_restart_keep_key_separate(finished):
    client, directory = finished
    settings = client.get("/companion-api/subtitle-settings")
    assert settings.status_code == 200
    style = settings.json()["style"]
    style["original"]["color"] = "#00FF00"
    assert client.post("/companion-api/subtitle-settings", json={"style": style}).status_code == 200
    created = client.post("/companion-api/style-templates", json={"name": "我的模板", "style": style})
    assert created.status_code == 200
    identity = created.json()["id"]
    download = client.get(f"/companion-api/style-templates/{identity}/download")
    assert download.status_code == 200
    assert download.json()["style"]["original"]["color"] == "#00FF00"
    assert client.post(f"/companion-api/style-templates/{identity}/delete").status_code == 200
    assert not (directory.parent / "config.json").exists()


def test_defaults_load_after_service_restart(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        style = client.get("/companion-api/subtitle-settings").json()["style"]
        style["translation"]["size"] = 64
        assert client.post("/companion-api/subtitle-settings", json={"style": style}).status_code == 200
    with TestClient(create_app(tmp_path)) as restarted:
        assert restarted.get("/companion-api/subtitle-settings").json()["style"] == style


def test_ass_export_is_clipped_immutable_and_hash_checked(finished, monkeypatch):
    from app.arctime import subtitle_exports
    client, directory = finished
    monkeypatch.setattr(subtitle_exports, "video_dimensions", lambda path: (640, 360))
    before = {p.name: media.fingerprint(p) for p in directory.iterdir() if p.is_file()}
    request = payload(client)
    response = client.post("/companion-api/jobs/abcdef123456/subtitle-export", json=request)
    assert response.status_code == 202
    result = wait_export(client)
    assert result["outputs"]
    assert result["outputs"][0]["style"] == request["style"]
    name = result["outputs"][0]["filename"]
    exported = client.get(f"/companion-api/jobs/abcdef123456/files/{name}")
    assert exported.status_code == 200
    assert "こんにちは" in exported.text and "0:00:00.00" in exported.text
    assert all(media.fingerprint(directory / name) == digest for name, digest in before.items())
    assert client.post("/companion-api/jobs/abcdef123456/subtitle-export", json=request).status_code == 202
    assert len(wait_export(client)["outputs"]) == 1
    (directory / name).write_text("manual change")
    assert client.get(f"/companion-api/jobs/abcdef123456/files/{name}").status_code == 409


def test_arctime_package_contains_only_portable_editable_assets(finished, monkeypatch):
    from app.arctime import subtitle_exports
    client, directory = finished
    monkeypatch.setattr(subtitle_exports, "video_dimensions", lambda path: (640, 360))
    template = client.post("/companion-api/arctime-templates?name=示例&filename=demo.atpj", content=b"opaque-project")
    assert template.status_code == 200
    request = payload(client, kind="arctime", arctime_template_id=template.json()["id"])
    assert client.post("/companion-api/jobs/abcdef123456/subtitle-export", json=request).status_code == 202
    output = wait_export(client)["outputs"][0]["filename"]
    archive = client.get(f"/companion-api/jobs/abcdef123456/files/{output}?download=true")
    with zipfile.ZipFile(BytesIO(archive.content)) as bundle:
        assert "clip.mp4" in bundle.namelist()
        assert bundle.read("clip.mp4") == b"original-clip"
        assert bundle.read("template.atpj") == b"opaque-project"
        assert "clip.ass" in bundle.namelist() and "clip.srt" in bundle.namelist()
        metadata = bundle.read("manifest.json").decode()
        assert str(directory) not in metadata and "deepseek_api_key" not in metadata
        assert json.loads(metadata)["time_origin_seconds"] == 0


def test_invalid_and_ineligible_exports_are_rejected(finished):
    client, directory = finished
    for changes in [{"video": "../config.json"}, {"kind": "burn", "video": "source.mp4"}, {"bilingual": True}]:
        assert client.post("/companion-api/jobs/abcdef123456/subtitle-export", json=payload(client, **changes)).status_code in {409, 422}
    (directory / "source.mp4").write_bytes(b"tampered")
    assert client.post("/companion-api/jobs/abcdef123456/subtitle-export", json=payload(client)).status_code == 409


def test_encoding_failure_keeps_original_task_and_can_retry(finished, monkeypatch):
    from app.arctime import subtitle_exports
    from app.arctime.subtitle_inputs import ExportError
    client, directory = finished
    monkeypatch.setattr(subtitle_exports, "video_dimensions", lambda path: (640, 360))
    monkeypatch.setattr(subtitle_exports, "burn_available", lambda: True)
    before = {p.name: media.fingerprint(p) for p in directory.iterdir() if p.is_file()}
    def fail(*args):
        raise ExportError("expected encoder failure")
    monkeypatch.setattr(subtitle_exports, "burn_clip", fail)
    request = payload(client, kind="burn")
    assert client.post("/companion-api/jobs/abcdef123456/subtitle-export", json=request).status_code == 202
    result = wait_export(client)
    assert result["active"]["state"] == "failed"
    assert result["active"]["error"] == "expected encoder failure"
    assert client.get("/companion-api/jobs/abcdef123456").json()["state"] == "completed"
    assert all(media.fingerprint(directory / name) == digest for name, digest in before.items())
    def success(source, working, duration, notify):
        path = working / "burn.mp4"
        path.write_bytes(b"burned-video")
        return path
    monkeypatch.setattr(subtitle_exports, "burn_clip", success)
    assert client.post("/companion-api/jobs/abcdef123456/subtitle-export", json=request).status_code == 202
    assert wait_export(client)["active"]["state"] == "completed"


def test_export_uses_shared_busy_gate_and_visible_history(finished, monkeypatch):
    import threading
    from app.arctime import subtitle_exports
    client, directory = finished
    entered, release = threading.Event(), threading.Event()
    monkeypatch.setattr(subtitle_exports, "video_dimensions", lambda path: (640, 360))
    monkeypatch.setattr(subtitle_exports, "burn_available", lambda: True)
    def blocked(source, working, duration, notify):
        entered.set()
        assert release.wait(5)
        path = working / "burn.mp4"
        path.write_bytes(b"burned-video")
        return path
    monkeypatch.setattr(subtitle_exports, "burn_clip", blocked)
    try:
        assert client.post("/companion-api/jobs/abcdef123456/subtitle-export", json=payload(client, kind="burn")).status_code == 202
        assert entered.wait(2)
        assert client.get("/companion-api/jobs").json()[0]["subtitle_export_busy"] is True
        assert client.post("/companion-api/jobs/abcdef123456/subtitle-export", json=payload(client)).status_code == 409
        assert client.post("/companion-api/jobs", json={"url": "https://example.org/test", "ranges": [["0", "1"]]}).status_code == 409
    finally:
        release.set()
    assert wait_export(client)["active"]["state"] == "completed"


def test_completion_during_preflight_keeps_previous_outputs(finished, monkeypatch):
    from app.arctime import subtitle_exports
    client, directory = finished
    monkeypatch.setattr(subtitle_exports, "video_dimensions", lambda path: (640, 360))
    old_name = "styled-" + "1" * 20 + ".ass"
    (directory / old_name).write_text("previous complete export")
    old = {"id": "1" * 20, "filename": old_name, "kind": "ass", "video": "source.mp4", "bilingual": False,
        "sha256": media.fingerprint(directory / old_name)}
    load = subtitle_exports.load_inputs
    calls = 0
    def completes_during_preflight(*args):
        nonlocal calls
        calls += 1
        if calls == 1:
            media.write_json(directory / "subtitle-exports.json", {"outputs": [old]})
        return load(*args)
    monkeypatch.setattr(subtitle_exports, "load_inputs", completes_during_preflight)
    assert client.post("/companion-api/jobs/abcdef123456/subtitle-export", json=payload(client)).status_code == 202
    assert len(wait_export(client)["outputs"]) == 2


def test_busy_run_lock_keeps_completed_export_history(finished, monkeypatch):
    from app.arctime import subtitle_exports, workflow
    client, directory = finished
    monkeypatch.setattr(subtitle_exports, "video_dimensions", lambda path: (640, 360))
    request = payload(client)
    assert client.post("/companion-api/jobs/abcdef123456/subtitle-export", json=request).status_code == 202
    assert len(wait_export(client)["outputs"]) == 1
    request["style"]["original"]["size"] = 64
    with workflow.exclusive_lock(directory / ".lock"):
        registry_before = (directory / "subtitle-exports.json").read_bytes()
        assert client.post("/companion-api/jobs/abcdef123456/subtitle-export", json=request).status_code == 202
        result = wait_export(client)
        assert result["active"]["state"] == "failed"
        assert len(result["outputs"]) == 1
        assert (directory / "subtitle-exports.json").read_bytes() == registry_before


def test_queued_export_overlays_prior_completed_activity_without_writing(finished, monkeypatch):
    import threading
    from app.arctime import subtitle_exports
    client, directory = finished
    monkeypatch.setattr(subtitle_exports, "video_dimensions", lambda path: (640, 360))
    request = payload(client)
    assert client.post("/companion-api/jobs/abcdef123456/subtitle-export", json=request).status_code == 202
    assert wait_export(client)["active"]["state"] == "completed"
    registry_before = (directory / "subtitle-exports.json").read_bytes()
    entered, release = threading.Event(), threading.Event()
    run = subtitle_exports.SubtitleExports.run
    def delayed(self, *args):
        entered.set()
        assert release.wait(5)
        return run(self, *args)
    monkeypatch.setattr(subtitle_exports.SubtitleExports, "run", delayed)
    try:
        assert client.post("/companion-api/jobs/abcdef123456/subtitle-export", json=request).status_code == 202
        assert entered.wait(2)
        result = client.get("/companion-api/jobs/abcdef123456/subtitle-exports").json()
        assert result["active"]["state"] == "exporting"
        assert len(result["outputs"]) == 1
        assert (directory / "subtitle-exports.json").read_bytes() == registry_before
    finally:
        release.set()
    assert wait_export(client)["active"]["state"] == "completed"


def test_publication_gap_recovers_verified_file_without_encoding_again(finished, monkeypatch):
    from app.arctime import subtitle_exports
    client, directory = finished
    monkeypatch.setattr(subtitle_exports, "video_dimensions", lambda path: (640, 360))
    link = subtitle_exports.os.link
    calls = 0
    def checkpoint_gap(source, target):
        nonlocal calls
        calls += 1
        link(source, target)
        raise RuntimeError("simulated interruption after publication")
    monkeypatch.setattr(subtitle_exports.os, "link", checkpoint_gap)
    request = payload(client)
    assert client.post("/companion-api/jobs/abcdef123456/subtitle-export", json=request).status_code == 202
    assert wait_export(client)["active"]["state"] == "failed"
    assert calls == 1
    assert client.post("/companion-api/jobs/abcdef123456/subtitle-export", json=request).status_code == 202
    result = wait_export(client)
    assert result["active"]["state"] == "completed"
    assert len(result["outputs"]) == 1 and calls == 1


@pytest.mark.parametrize("damage", ["missing_receipt", "changed_file", "changed_identity"])
def test_recovery_refuses_unverified_existing_file(finished, monkeypatch, damage):
    from app.arctime import subtitle_exports
    client, directory = finished
    monkeypatch.setattr(subtitle_exports, "video_dimensions", lambda path: (640, 360))
    link = subtitle_exports.os.link
    def gap(source, target):
        link(source, target)
        raise RuntimeError("publication gap")
    monkeypatch.setattr(subtitle_exports.os, "link", gap)
    request = payload(client)
    assert client.post("/companion-api/jobs/abcdef123456/subtitle-export", json=request).status_code == 202
    assert wait_export(client)["active"]["state"] == "failed"
    receipt = next(directory.glob("styled-*.receipt.json"))
    product = next(directory.glob("styled-*.ass"))
    if damage == "missing_receipt":
        receipt.unlink()
    elif damage == "changed_file":
        product.write_bytes(b"user edited file")
    else:
        record = json.loads(receipt.read_bytes())
        record["video"] = "source.mp4"
        receipt.write_text(json.dumps(record))
    before = product.read_bytes()
    def no_encoding(*args):
        pytest.fail("unverified existing output must not be re-encoded")
    monkeypatch.setattr(subtitle_exports, "video_dimensions", no_encoding)
    assert client.post("/companion-api/jobs/abcdef123456/subtitle-export", json=request).status_code == 202
    result = wait_export(client)
    assert result["active"]["state"] == "failed" and result["active"]["error"]
    assert result["outputs"] == [] and product.read_bytes() == before


def test_encoder_log_copy_failure_keeps_published_output_reusable(finished, monkeypatch):
    from app.arctime import subtitle_exports
    client, directory = finished
    monkeypatch.setattr(subtitle_exports, "video_dimensions", lambda path: (640, 360))
    monkeypatch.setattr(subtitle_exports, "burn_available", lambda: True)
    calls = 0
    def encode(source, working, duration, notify):
        nonlocal calls
        calls += 1
        (working / "encoder.log").write_text("encoded")
        product = working / "burn.mp4"
        product.write_bytes(b"encoded output")
        return product
    def fail_copy(*args):
        raise OSError("log destination unavailable")
    monkeypatch.setattr(subtitle_exports, "burn_clip", encode)
    monkeypatch.setattr(subtitle_exports.shutil, "copyfile", fail_copy)
    request = payload(client, kind="burn")
    assert client.post("/companion-api/jobs/abcdef123456/subtitle-export", json=request).status_code == 202
    result = wait_export(client)
    assert result["active"]["state"] == "failed" and len(result["outputs"]) == 1
    assert client.post("/companion-api/jobs/abcdef123456/subtitle-export", json=request).status_code == 202
    assert wait_export(client)["active"]["state"] == "completed" and calls == 1


def test_corrupt_registry_during_worker_read_clears_busy_without_overwriting(finished):
    from app.arctime.subtitle_exports import SubtitleExports
    from app.arctime.subtitle_inputs import ExportRequest
    from app.arctime.companion_manager import JobManager
    client, directory = finished
    manager = JobManager(directory.parent, directory / "unused-model", 1)
    exports = SubtitleExports(manager)
    registry = directory / "subtitle-exports.json"
    registry.write_bytes(b"corrupt registry preserved")
    manager.active = {"id": "abcdef123456", "state": "subtitle_export"}
    try:
        exports.run("abcdef123456", ExportRequest.model_validate(payload(client)), None)
        assert manager.active is None
        assert exports.failures["abcdef123456"].state == "failed"
        assert registry.read_bytes() == b"corrupt registry preserved"
    finally:
        manager.executor.shutdown(wait=True)
