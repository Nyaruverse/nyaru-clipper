import errno
import hashlib
import json
import os
import threading
import time
from contextlib import contextmanager
from pathlib import Path

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
    from app.arctime.companion_manager import JobManager
    from app.arctime.local_asr import DEFAULT_MODEL
    manager = JobManager(tmp_path, DEFAULT_MODEL, 4)
    monkeypatch.setattr("app.arctime.gui.JobManager", lambda *args: manager)
    with TestClient(create_app(tmp_path)) as client:
        client.app.state.manager = manager
        yield client


def test_local_upload_creates_saozi_and_returns_preview(saozi_client):
    response = saozi_client.post("/companion-api/saozi/upload?language=zh", content=b"local-video")
    assert response.status_code == 202
    job = completed(saozi_client, response.json()["id"])
    assert job["state"] == "completed"
    assert job["mode"] == "saozi"
    assert len(job["clips"]) == 1
    assert saozi_client.get(f"/companion-api/jobs/{job['id']}/files/source.mp4").content == b"local-video"


@pytest.mark.parametrize("endpoint", ["saozi/upload", "jobs/upload"])
def test_owned_upload_transfers_inode_without_second_copy(saozi_client, tmp_path, monkeypatch, record_property, endpoint):
    from app.arctime import saozi_api
    mkstemp = saozi_api.tempfile.mkstemp
    uploads = []
    copies = []
    copyfile = workflow.shutil.copyfile

    def capture_upload(*args, **kwargs):
        descriptor, name = mkstemp(*args, **kwargs)
        if Path(name).name.startswith(".saozi-upload-"):
            uploads.append((Path(name), Path(name).stat().st_ino))
        return descriptor, name

    def capture_copy(source, target, *args, **kwargs):
        copies.append((str(source), str(target)))
        return copyfile(source, target, *args, **kwargs)

    monkeypatch.setattr(saozi_api.tempfile, "mkstemp", capture_upload)
    monkeypatch.setattr(workflow.shutil, "copyfile", capture_copy)
    payload = b"owned-video" * 4096
    response = saozi_client.post(f"/companion-api/{endpoint}?language=zh", content=payload)
    assert response.status_code == 202
    job = completed(saozi_client, response.json()["id"])
    assert job["state"] == "completed"
    source = tmp_path / job["id"] / "source.mp4"
    saved = json.loads((source.parent / "job.json").read_text())
    assert source.read_bytes() == payload
    assert copies == [], "owned upload attempted a second whole-file copy"
    assert source.stat().st_ino == uploads[0][1]
    assert not uploads[0][0].exists()
    assert saved["video_sha256"] == hashlib.sha256(payload).hexdigest()
    assert saved["duration"] == 10.0
    record_property("transfer", json.dumps({"source_sha256": saved["video_sha256"],
                                            "inode_retained": True, "upload_removed": True,
                                            "duration": saved["duration"]}))


def test_external_prefix_lookalike_is_copied_and_never_cleaned(saozi_client, tmp_path):
    from app.arctime.companion_models import JobInput
    manager = saozi_client.app.state.manager
    source = tmp_path / ".saozi-upload-user-owned"
    source.write_bytes(b"external-original")
    inode = source.stat().st_ino
    request = JobInput(url="https://local.invalid", saozi=False, ranges=[("0", "5")])
    job_id = manager.submit(request, deferred=True)
    manager.run(job_id, request, local_source=source)
    assert manager.last["state"] == "completed"
    assert source.read_bytes() == b"external-original"
    assert source.stat().st_ino == inode
    assert (tmp_path / job_id / "source.mp4").read_bytes() == source.read_bytes()
    assert (tmp_path / job_id / "source.mp4").stat().st_ino != inode


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


