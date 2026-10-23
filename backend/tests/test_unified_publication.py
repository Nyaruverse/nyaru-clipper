from __future__ import annotations

from itertools import product
from pathlib import Path
from uuid import uuid4
from typing import Literal, assert_never

import pytest
from sqlmodel import Session, select

from app.models import WorkstationEvent
from app.models_unified import OperationStep, UnifiedOperation, UnifiedPublication
from app.services.task_operations import begin_step, bind_task, claim_operation, enqueue_operation, set_admissions
from app.services.task_publication import Publisher
from app.services.publication_receipts import recovery_decision
from test_unified_operations import database


class PowerCut(RuntimeError):
    pass


def running(engine):
    with Session(engine) as session:
        binding = bind_task(session, uuid4(), "new", "g", origin="native")
        enqueue_operation(session, binding.task_id, "process_live", {"input": {"video": "hash"}, "config": {"language": "ja"}})
        set_admissions(session, paused=False)
        session.commit()
    with Session(engine) as session:
        operation = claim_operation(session)
        step = begin_step(session, operation.id, operation.execution_token, "clip-1", ("video", "subtitles"))
        session.commit()
        return operation.id, operation.execution_token, step.id


@pytest.mark.parametrize("fault", ["intent", "prepared", "ready", "file:subtitles", "file:video", "committed"])
def test_crash_at_every_set_boundary_never_completes_parent(tmp_path: Path, fault: str) -> None:
    engine = database(tmp_path)
    operation_id, token, step_id = running(engine)
    root = tmp_path / "artifacts"
    stage = root / ".unified/staging" / operation_id / "1"
    stage.mkdir(parents=True)
    (stage / "clip.mp4").write_bytes(b"registered video")
    (stage / "clip.srt").write_bytes(b"registered subtitles")

    def crash(point: str) -> None:
        if point == fault:
            raise PowerCut(point)

    publisher = Publisher(engine, root, fault=crash)
    with pytest.raises(PowerCut):
        publisher.publish(operation_id, token, step_id, {"video": stage / "clip.mp4", "subtitles": stage / "clip.srt"})
    publisher = Publisher(engine, root)
    decisions = publisher.reconcile(processes_released=lambda operation: True)
    with Session(engine) as session:
        publication = session.exec(select(UnifiedPublication)).one()
        operation = session.get(UnifiedOperation, operation_id)
        step = session.get(OperationStep, step_id)
        assert operation.state == "interrupted"
        if fault == "intent":
            assert decisions == ["J02"] and publication.state == "interrupted"
            assert step.state != "succeeded"
        else:
            assert publication.state == "committed" and step.state == "succeeded"
            assert len(list((root / ".unified/results" / publication.id).iterdir())) == 2
            events = session.exec(select(WorkstationEvent).where(WorkstationEvent.event_type == "publication.committed")).all()
            assert len(events) == 1
    assert Publisher(engine, root).reconcile(processes_released=lambda operation: True) == (["J12"] if fault != "intent" else [])


def test_recovery_table_has_exactly_one_rule_per_combination() -> None:
    seen = set()
    for database_state, receipt, outputs, eligible, staging in product(
        ("N", "R", "C"), ("missing", "corrupt", "valid"), ("zero", "partial", "all", "bad"), (False, True), (False, True),
    ):
        result = recovery_decision(database_state, receipt, outputs, eligible, staging)
        rules = {
            "J00": receipt == "corrupt",
            "J01": receipt != "corrupt" and not eligible and database_state != "C",
            "J14": receipt != "corrupt" and not eligible and database_state == "C",
            "J02": receipt == "missing" and eligible and database_state == "N" and outputs == "zero",
            "J03": receipt == "missing" and eligible and database_state == "N" and outputs != "zero",
            "J04": receipt == "missing" and eligible and database_state != "N",
            "J05": receipt == "valid" and eligible and database_state == "N" and outputs == "zero" and staging,
            "J06": receipt == "valid" and eligible and database_state == "N" and outputs == "zero" and not staging,
            "J07": receipt == "valid" and eligible and database_state == "N" and outputs != "zero",
            "J08": receipt == "valid" and eligible and database_state == "R" and outputs in {"zero", "partial"} and staging,
            "J09": receipt == "valid" and eligible and database_state == "R" and outputs in {"zero", "partial"} and not staging,
            "J10": receipt == "valid" and eligible and database_state == "R" and outputs == "all",
            "J11": receipt == "valid" and eligible and database_state == "R" and outputs == "bad",
            "J12": receipt == "valid" and eligible and database_state == "C" and outputs == "all",
            "J13": receipt == "valid" and eligible and database_state == "C" and outputs != "all",
        }
        assert [key for key, matches in rules.items() if matches] == [result]
        seen.add(result)
    assert len(seen) == 15


