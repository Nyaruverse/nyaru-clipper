from pathlib import Path
from uuid import uuid4

import pytest
from sqlmodel import Session, select

from app.models_migration import MigrationBatch, MigrationGroup, MigrationSource
from app.models_unified import TaskBinding
from app.services.migration_groups import create_group, rollback_category, withdraw_group, cancel_batch
from app.services.task_operations import OperationConflict, bind_task, runtime, set_admissions
from test_unified_operations import database


def test_cross_batch_cancel_never_hides_activation_or_new_writes(tmp_path: Path) -> None:
    engine = database(tmp_path)
    with Session(engine) as session:
        group = create_group(session)
        source = MigrationSource(id=str(uuid4()), group_id=group.id, origin='companion', roots_json='{}')
        session.add(source)
        first = MigrationBatch(id=uuid4().hex, group_id=group.id, source_id=source.id, state='activated')
        second = MigrationBatch(id=uuid4().hex, group_id=group.id, source_id=source.id)
        session.add_all([first, second])
        binding = bind_task(session, uuid4(), 'old-a', 'generation', origin='companion')
        binding.state, binding.root_group_id = 'activated', group.id
        group.ever_activated = True
        session.add_all([binding, group])
        assert rollback_category(session, group.id) == 'R1'
        session.commit()
        set_admissions(session, paused=False)
        set_admissions(session, paused=True)
        session.commit()
        assert cancel_batch(session, second.id).state == 'cancelled'
        assert rollback_category(session, group.id) == 'R2'
        with pytest.raises(OperationConflict, match='R2'):
            withdraw_group(session, group.id)
        assert session.get(TaskBinding, binding.task_id).state == 'activated'
        group_id, first_id = group.id, first.id
        session.commit()
    with Session(engine) as session:
        assert rollback_category(session, group_id) == 'R2'
        assert session.exec(select(MigrationBatch).where(MigrationBatch.id == first_id)).one().state == 'activated'


def test_r0_and_r1_require_whole_group_withdrawal_and_remember_history(tmp_path: Path) -> None:
    engine = database(tmp_path)
    with Session(engine) as session:
        group = create_group(session)
        assert rollback_category(session, group.id) == 'R0'
        group.ever_activated = True
        session.add(group)
        assert rollback_category(session, group.id) == 'R1'
        runtime(session).paused = False
        with pytest.raises(OperationConflict, match='paused'):
            withdraw_group(session, group.id)
        runtime(session).paused = True
        receipt = withdraw_group(session, group.id)
        assert receipt['category'] == 'R1' and receipt['group_id'] == group.id
        assert session.get(MigrationGroup, group.id).ever_activated is True
        assert rollback_category(session, group.id) == 'R1'
        session.commit()