def test_upload_write_and_failure_record_enospc_release_reservation(saozi_client, tmp_path, monkeypatch, record_property, caplog):
    from app.arctime import saozi_api
    manager = saozi_client.app.state.manager
    primary = OSError(errno.ENOSPC, "upload write primary")
    fdopen = saozi_api.os.fdopen

    class FullDiskFile:
        def write(self, block):
            raise primary

    @contextmanager
    def full_disk_file(*args, **kwargs):
        with fdopen(*args, **kwargs):
            yield FullDiskFile()

    def full_disk_record(*args):
        raise OSError(errno.ENOSPC, "failure record secondary")

    with monkeypatch.context() as faults:
        faults.setattr(saozi_api.os, "fdopen", full_disk_file)
        faults.setattr(workflow.media, "write_json", full_disk_record)
        with pytest.raises(OSError) as raised:
            saozi_client.post("/companion-api/saozi/upload", content=b"video")
    assert manager.active is None
    assert raised.value is primary
    assert manager.last["state"] == "failed"
    failed_id = manager.last["id"]
    assert not (tmp_path / failed_id / "gui.json").exists()
    assert not list(tmp_path.glob(".saozi-upload-*"))
    assert "upload_failure_record_deferred" in caplog.text
    assert "failure record secondary" not in caplog.text
    record_property("after_failure", json.dumps({"active": manager.active, "last": manager.last,
                                                "primary_preserved": raised.value is primary}))
    retry = saozi_client.post("/companion-api/saozi/upload", content=b"retry-video")
    assert retry.status_code == 202
    record_property("retry_http_status", retry.status_code)
    assert completed(saozi_client, retry.json()["id"])["state"] == "completed"


def test_upload_unlink_failure_preserves_primary_and_releases_reservation(saozi_client, tmp_path, monkeypatch, record_property, caplog):
    manager = saozi_client.app.state.manager
    unlink = Path.unlink

    def deny_upload_unlink(path, *args, **kwargs):
        if path.name.startswith(".saozi-upload-"):
            raise PermissionError(errno.EACCES, "temporary unlink secondary")
        return unlink(path, *args, **kwargs)

    with monkeypatch.context() as faults:
        faults.setattr(Path, "unlink", deny_upload_unlink)
        response = saozi_client.post("/companion-api/saozi/upload", content=b"")
    assert response.status_code == 422
    assert response.json()["detail"] == "请选择非空录像文件"
    assert manager.active is None
    assert manager.last["state"] == "failed"
    record = json.loads((tmp_path / manager.last["id"] / "gui.json").read_text())
    assert record["state"] == "failed"
    assert len(list(tmp_path.glob(".saozi-upload-*"))) == 1
    assert "upload_cleanup_deferred" in caplog.text
    assert "temporary unlink secondary" not in caplog.text
    record_property("after_failure", json.dumps({"active": manager.active, "last": manager.last,
                                                "primary_http_status": response.status_code}))
    retry = saozi_client.post("/companion-api/saozi/upload", content=b"retry-video")
    assert retry.status_code == 202
    record_property("retry_http_status", retry.status_code)
    assert completed(saozi_client, retry.json()["id"])["state"] == "completed"


@pytest.mark.parametrize("record_fails", [False, True])
def test_worker_secondary_failures_release_reservation(saozi_client, tmp_path, monkeypatch, record_fails, record_property):
    manager = saozi_client.app.state.manager
    primary = RuntimeError("worker primary failure")
    unlink, write_json = Path.unlink, workflow.media.write_json
    futures = []
    submit = manager.executor.submit

    def capture_submit(*args, **kwargs):
        future = submit(*args, **kwargs)
        futures.append(future)
        return future

    def fail_create(*args, **kwargs):
        raise primary

    def deny_upload_unlink(path, *args, **kwargs):
        if path.name.startswith(".saozi-upload-"):
            raise PermissionError(errno.EACCES, "worker unlink secondary")
        return unlink(path, *args, **kwargs)

    def write_failure(path, value):
        if record_fails and path.name == "gui.json":
            raise OSError(errno.ENOSPC, "worker record secondary")
        return write_json(path, value)

    with monkeypatch.context() as faults:
        faults.setattr(manager.executor, "submit", capture_submit)
        faults.setattr(workflow, "create_run", fail_create)
        faults.setattr(workflow.media, "write_json", write_failure)
        faults.setattr(Path, "unlink", deny_upload_unlink)
        response = saozi_client.post("/companion-api/saozi/upload", content=b"video")
        assert response.status_code == 202
        failure = futures[0].exception(timeout=5)
    assert manager.active is None
    assert manager.last["id"] == response.json()["id"]
    assert manager.last["state"] == "failed"
    assert manager.last["error"] == "worker primary failure"
    if record_fails:
        assert failure is primary
    else:
        assert failure is None
        record = json.loads((tmp_path / manager.last["id"] / "gui.json").read_text())
        assert record["error"] == "worker primary failure"
    assert len(list(tmp_path.glob(".saozi-upload-*"))) == 1
    record_property("after_failure", json.dumps({"active": manager.active, "last": manager.last,
                                                "future_error": str(failure) if failure else None}))
    retry = saozi_client.post("/companion-api/saozi/upload", content=b"retry-video")
    assert retry.status_code == 202
    record_property("retry_http_status", retry.status_code)
    assert completed(saozi_client, retry.json()["id"])["state"] == "completed"