@pytest.mark.parametrize("damage,expected", [("staging", "J09"), ("receipt", "J00"), ("receipt-missing", "J04"),
    ("output", "J11"), ("cancel", "J01"), ("database-receipt", "J00")])
def test_partial_set_damage_and_cancel_cannot_be_adopted(tmp_path: Path,
        damage: Literal['staging', 'receipt', 'receipt-missing', 'output', 'cancel', 'database-receipt'], expected: str) -> None:
    from app.services.task_operations import request_cancel
    engine = database(tmp_path)
    operation_id, token, step_id = running(engine)
    root = tmp_path / "artifacts"
    stage = root / ".unified/staging" / operation_id / "1"
    stage.mkdir(parents=True)
    video, subtitles = stage / "clip.mp4", stage / "clip.srt"
    video.write_bytes(b"video")
    subtitles.write_bytes(b"srt")

    def crash(point: str) -> None:
        if point == "file:subtitles":
            raise PowerCut(point)

    with pytest.raises(PowerCut):
        Publisher(engine, root, fault=crash).publish(operation_id, token, step_id, {"video": video, "subtitles": subtitles})
    with Session(engine) as session:
        publication = session.exec(select(UnifiedPublication)).one()
        publication_id = publication.id
        if damage == "cancel":
            request_cancel(session, operation_id)
        elif damage == "database-receipt":
            publication.receipt_json = "{broken"
            session.add(publication)
        session.commit()
    receipt = root / ".unified/receipts" / f"{publication_id}.json"
    match damage:
        case "staging":
            video.unlink()
        case "receipt":
            receipt.write_bytes(b"corrupt")
        case "receipt-missing":
            receipt.unlink()
        case "output":
            next((root / ".unified/results" / publication_id).iterdir()).write_bytes(b"corrupt")
        case 'cancel' | 'database-receipt':
            pass
        case unreachable:
            assert_never(unreachable)
    assert Publisher(engine, root).reconcile(processes_released=lambda operation: True) == [expected]
    with Session(engine) as session:
        assert session.get(OperationStep, step_id).state != "succeeded"
        assert session.exec(select(WorkstationEvent).where(WorkstationEvent.event_type == "publication.committed")).all() == []


def test_published_files_are_independent_of_staging_and_history_survives_retry(tmp_path: Path) -> None:
    from app.services.task_operations import complete_operation, retry_operation
    engine = database(tmp_path)
    operation_id, token, step_id = running(engine)
    root = tmp_path / "artifacts"
    stage = root / ".unified/staging" / operation_id / "1"
    stage.mkdir(parents=True)
    video, subtitles = stage / "clip.mp4", stage / "clip.srt"
    video.write_bytes(b"video")
    subtitles.write_bytes(b"srt")
    publication_id = Publisher(engine, root).publish(operation_id, token, step_id, {"video": video, "subtitles": subtitles})
    assert Publisher(engine, root).publish(operation_id, token, step_id, {"video": video, "subtitles": subtitles}) == publication_id
    video.write_bytes(b"changed staging")
    assert (root / ".unified/results" / publication_id / "video.mp4").read_bytes() == b"video"
    with Session(engine) as session:
        complete_operation(session, operation_id, token, "failed", failure_code="later_translation_failed")
        session.commit()
    with Session(engine) as session:
        retry_operation(session, operation_id)
        session.commit()
    with Session(engine) as session:
        claim_operation(session)
        session.commit()
    assert Publisher(engine, root).reconcile(processes_released=lambda operation: True) == ["J12"]
    with Session(engine) as session:
        assert len(session.exec(select(WorkstationEvent).where(WorkstationEvent.event_type == "publication.committed")).all()) == 1


