from pathlib import Path

import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, SQLModel, create_engine, select


def _reset_runtime_state() -> None:
    try:
        from app.db import reset_db_runtime
    except ModuleNotFoundError:
        return
    reset_db_runtime()


def test_ensure_task_dirs_creates_canonical_layout(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("APP_DATA_DIR", str(tmp_path / "data"))
    _reset_runtime_state()

    from app.services.storage import ensure_task_dirs

    task_dirs = ensure_task_dirs("task-demo")

    assert sorted(task_dirs.keys()) == ["exports", "logs", "raw", "reports", "work"]
    assert all(Path(path).is_dir() for path in task_dirs.values())
    assert {Path(path).parent.name for path in task_dirs.values()} == {"task-demo"}
    assert {Path(path).name for path in task_dirs.values()} == set(task_dirs.keys())


@pytest.fixture
def accounting(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_DATA_DIR", str(tmp_path / "data"))
    from app.models import Task
    from app.services.storage import ensure_task_dirs

    engine = create_engine(f"sqlite:///{tmp_path / 'accounting.sqlite'}")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        for task_id in ("one", "two"):
            session.add(Task(id=task_id, source_url="https://example.invalid/video", normalized_source_url=f"https://example.invalid/{task_id}"))
            ensure_task_dirs(task_id)["work"].joinpath("unregistered.bin").write_bytes(b"unregistered")
        session.commit()
        yield session, engine
    engine.dispose()


def test_single_registration_and_existing_file_update_are_immediate(accounting):
    from app.models import Task
    from app.services.storage import get_task_root, persist_artifact_metadata

    session, _ = accounting
    path = get_task_root("one") / "work" / "unregistered.bin"
    first = persist_artifact_metadata(session, task_id="one", stage_name="asr", kind="first", path=path)
    assert first.id is not None
    assert session.get(Task, "one").storage_bytes == len(b"unregistered")
    path.write_bytes(b"replacement")
    second = persist_artifact_metadata(session, task_id="one", stage_name="asr", kind="second", path=path)
    assert second.id != first.id
    assert session.get(Task, "one").storage_bytes == len(b"replacement")


def test_batch_empty_nested_and_task_session_isolation(accounting):
    from app.models import Task
    from app.services.storage import artifact_batch, get_task_root, persist_artifact_metadata

    session, engine = accounting
    path = get_task_root("one") / "work" / "unregistered.bin"
    with artifact_batch(session, task_id="one"):
        with pytest.raises(RuntimeError, match="already active"):
            with artifact_batch(session, task_id="one"):
                pytest.fail("same-task nesting must be rejected")
        with Session(engine) as other:
            with artifact_batch(other, task_id="one"):
                pass
            assert other.get(Task, "one").storage_bytes == len(b"unregistered")
            other.rollback()
        with artifact_batch(session, task_id="two"):
            pass
        assert session.get(Task, "two").storage_bytes == len(b"unregistered")
        persist_artifact_metadata(session, task_id="one", stage_name="asr", kind="first", path=path)
        assert session.get(Task, "one").storage_bytes == 0
    assert session.get(Task, "one").storage_bytes == len(b"unregistered")
    session.rollback()
    with Session(engine) as other:
        assert other.get(Task, "one").storage_bytes == 0


@pytest.mark.parametrize("sql_failure", [False, True])
def test_aborted_batch_preserves_error_and_retry_recounts_leftover_files(accounting, sql_failure):
    from app.models import Artifact, Task, WorkstationEvent
    from app.services.storage import artifact_batch, get_task_root, invalidate_translation_artifacts, persist_artifact_metadata

    session, _ = accounting
    root = get_task_root("one")
    path = root / "work" / "translation.json"
    path.write_bytes(b"translation")
    with pytest.raises(IntegrityError if sql_failure else OSError):
        with artifact_batch(session, task_id="one"):
            persist_artifact_metadata(session, task_id="one", stage_name="translation", kind="first", path=path)
            (root / "orphan.bin").write_bytes(b"orphan")
            if sql_failure:
                session.add(Task(id="one", source_url="duplicate", normalized_source_url="duplicate"))
                session.flush()
            else:
                raise OSError("interrupted publication")
    session.rollback()
    with artifact_batch(session, task_id="one"):
        persist_artifact_metadata(session, task_id="one", stage_name="translation", kind="retry", path=path)
    assert session.get(Task, "one").storage_bytes == len(b"unregisteredtranslationorphan")
    assert len(session.exec(select(Artifact)).all()) == 1
    assert len(session.exec(select(WorkstationEvent)).all()) == 1
    invalidate_translation_artifacts(session, task_id="one")
    assert session.get(Task, "one").storage_bytes == len(b"unregisteredorphan")


@pytest.mark.parametrize("publication,expected", [("asr", 3), ("preproofread", 2), ("final", 3), ("download", 2)])
def test_real_publication_consumers_scan_once(accounting, monkeypatch, publication, expected):
    from app.models import Artifact, Task, TaskStage, WorkstationEvent
    from app.services.asr_whisperx import _persist_asr_artifacts
    from app.services.downloader import _persist_success
    from app.services.storage import get_task_root
    from app.services.translation_provider import _persist_final_translation_publication, _persist_preproofread_artifacts

    session, _ = accounting
    for stage in ("translation", "ingest"):
        session.add(TaskStage(task_id="one", name=stage))
    session.commit()
    root = get_task_root("one")
    paths = [root / "work" / f"output-{i}" for i in range(3)]
    for path in paths:
        path.write_bytes(b"output")
    scans = []
    original = Path.rglob

    def counted(path, pattern):
        if path == root and pattern == "*":
            scans.append(path)
        return original(path, pattern)

    monkeypatch.setattr(Path, "rglob", counted)
    match publication:
        case "asr":
            _persist_asr_artifacts(session, task_id="one", audio_path=paths[0], transcript_path=paths[1], subtitle_path=paths[2], raw_alignment_path=paths[0], model_metadata={}, elapsed_seconds=1, segment_count=1, language="zh")
        case "preproofread":
            _persist_preproofread_artifacts(session, task_id="one", source_transcript_path=paths[0], transcript_path=paths[1], subtitle_path=paths[2], provider_metadata={}, elapsed_seconds=1, segment_count=1)
        case "final":
            _persist_final_translation_publication(session, task_id="one", audit_path=paths[0], transcript_path=paths[1], subtitle_path=paths[2], proofread_model="fixture", proofread_batch_count=1, elapsed_seconds=1, segment_count=1)
        case "download":
            _persist_success(session, task_id="one", output_path=paths[0], source_metadata={}, selected_downloader="fixture", fallback_used=False, auth_cookie_present=False)
        case unexpected:
            raise AssertionError(unexpected)
    artifacts = session.exec(select(Artifact)).all()
    events = session.exec(select(WorkstationEvent).where(WorkstationEvent.event_type == "artifact.ready")).all()
    assert len(scans) == 1
    assert session.get(Task, "one").storage_bytes == sum(p.stat().st_size for p in original(root, "*") if p.is_file())
    assert len(artifacts) == len(events) == expected
    assert all(artifact.id is not None for artifact in artifacts)


@pytest.mark.parametrize("export", [False, True])
def test_existing_report_or_export_recounts_replaced_file(accounting, export):
    from app.models import Task, WorkstationEvent
    from app.services.clip_export import _persist_export_artifact
    from app.services.reporting import _persist_report_artifact
    from app.services.storage import get_task_root

    session, _ = accounting
    path = get_task_root("one") / "exports" / "output"

    def publish():
        if export:
            return _persist_export_artifact(session, task_id="one", candidate_id=1, output_path=path, start_s=0, end_s=1, source_duration_s=2, source_video_reference="source", export_backend="cpu", video_encoder="fixture")
        return _persist_report_artifact(session, task_id="one", output_path=path)

    path.write_bytes(b"old")
    original_id = publish().id
    path.write_bytes(b"replacement-output")
    assert publish().id == original_id
    assert session.get(Task, "one").storage_bytes == len(b"unregisteredreplacement-output")
    assert len(session.exec(select(WorkstationEvent)).all()) == 1


def test_cleanup_reconciliation_does_not_commit_or_expire_caller_changes(accounting):
    from app.models import Task
    from app.services.storage import reconcile_storage_after_cleanup

    session, engine = accounting
    task = session.get(Task, "one")
    task.title = "uncommitted caller title"
    reconcile_storage_after_cleanup(session, task_id="one")
    assert task.title == "uncommitted caller title"
    with Session(engine) as observer:
        persisted = observer.get(Task, "one")
        assert persisted.title is None
        assert persisted.storage_bytes == len(b"unregistered")
    session.rollback()


def test_accounting_correction_event_rolls_back_with_failed_commit_and_recovers(accounting, monkeypatch):
    from app.models import Task, WorkstationEvent
    from app.services.storage import reconcile_storage_after_cleanup
    from sqlalchemy.exc import OperationalError

    session, engine = accounting
    staged = []

    def fail_commit(accounting_session):
        staged.extend(event.event_type for event in accounting_session.exec(select(WorkstationEvent)).all())
        raise OperationalError("commit", {}, RuntimeError("injected accounting commit failure"))

    with monkeypatch.context() as patch:
        patch.setattr(Session, "commit", fail_commit)
        reconcile_storage_after_cleanup(session, task_id="one")
    with Session(engine) as observer:
        assert observer.get(Task, "one").storage_bytes == 0
        assert observer.exec(select(WorkstationEvent)).all() == []
    assert staged == ["task.updated"]
    reconcile_storage_after_cleanup(session, task_id="one")
    with Session(engine) as observer:
        assert observer.get(Task, "one").storage_bytes == len(b"unregistered")
        assert [event.event_type for event in observer.exec(select(WorkstationEvent)).all()] == ["task.updated"]