def test_successful_upload_handoff_keeps_reservation_until_worker_finishes(saozi_client, tmp_path, monkeypatch, record_property):
    manager = saozi_client.app.state.manager
    entered, release = threading.Event(), threading.Event()
    create_run = workflow.create_run
    futures = []
    submit = manager.executor.submit

    def capture_submit(*args, **kwargs):
        future = submit(*args, **kwargs)
        futures.append(future)
        return future

    def blocked_create(*args, **kwargs):
        entered.set()
        assert release.wait(5)
        return create_run(*args, **kwargs)

    monkeypatch.setattr(manager.executor, "submit", capture_submit)
    monkeypatch.setattr(workflow, "create_run", blocked_create)
    response = saozi_client.post("/companion-api/saozi/upload", content=b"video")
    try:
        assert response.status_code == 202
        assert entered.wait(2)
        assert manager.active["id"] == response.json()["id"]
        assert len(list(tmp_path.glob(".saozi-upload-*"))) == 1
        assert saozi_client.post("/companion-api/saozi/upload", content=b"other").status_code == 409
        record_property("during_handoff", json.dumps({"active": manager.active, "second_http_status": 409}))
    finally:
        release.set()
    futures[0].result(timeout=5)
    assert manager.active is None
    assert manager.last["state"] == "completed"
    assert not list(tmp_path.glob(".saozi-upload-*"))
    record_property("after_worker", json.dumps({"active": manager.active, "last": manager.last}))


@pytest.mark.parametrize("worker", [False, True])
def test_cleanup_does_not_release_replacement_reservation(saozi_client, monkeypatch, worker, record_property):
    manager = saozi_client.app.state.manager
    unlink = Path.unlink
    replacements, futures = [], []
    submit = manager.executor.submit
    rename = Path.rename

    def keep_upload_for_cleanup(path, target):
        if path.name.startswith(".saozi-upload-"):
            raise OSError(errno.ENOSPC, "transfer interrupted")
        return rename(path, target)

    def capture_submit(*args, **kwargs):
        future = submit(*args, **kwargs)
        futures.append(future)
        return future

    def replace_during_cleanup(path, *args, **kwargs):
        if path.name.startswith(".saozi-upload-"):
            with manager.lock:
                replacement = {**manager.active, "state": "preparing", "message": "replacement"}
                manager.active = replacement
                replacements.append(replacement)
            raise PermissionError(errno.EACCES, "cleanup secondary")
        return unlink(path, *args, **kwargs)

    with monkeypatch.context() as faults:
        if worker:
            faults.setattr(Path, "rename", keep_upload_for_cleanup)
        faults.setattr(Path, "unlink", replace_during_cleanup)
        faults.setattr(manager.executor, "submit", capture_submit)
        response = saozi_client.post("/companion-api/saozi/upload", content=b"video" if worker else b"")
        assert response.status_code == (202 if worker else 422)
        if worker:
            futures[0].result(timeout=5)
    assert manager.active is replacements[0]
    assert manager.active["state"] == "preparing"
    assert manager.last is None
    assert saozi_client.post("/companion-api/saozi/upload", content=b"other").status_code == 409
    record_property("after_cleanup", json.dumps({"active": manager.active, "last": manager.last,
                                                "replacement_preserved": manager.active is replacements[0]}))


