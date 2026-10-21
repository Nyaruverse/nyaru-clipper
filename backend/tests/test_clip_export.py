from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from sqlmodel import select


def _reset_runtime_state() -> None:
    try:
        from app.db import reset_db_runtime
    except ModuleNotFoundError:
        return
    reset_db_runtime()


@pytest.fixture()
def backend_env(tmp_path, monkeypatch) -> dict[str, Path | str]:
    data_dir = tmp_path / "data"
    db_path = tmp_path / "task-state.sqlite3"
    monkeypatch.setenv("APP_DATA_DIR", str(data_dir))
    monkeypatch.setenv("APP_DATABASE_URL", f"sqlite:///{db_path}")
    _reset_runtime_state()
    return {"data_dir": data_dir, "db_path": db_path}


def _create_task(source_url: str) -> str:
    from app.db import init_db, session_scope
    from app.repositories.tasks import create_task

    init_db()
    with session_scope() as session:
        payload, _ = create_task(session, source_url)
        return payload["task_id"]


def _seed_export_inputs(data_dir: Path, task_id: str, *, duration_seconds: float) -> int:
    from app.db import session_scope
    from app.models import ClipCandidate
    from app.services.storage import persist_artifact_metadata

    task_root = data_dir / "tasks" / task_id
    source_path = task_root / "raw" / "source.mp4"
    media_probe_path = task_root / "work" / "media-probe.json"
    source_path.parent.mkdir(parents=True, exist_ok=True)
    media_probe_path.parent.mkdir(parents=True, exist_ok=True)
    source_path.write_bytes(b"source-video")
    media_probe_path.write_text(
        json.dumps(
            {
                "format": {"duration": str(duration_seconds)},
                "streams": [{"codec_type": "video", "width": 1920, "height": 1080}],
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    with session_scope() as session:
        persist_artifact_metadata(
            session,
            task_id=task_id,
            stage_name="ingest",
            kind="source_video",
            path=source_path,
            metadata={"output_file_path": str(source_path)},
        )
        persist_artifact_metadata(
            session,
            task_id=task_id,
            stage_name="media_prep",
            kind="media_probe",
            path=media_probe_path,
            metadata={"ffprobe_metadata": {"format": {"duration": str(duration_seconds)}}},
        )
        candidate = ClipCandidate(
            task_id=task_id,
            start_seconds=10.0,
            end_seconds=22.0,
            score=0.91,
            reason="peak-moment",
            status="candidate",
        )
        session.add(candidate)
        session.flush()
        session.refresh(candidate)
        return int(candidate.id)


@pytest.mark.parametrize("fault", ["none", "unlink", "accounting"])
def test_public_export_overwrite_persists_final_tree_size(backend_env, monkeypatch, caplog, fault):
    data_dir = Path(backend_env["data_dir"])
    task_id = _create_task("https://www.bilibili.com/video/BV1hs411c7mW")
    candidate_id = _seed_export_inputs(data_dir, task_id, duration_seconds=120.0)
    from app.db import session_scope
    from app.models import Task, TaskStage
    from app.services.clip_export import export_confirmed_clip
    from app.services.storage import get_task_root
    from app.services import storage
    from sqlalchemy.exc import OperationalError

    root = get_task_root(task_id)
    orphan = root / "exports" / "interrupted.previous"
    orphan.write_bytes(b"retained-orphan")
    content = b"first-output"

    def fake_run(args, **kwargs):
        Path(args[-1]).write_bytes(content)
        return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")

    monkeypatch.setattr("subprocess.run", fake_run)
    with session_scope() as session:
        first = export_confirmed_clip(session, task_id, candidate_id=candidate_id)
    content = b"replacement-output"
    unlink = Path.unlink

    def fail_owned_cleanup(path, *args, **kwargs):
        if path.suffix == ".previous" and path != orphan:
            raise OSError("owned backup cleanup failed")
        return unlink(path, *args, **kwargs)

    with monkeypatch.context() as patch:
        if fault == "unlink":
            patch.setattr(Path, "unlink", fail_owned_cleanup)
        with session_scope() as session:
            original_refresh = storage.refresh_task_storage

            def fail_recount(accounting, *, task_id):
                if accounting is not session:
                    raise OperationalError("recount", {}, RuntimeError("accounting unavailable"))
                original_refresh(accounting, task_id=task_id)

            if fault == "accounting":
                patch.setattr(storage, "refresh_task_storage", fail_recount)
            if fault == "unlink":
                with pytest.raises(OSError, match="owned backup cleanup failed"):
                    export_confirmed_clip(session, task_id, candidate_id=candidate_id)
            else:
                export_confirmed_clip(session, task_id, candidate_id=candidate_id)
    with session_scope() as session:
        actual = sum(p.stat().st_size for p in root.rglob("*") if p.is_file())
        if fault == "accounting":
            assert session.get(Task, task_id).storage_bytes > actual
            assert "storage_recount_deferred" in caplog.text
        else:
            assert session.get(Task, task_id).storage_bytes == actual
        assert session.get(Task, task_id).status == "pending"
        assert session.exec(select(TaskStage).where(TaskStage.task_id == task_id, TaskStage.name == "export")).one().status == "success"
    assert first.output_path.read_bytes() == b"replacement-output"
    assert orphan.read_bytes() == b"retained-orphan"
    assert len(list((root / "exports").glob("*.previous"))) == 1 + int(fault == "unlink")
    with session_scope() as session:
        result = export_confirmed_clip(session, task_id, candidate_id=candidate_id)
    assert result.output_path.read_bytes() == b"replacement-output"
    with session_scope() as session:
        assert session.get(Task, task_id).storage_bytes == sum(p.stat().st_size for p in root.rglob("*") if p.is_file())


def test_export_confirmed_range(backend_env, monkeypatch) -> None:
    data_dir = Path(backend_env["data_dir"])
    task_id = _create_task("https://www.bilibili.com/video/BV1hs411c7mW")
    candidate_id = _seed_export_inputs(data_dir, task_id, duration_seconds=120.0)
    commands: list[list[str]] = []

    def fake_run(args: list[str], **kwargs) -> subprocess.CompletedProcess[str]:
        commands.append(list(args))
        output_path = Path(args[-1])
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"exported-clip")
        return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")

    monkeypatch.setattr("subprocess.run", fake_run)

    from app.db import session_scope
    from app.models import Artifact, ClipCandidate, TaskStage
    from app.services.clip_export import export_confirmed_clip

    with session_scope() as session:
        result = export_confirmed_clip(
            session,
            task_id,
            candidate_id=candidate_id,
            start_s=12.5,
            end_s=20.0,
        )

    assert result.output_path.name == "clip-00012500-00020000.mp4"
    assert result.output_path.exists()
    assert result.start_s == 12.5
    assert result.end_s == 20.0
    assert [command[0] for command in commands] == ["ffmpeg"]
    assert "subtitles" not in " ".join(commands[0])

    with session_scope() as session:
        stage = session.exec(
            select(TaskStage).where(TaskStage.task_id == task_id).where(TaskStage.name == "export")
        ).one()
        artifacts = session.exec(
            select(Artifact).where(Artifact.task_id == task_id).where(Artifact.stage_name == "export")
        ).all()
        candidate = session.exec(select(ClipCandidate).where(ClipCandidate.id == candidate_id)).one()
        stage_status = stage.status
        stage_summary = stage.summary
        candidate_status = candidate.status
        artifact_kinds = {artifact.kind for artifact in artifacts}
        artifact_metadata = json.loads(artifacts[0].metadata_json)

    assert stage_status == "success"
    assert stage_summary == "Exported clip clip-00012500-00020000.mp4"
    assert candidate_status == "exported"
    assert artifact_kinds == {"clip_export"}
    assert artifact_metadata["candidate_id"] == candidate_id
    assert artifact_metadata["start_s"] == 12.5
    assert artifact_metadata["end_s"] == 20.0
    assert artifact_metadata["source_duration_s"] == 120.0
    assert artifact_metadata["export_backend"] == "cpu"
    assert artifact_metadata["video_encoder"] == "libx264"


def test_rejects_out_of_bounds_range(backend_env) -> None:
    data_dir = Path(backend_env["data_dir"])
    task_id = _create_task("https://www.bilibili.com/video/BV1is411c7mX")
    candidate_id = _seed_export_inputs(data_dir, task_id, duration_seconds=30.0)

    from app.db import session_scope
    from app.models import Artifact, TaskStage
    from app.services.clip_export import ClipExportFailure, export_confirmed_clip

    with session_scope() as session:
        with pytest.raises(ClipExportFailure, match="outside the source duration"):
            export_confirmed_clip(
                session,
                task_id,
                candidate_id=candidate_id,
                start_s=10.0,
                end_s=40.0,
            )

    with session_scope() as session:
        stage = session.exec(
            select(TaskStage).where(TaskStage.task_id == task_id).where(TaskStage.name == "export")
        ).one()
        artifacts = session.exec(
            select(Artifact).where(Artifact.task_id == task_id).where(Artifact.stage_name == "export")
        ).all()
        stage_status = stage.status
        artifact_count = len(artifacts)

    assert stage_status == "pending"
    assert artifact_count == 0


@pytest.mark.parametrize("failure", ["process", "empty", "exception", "database"])
def test_reexport_failure_preserves_published_clip(backend_env, monkeypatch, failure: str) -> None:
    # Given: an already published clip and its artifact record.
    from app.db import session_scope
    from app.models import Artifact
    from app.services import clip_export

    task_id = _create_task("https://www.bilibili.com/video/BV1preserve01")
    candidate_id = _seed_export_inputs(Path(backend_env["data_dir"]), task_id, duration_seconds=120)

    def successful_run(args, **kwargs):
        Path(args[-1]).write_bytes(b"previous complete clip")
        return subprocess.CompletedProcess(args, 0, "", "")

    monkeypatch.setattr("subprocess.run", successful_run)
    with session_scope() as session:
        previous = clip_export.export_confirmed_clip(session, task_id, candidate_id=candidate_id)
    with session_scope() as session:
        artifact = session.get(Artifact, previous.artifact_id)
        original_metadata = artifact.metadata_json

    def failed_run(args, **kwargs):
        Path(args[-1]).write_bytes(b"" if failure == "empty" else b"partial replacement")
        if failure == "exception":
            raise OSError("encoder interrupted")
        return subprocess.CompletedProcess(args, 0 if failure in {"empty", "database"} else 1, "", "encoding failed")

    def failed_persistence(*args, **kwargs):
        raise OSError("database persistence interrupted")

    monkeypatch.setattr("subprocess.run", failed_run)
    if failure == "database":
        monkeypatch.setattr(clip_export, "_persist_export_artifact", failed_persistence)

    # When: replacement encoding or publication fails.
    with pytest.raises((clip_export.ClipExportFailure, OSError)):
        with session_scope() as session:
            clip_export.export_confirmed_clip(session, task_id, candidate_id=candidate_id)

    # Then: the published bytes and usable artifact remain unchanged.
    assert previous.output_path.read_bytes() == b"previous complete clip"
    with session_scope() as session:
        artifact = session.get(Artifact, previous.artifact_id)
        assert artifact.metadata_json == original_metadata
        assert session.exec(select(Artifact).where(Artifact.kind == "clip_export")).all() == [artifact]
    assert not list(previous.output_path.parent.glob("*.partial.mp4"))


@pytest.mark.parametrize("competing_start", [None, 11.0])
def test_simultaneous_reexport_rejects_competing_writer(backend_env, monkeypatch, competing_start) -> None:
    # Given: one encoder holds the same output while a second request arrives.
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event

    from app.db import session_scope
    from app.models import Artifact
    from app.services.clip_export import ClipExportFailure, export_confirmed_clip

    task_id = _create_task("https://www.bilibili.com/video/BV1concurr001")
    candidate_id = _seed_export_inputs(Path(backend_env["data_dir"]), task_id, duration_seconds=120)
    started, release = Event(), Event()

    def controlled_run(args, **kwargs):
        started.set()
        assert release.wait(timeout=10)
        Path(args[-1]).write_bytes(b"one complete publication")
        return subprocess.CompletedProcess(args, 0, "", "")

    monkeypatch.setattr("subprocess.run", controlled_run)

    def export(start_s=None):
        with session_scope() as session:
            return export_confirmed_clip(session, task_id, candidate_id=candidate_id, start_s=start_s)

    # When: the competing request targets the same interval.
    with ThreadPoolExecutor(max_workers=1) as executor:
        first = executor.submit(export)
        try:
            assert started.wait(timeout=10)
            with pytest.raises(ClipExportFailure) as rejected:
                export(competing_start)
            assert rejected.value.code == "export_busy"
        finally:
            release.set()
        result = first.result(timeout=10)

    # Then: only one complete file and one consistent artifact were published.
    assert result.output_path.read_bytes() == b"one complete publication"
    with session_scope() as session:
        artifacts = session.exec(select(Artifact).where(Artifact.kind == "clip_export")).all()
        assert len(artifacts) == 1
        assert artifacts[0].path == str(result.output_path)


def test_amf_missing_output_still_falls_back_to_cpu(backend_env, monkeypatch) -> None:
    from app.db import session_scope
    from app.services import export_encoding
    from app.services.clip_export import export_confirmed_clip

    task_id = _create_task("https://www.bilibili.com/video/BV1amffall01")
    candidate_id = _seed_export_inputs(Path(backend_env["data_dir"]), task_id, duration_seconds=120)
    monkeypatch.setenv("APP_EXPORT_VIDEO_BACKEND", "windows-amf")
    monkeypatch.setenv("APP_WINDOWS_FFMPEG_BINARY", "/synthetic/ffmpeg.exe")
    monkeypatch.setattr(export_encoding, "_convert_wsl_path", str)
    encoders = []

    def missing_amf_output(args, **kwargs):
        encoder = args[args.index("-c:v") + 1]
        encoders.append(encoder)
        if encoder == "libx264":
            Path(args[-1]).write_bytes(b"complete CPU fallback")
        return subprocess.CompletedProcess(args, 0, "", "")

    monkeypatch.setattr("subprocess.run", missing_amf_output)
    with session_scope() as session:
        result = export_confirmed_clip(session, task_id, candidate_id=candidate_id)
    assert encoders == ["h264_amf", "libx264"]
    assert result.output_path.read_bytes() == b"complete CPU fallback"
