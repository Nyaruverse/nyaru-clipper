from __future__ import annotations

import json
import shutil
import sqlite3
import tempfile
from pathlib import Path
from uuid import UUID

from sqlmodel import Session, create_engine, select

from app.arctime.subtitle_style import SubtitleStyle
from app.arctime.subtitle_document import SubtitleDocument, validate_source
from app.models import Artifact, PipelineRun, QueueEntry, StageRun, Task, TaskExecutionControl, TaskJob, TaskStage, TaskTagLink
from app.models_migration import MigrationSource
from app.services.migration_snapshot import SourceRoots, TaskMetadata, inventory
from app.services.task_migration import Migrator
from app.services.task_operations import OperationConflict
from app.services.unified_files import checked_path
from app.services.workstation_artifacts import snapshot_workstation


def prepare_workstation(migration: Migrator, source_id: UUID, roots: SourceRoots, *, database_name: str,
                        legacy_id: str, batch_id: str | None = None) -> str:
    if roots.database is None or Path(database_name).name != database_name or Path(legacy_id).name != legacy_id:
        raise OperationConflict('explicit registered database and task identity required')
    before = inventory(roots)
    with Session(migration.engine) as registry:
        source_record = registry.get(MigrationSource, str(source_id))
        if source_record is None or source_record.roots_json != roots.model_dump_json():
            raise OperationConflict('source paths differ from registered relocation')
        aliases = {Path(old): Path(new) for old, new in json.loads(source_record.path_aliases_json).items()}
    database = checked_path(roots.database, database_name)
    migration.root.mkdir(mode=0o700, parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.migration-db-', dir=migration.root) as temporary:
        copied = Path(temporary) / database_name
        for suffix in ('', '-wal', '-shm'):
            source = database.with_name(database_name + suffix)
            if source.exists():
                shutil.copyfile(source, copied.with_name(database_name + suffix))
        engine = create_engine('sqlite://', creator=lambda: sqlite3.connect(copied.as_uri() + '?mode=ro', uri=True))
        try:
            with Session(engine) as session:
                task = session.get(Task, legacy_id)
                if task is None:
                    raise OperationConflict('registered workstation task missing')
                context = snapshot_workstation(session, task_id=legacy_id, root=checked_path(roots.tasks, legacy_id),
                    source_instance_id=source_id, path_aliases=aliases, media_root=roots.media)
                base = context.document(SubtitleStyle())
                documents = [path for directory in (roots.tasks / legacy_id, roots.settings / context.source.task_id,
                    roots.settings / legacy_id) if (path := checked_path(directory, 'subtitle-document.json')).is_file()]
                if len({path.read_bytes() for path in documents}) > 1:
                    raise OperationConflict('multiple saved editor documents differ; explicit resolution required')
                document = SubtitleDocument.model_validate_json(documents[0].read_bytes()) if documents else base
                validate_source(document, base)
                metadata = TaskMetadata.model_validate({**task.model_dump(include=set(TaskMetadata.model_fields) - {'tags'}),
                    'tags': tuple(session.exec(select(TaskTagLink.tag_name).where(TaskTagLink.task_id == legacy_id)).all())})
                tables = (TaskStage, TaskJob, TaskExecutionControl, QueueEntry, PipelineRun, Artifact)
                history = {table.__tablename__: [row.model_dump(mode='json') for row in session.exec(select(table).where(table.task_id == legacy_id)).all()]
                    for table in tables}
                runs = [row['id'] for row in history['pipelinerun']]
                history['stagerun'] = [row.model_dump(mode='json') for row in session.exec(select(StageRun).where(StageRun.run_id.in_(runs))).all()]
                if inventory(roots) != before:
                    raise OperationConflict('source database/files changed during preparation')
                return migration.prepare(source_id, context, document, metadata=metadata,
                    history=history, batch_id=batch_id)
        finally:
            engine.dispose()


def require_workstation_stopped(roots: SourceRoots, staging: Path) -> None:
    if roots.database is None:
        raise OperationConflict('workstation database protection domain missing')
    database_name = roots.database_name
    if Path(database_name).name != database_name:
        raise OperationConflict('unsafe historical database filename')
    database = checked_path(roots.database, database_name)
    with tempfile.TemporaryDirectory(prefix='.migration-proof-', dir=staging) as temporary:
        copied = Path(temporary) / database_name
        for suffix in ('', '-wal', '-shm'):
            source = database.with_name(database_name + suffix)
            if source.exists():
                shutil.copyfile(source, copied.with_name(database_name + suffix))
        with sqlite3.connect(copied) as connection:
            if connection.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                raise OperationConflict('historical SQLite set is inconsistent')
            if connection.execute("SELECT 1 FROM taskjob WHERE status='running' LIMIT 1").fetchone():
                raise OperationConflict('old workstation job is still running')
            if connection.execute('SELECT 1 FROM taskexecutioncontrol WHERE active_process_group_id IS NOT NULL LIMIT 1').fetchone():
                raise OperationConflict('old workstation process ownership is not released')
            if connection.execute("SELECT 1 FROM queueentry WHERE state='running' LIMIT 1").fetchone():
                raise OperationConflict('old workstation queue still owns a running task')