def test_disk_full_retains_receipt_and_subset_without_success(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import errno
    from app.services import task_publication
    engine = database(tmp_path)
    operation_id, token, step_id = running(engine)
    root = tmp_path / "artifacts"
    stage = root / ".unified/staging" / operation_id / "1"
    stage.mkdir(parents=True)
    files = {"video": stage / "clip.mp4", "subtitles": stage / "clip.srt"}
    for path in files.values():
        path.write_bytes(path.name.encode())
    actual = task_publication.publish_file

    def disk_full(source: Path, target: Path, sha256: str, size: int) -> None:
        if target.suffix == ".mp4":
            raise OSError(errno.ENOSPC, "isolated disk-full injection")
        actual(source, target, sha256, size)

    monkeypatch.setattr(task_publication, "publish_file", disk_full)
    with pytest.raises(OSError) as failure:
        Publisher(engine, root).publish(operation_id, token, step_id, files)
    assert failure.value.errno == errno.ENOSPC
    with Session(engine) as session:
        publication = session.exec(select(UnifiedPublication)).one()
        assert publication.state == "ready"
        assert session.get(OperationStep, step_id).state == "running"
        assert len(list((root / ".unified/results" / publication.id).iterdir())) == 1
    monkeypatch.setattr(task_publication, "publish_file", actual)
    assert Publisher(engine, root).reconcile(processes_released=lambda operation: True) == ["J08"]


def test_recovery_requires_released_processes_and_never_runs_engines(tmp_path: Path) -> None:
    from app.services.task_operations import OperationConflict
    engine = database(tmp_path)
    running(engine)
    with pytest.raises(OperationConflict, match="still own"):
        Publisher(engine, tmp_path / "files").reconcile(processes_released=lambda operation: False)
    with Session(engine) as session:
        assert claim_operation(session) is None


@pytest.mark.parametrize('commit_number,after,expected', [(1, False, []), (1, True, ['J02']),
    (2, False, ['J05']), (2, True, ['J08']), (3, False, ['J08']), (3, True, ['J08']),
    (4, False, ['J10']), (4, True, ['J10']), (5, False, ['J10']), (5, True, ['J12'])])
def test_database_commit_failure_is_reconciled_from_observed_durable_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
        commit_number: int, after: bool, expected: list[str]) -> None:
    from sqlalchemy.exc import OperationalError
    engine = database(tmp_path)
    operation_id, token, step_id = running(engine)
    root = tmp_path / 'artifacts'
    stage = root / '.unified/staging' / operation_id / '1'
    stage.mkdir(parents=True)
    files = {'video': stage / 'clip.mp4', 'subtitles': stage / 'clip.srt'}
    for path in files.values():
        path.write_bytes(path.name.encode())
    original = Session.commit
    calls = [0]

    def failure(session: Session) -> None:
        calls[0] += 1
        if calls[0] == commit_number:
            if after:
                original(session)
            raise OperationalError('injected commit boundary', {}, None)
        original(session)

    with monkeypatch.context() as patch:
        patch.setattr(Session, 'commit', failure)
        with pytest.raises(OperationalError):
            Publisher(engine, root).publish(operation_id, token, step_id, files)
    assert Publisher(engine, root).reconcile(processes_released=lambda operation: True) == expected
    with Session(engine) as session:
        assert session.get(UnifiedOperation, operation_id).state == 'interrupted'
        committed = session.exec(select(UnifiedPublication).where(UnifiedPublication.state == 'committed')).all()
        assert len(committed) == (1 if commit_number > 1 else 0)