@pytest.mark.parametrize("fault", ["exdev", "enospc", "move", "probe", "asr"])
def test_owned_upload_failure_preserves_state_and_releases_admission(saozi_client, tmp_path, monkeypatch, record_property, fault):
    from test_arctime_workflow import FakeASR
    manager = saozi_client.app.state.manager
    rename = Path.rename
    submit = manager.executor.submit
    futures = []

    def capture_submit(*args, **kwargs):
        future = submit(*args, **kwargs)
        futures.append(future)
        return future

    def fail_move(path, target):
        if path.name.startswith(".saozi-upload-"):
            raise OSError({"exdev": errno.EXDEV, "enospc": errno.ENOSPC, "move": errno.EACCES}[fault], "transfer fault")
        return rename(path, target)

    def fail_media(*args):
        raise ValueError("media fault")

    payload = b"preserve-after-transfer"
    with monkeypatch.context() as faults:
        faults.setattr(manager.executor, "submit", capture_submit)
        if fault in {"exdev", "enospc", "move"}:
            faults.setattr(Path, "rename", fail_move)
        elif fault == "probe":
            faults.setattr(workflow.media, "probe_video", fail_media)
        else:
            faults.setattr(FakeASR, "transcribe", fail_media)
        response = saozi_client.post("/companion-api/jobs/upload?language=zh", content=payload)
        assert response.status_code == 202
        futures[0].result(timeout=5)
    job_id = response.json()["id"]
    directory = tmp_path / job_id
    manifest = json.loads((directory / "job.json").read_text())
    diagnostic = json.loads((directory / "gui.json").read_text())
    assert manager.active is None
    assert manager.last["state"] == diagnostic["state"] == "failed"
    assert manifest["state"] == ("transcribing" if fault == "asr" else "download_failed")
    assert manifest["llm_model"] == diagnostic["model"]
    if fault in {"probe", "asr"}:
        assert (directory / "source.mp4").read_bytes() == payload
    else:
        assert not (directory / "source.mp4").exists()
    if fault == "exdev":
        assert "no copy attempted" in diagnostic["error"]
    assert not list(tmp_path.glob(".saozi-upload-*"))
    record_property("failure", json.dumps({"fault": fault, "manifest": manifest,
                                           "diagnostic": diagnostic, "active": manager.active,
                                           "source_retained": (directory / "source.mp4").exists()}))
    retry = saozi_client.post("/companion-api/jobs/upload?language=zh", content=b"retry")
    assert retry.status_code == 202
    assert completed(saozi_client, retry.json()["id"])["state"] == "completed"


def test_executor_handoff_failure_cleans_owned_upload_and_releases_admission(saozi_client, tmp_path, monkeypatch):
    manager = saozi_client.app.state.manager

    def fail_submit(*args, **kwargs):
        raise RuntimeError("executor handoff failed")

    with monkeypatch.context() as faults:
        faults.setattr(manager.executor, "submit", fail_submit)
        with pytest.raises(RuntimeError, match="executor handoff failed"):
            saozi_client.post("/companion-api/saozi/upload", content=b"video")
    assert manager.active is None
    assert manager.last["state"] == "failed"
    assert not list(tmp_path.glob(".saozi-upload-*"))
    assert json.loads((tmp_path / manager.last["id"] / "gui.json").read_text())["state"] == "failed"
    retry = saozi_client.post("/companion-api/saozi/upload?language=zh", content=b"retry")
    assert retry.status_code == 202
    assert completed(saozi_client, retry.json()["id"])["state"] == "completed"


@pytest.mark.parametrize("streamed", [False, True])
def test_upload_low_space_rejects_before_transfer_and_allows_retry(saozi_client, tmp_path, monkeypatch, streamed):
    from app.arctime import saozi_api
    manager = saozi_client.app.state.manager
    usage = saozi_api.shutil.disk_usage(tmp_path)
    with monkeypatch.context() as faults:
        faults.setattr(saozi_api.shutil, "disk_usage", lambda path: usage._replace(free=0))
        response = saozi_client.post("/companion-api/jobs/upload", content=iter([b"video"]) if streamed else b"video")
    assert response.status_code == 413
    assert manager.active is None
    assert not list(tmp_path.glob(".saozi-upload-*"))
    assert not list(tmp_path.glob("*/source.mp4"))
    if streamed:
        assert manager.last["state"] == "failed"
    retry = saozi_client.post("/companion-api/jobs/upload?language=zh", content=b"retry")
    assert retry.status_code == 202
    assert completed(saozi_client, retry.json()["id"])["state"] == "completed"


def test_upload_rejected_identity_never_unlinks_external_file(saozi_client, tmp_path, monkeypatch):
    from app.arctime import saozi_api
    mkstemp = saozi_api.tempfile.mkstemp
    external_root = tmp_path / "external"
    external_root.mkdir()
    external = external_root / ".saozi-upload-lookalike"
    external.write_bytes(b"external-original")

    def outside_file(*args, **kwargs):
        if kwargs.get("prefix") == ".saozi-upload-":
            return os.open(external, os.O_RDWR), str(external)
        return mkstemp(*args, **kwargs)

    with monkeypatch.context() as faults:
        faults.setattr(saozi_api.tempfile, "mkstemp", outside_file)
        with pytest.raises(OSError, match="ownership changed"):
            saozi_client.post("/companion-api/jobs/upload", content=b"video")
    assert external.read_bytes() == b"external-original"
    assert saozi_client.app.state.manager.active is None


