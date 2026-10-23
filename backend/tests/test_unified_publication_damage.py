from __future__ import annotations

from pathlib import Path

import pytest
from sqlmodel import Session, select

from app.models_unified import UnifiedOperation, UnifiedPublication
from app.services.task_publication import Publisher
from test_unified_operations import database


from test_unified_publication import PowerCut, running


def test_committed_missing_file_is_unavailable_and_never_rewritten(tmp_path: Path) -> None:
    engine = database(tmp_path)
    operation_id, token, step_id = running(engine)
    root = tmp_path / 'artifacts'
    stage = root / '.unified/staging' / operation_id / '1'
    stage.mkdir(parents=True)
    files = {'video': stage / 'clip.mp4', 'subtitles': stage / 'clip.srt'}
    for path in files.values():
        path.write_bytes(path.name.encode())
    publisher = Publisher(engine, root)
    identifier = publisher.publish(operation_id, token, step_id, files)
    receipt = publisher.registered(identifier)
    removed = root / receipt.outputs[0].target
    removed.unlink()
    assert publisher.reconcile(processes_released=lambda operation: True) == ['J13']
    assert not removed.exists()
    with pytest.raises(ValueError):
        publisher.registered(identifier)


@pytest.mark.parametrize('point,expected', [('prepared', 'J05'), ('file:subtitles', 'J07')])
def test_durable_receipt_without_publication_row_is_not_silently_ignored(tmp_path: Path, point: str, expected: str) -> None:
    from sqlalchemy import delete
    engine = database(tmp_path)
    operation_id, token, step_id = running(engine)
    root = tmp_path / 'artifacts'
    stage = root / '.unified/staging' / operation_id / '1'
    stage.mkdir(parents=True)
    files = {'video': stage / 'clip.mp4', 'subtitles': stage / 'clip.srt'}
    for path in files.values():
        path.write_bytes(path.name.encode())

    def crash(observed: str) -> None:
        if point == observed:
            raise PowerCut(point)

    with pytest.raises(PowerCut):
        Publisher(engine, root, fault=crash).publish(operation_id, token, step_id, files)
    with Session(engine) as session:
        session.execute(delete(UnifiedPublication))
        session.commit()
    assert Publisher(engine, root).reconcile(processes_released=lambda operation: True) == [expected]
    with Session(engine) as session:
        publication = session.exec(select(UnifiedPublication)).one()
        assert publication.state == ('committed' if expected == 'J05' else 'blocked')


def test_unknown_publication_state_blocks_without_revoking_original_attempt(tmp_path: Path) -> None:
    from app.models_unified import UnifiedRuntime
    from app.services.task_operations import OperationConflict
    engine = database(tmp_path)
    operation_id, token, step_id = running(engine)
    root = tmp_path / 'artifacts'
    stage = root / '.unified/staging' / operation_id / '1'
    stage.mkdir(parents=True)
    files = {'video': stage / 'clip.mp4', 'subtitles': stage / 'clip.srt'}
    for path in files.values():
        path.write_bytes(path.name.encode())
    identifier = Publisher(engine, root).publish(operation_id, token, step_id, files)
    with Session(engine) as session:
        publication = session.get(UnifiedPublication, identifier)
        publication.state = 'future-state'
        session.add(publication)
        session.commit()
    with pytest.raises(OperationConflict, match='unsupported'):
        Publisher(engine, root).reconcile(processes_released=lambda operation: True)
    with Session(engine) as session:
        assert session.get(UnifiedRuntime, 1).recovering is True
        assert session.get(UnifiedOperation, operation_id).execution_token == token
        assert session.get(UnifiedOperation, operation_id).state == 'running'
