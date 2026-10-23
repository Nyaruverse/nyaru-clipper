from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path

import pytest
from sqlalchemy import inspect, text
from sqlmodel import Session, SQLModel, create_engine, select

from app.db_migrations import upgrade_database
from app.models import Artifact, Task, TaskStage
from app.models_unified import TaskBinding
from app.services.task_operations import runtime


def test_upgrade_of_independent_copy_preserves_legacy_rows_and_original_bytes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from alembic import command
    from alembic.config import Config
    original, candidate = tmp_path / 'old.sqlite3', tmp_path / 'candidate.sqlite3'
    config = Config(str(Path(__file__).resolve().parents[1] / 'alembic.ini'))
    config.set_main_option('sqlalchemy.url', f'sqlite:///{original}')
    command.upgrade(config, '20260714_01')
    engine = create_engine(f'sqlite:///{original}')
    unified_tables = {'unifiedruntime', 'taskbinding', 'unifiedoperation', 'operationattempt', 'operationprocess',
        'operationstep', 'unifiedpublication', 'documenthead', 'documentversion', 'globalhead', 'globalversion',
        'migrationgroup', 'migrationsource', 'migrationbatch', 'migrationmember', 'migrationdependency'}
    SQLModel.metadata.create_all(engine, tables=[table for table in SQLModel.metadata.sorted_tables if table.name not in unified_tables])
    with Session(engine) as session:
        session.add(Task(id='old-failed', source_url='https://example.invalid', normalized_source_url='https://example.invalid', status='failed', title='旧任务'))
        session.add(TaskStage(task_id='old-failed', name='translation', status='failed', failure_code='provider_timeout', attempts=2))
        session.add(Artifact(task_id='old-failed', stage_name='asr', kind='subtitle_srt', path='preserved.srt'))
        session.commit()
    engine.dispose()
    before = hashlib.sha256(original.read_bytes()).hexdigest()
    with sqlite3.connect(original) as source, sqlite3.connect(candidate) as destination:
        source.backup(destination)
    monkeypatch.setenv('APP_DATA_DIR', str(tmp_path / 'candidate-data'))
    upgrade_database(f'sqlite:///{candidate}')
    upgrade_database(f'sqlite:///{candidate}')
    engine = create_engine(f'sqlite:///{candidate}')
    inspector = inspect(engine)
    assert unified_tables.issubset(inspector.get_table_names())
    for table in unified_tables:
        assert {column['name'] for column in inspector.get_columns(table)} == set(SQLModel.metadata.tables[table].columns.keys())
    with Session(engine) as session:
        assert session.get(Task, 'old-failed').title == '旧任务'
        stage = session.exec(select(TaskStage)).one()
        assert (stage.status, stage.failure_code, stage.attempts) == ('failed', 'provider_timeout', 2)
        assert session.exec(select(Artifact)).one().path == 'preserved.srt'
        assert session.exec(select(TaskBinding)).all() == []
        assert runtime(session).paused is True
        assert session.execute(text('PRAGMA synchronous')).scalar_one() == 2
        assert session.execute(text('PRAGMA journal_mode')).scalar_one() in {'delete', 'wal'}
    assert hashlib.sha256(original.read_bytes()).hexdigest() == before


def test_failed_upgrade_preserves_source_and_candidate_copy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from alembic import command
    original, candidate = tmp_path / 'old.sqlite3', tmp_path / 'candidate.sqlite3'
    with sqlite3.connect(original) as connection:
        connection.execute('CREATE TABLE retained(value TEXT)')
        connection.execute("INSERT INTO retained VALUES ('old data')")
    candidate.write_bytes(original.read_bytes())
    before = original.read_bytes()
    monkeypatch.setenv('APP_DATA_DIR', str(tmp_path / 'candidate-data'))

    def fail(config, revision) -> None:
        raise OSError('injected upgrade failure')

    monkeypatch.setattr(command, 'upgrade', fail)
    with pytest.raises(OSError):
        upgrade_database(f'sqlite:///{candidate}')
    assert original.read_bytes() == before and candidate.is_file()