@pytest.mark.parametrize("replacement", ["symlink", "regular"])
def test_upload_handoff_replacement_is_preserved_on_worker_cleanup(saozi_client, tmp_path, monkeypatch, replacement):
    manager = saozi_client.app.state.manager
    submit = manager.executor.submit
    futures, uploads = [], []
    external = tmp_path / "external-original.mp4"
    external.write_bytes(b"external-original")

    def substitute_before_worker(*args, **kwargs):
        upload = kwargs["owned_upload"]
        uploads.append(upload.path)
        upload.path.rename(tmp_path / "owned-retained")
        if replacement == "symlink":
            upload.path.symlink_to(external)
        else:
            upload.path.write_bytes(b"replacement")
        future = submit(*args, **kwargs)
        futures.append(future)
        return future

    with monkeypatch.context() as faults:
        faults.setattr(manager.executor, "submit", substitute_before_worker)
        response = saozi_client.post("/companion-api/jobs/upload", content=b"uploaded-original")
        assert response.status_code == 202
        futures[0].result(timeout=5)
    assert manager.active is None
    assert manager.last["state"] == "failed"
    assert "ownership changed" in manager.last["error"]
    assert external.read_bytes() == b"external-original"
    assert (tmp_path / "owned-retained").read_bytes() == b"uploaded-original"
    assert uploads[0].read_bytes() == (b"external-original" if replacement == "symlink" else b"replacement")
    assert uploads[0].is_symlink() == (replacement == "symlink")
    assert not (tmp_path / response.json()["id"] / "source.mp4").exists()


def test_transfer_with_secondary_record_and_cleanup_failures_releases_admission(saozi_client, tmp_path, monkeypatch, record_property):
    manager = saozi_client.app.state.manager
    primary = OSError(errno.EXDEV, "transfer primary")
    rename, unlink, write_json, submit = Path.rename, Path.unlink, workflow.media.write_json, manager.executor.submit
    futures = []

    def fail_move(path, target):
        if path.name.startswith(".saozi-upload-"):
            raise primary
        return rename(path, target)

    def fail_cleanup(path, *args, **kwargs):
        if path.name.startswith(".saozi-upload-"):
            raise PermissionError(errno.EACCES, "cleanup secondary")
        return unlink(path, *args, **kwargs)

    def fail_record(path, value):
        if path.name == "gui.json" and value["state"] == "failed":
            raise OSError(errno.ENOSPC, "record secondary")
        return write_json(path, value)

    def capture_submit(*args, **kwargs):
        future = submit(*args, **kwargs)
        futures.append(future)
        return future

    with monkeypatch.context() as faults:
        faults.setattr(Path, "rename", fail_move)
        faults.setattr(Path, "unlink", fail_cleanup)
        faults.setattr(workflow.media, "write_json", fail_record)
        faults.setattr(manager.executor, "submit", capture_submit)
        response = saozi_client.post("/companion-api/jobs/upload", content=b"owned-original")
        assert response.status_code == 202
        failure = futures[0].exception(timeout=5)
    assert manager.active is None
    assert manager.last["state"] == "failed"
    assert isinstance(failure, OSError)
    assert failure.errno == errno.EXDEV
    assert "no copy attempted" in str(failure)
    assert isinstance(failure.__cause__, OSError)
    assert failure.__cause__.errno == errno.ENOSPC
    assert json.loads((tmp_path / response.json()["id"] / "job.json").read_text())["state"] == "download_failed"
    assert len(list(tmp_path.glob(".saozi-upload-*"))) == 1
    assert next(tmp_path.glob(".saozi-upload-*")).read_bytes() == b"owned-original"
    record_property("secondary_failures", json.dumps({"active": manager.active, "last": manager.last,
                                                      "failure_errno": failure.errno,
                                                      "owned_upload_retained": True}))
    retry = saozi_client.post("/companion-api/jobs/upload?language=zh", content=b"retry")
    assert retry.status_code == 202
    assert completed(saozi_client, retry.json()["id"])["state"] == "completed"


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
