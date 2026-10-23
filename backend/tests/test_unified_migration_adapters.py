from pathlib import Path
from uuid import uuid4
import subprocess

from sqlmodel import Session, select

from app.arctime.subtitle_templates import TemplateStore
from app.arctime.media import tool_path
from app.models_migration import MigrationMember
from app.services.migration_companion import prepare_companion
from app.services.migration_snapshot import SourceRoots, read_candidate
from app.services.migration_workstation import prepare_workstation
from app.services.task_migration import Migrator
from test_unified_operations import database
from unification_fixtures import _run
from unified_edit_fixture import make_editor_fixture


def media_fixture(root: Path) -> Path:
    root.mkdir()
    subprocess.run([tool_path('ffmpeg'), '-v', 'error', '-nostdin', '-n', '-f', 'lavfi', '-i',
        'color=black:size=1280x720:rate=30:duration=6', '-c:v', 'libx264', '-preset', 'ultrafast',
        str(root / 'source.mp4')], check=True, capture_output=True, timeout=30)
    return root


def test_companion_adapter_preserves_bilingual_words_and_records_fingerprint_compatibility(tmp_path: Path) -> None:
    source_id = uuid4()
    media = media_fixture(tmp_path / 'media')
    tasks, settings = tmp_path / 'old-tasks', tmp_path / 'old-settings'
    _run(tasks / 'abcdef123456', media / 'source.mp4')
    TemplateStore(settings)
    roots = SourceRoots(tasks=tasks, settings=settings)
    migration = Migrator(database(tmp_path), tmp_path / 'new-tasks', tmp_path / 'new-settings')
    migration.register(source_id, roots, origin='companion')
    batch = prepare_companion(migration, source_id, roots, legacy_id='abcdef123456')
    migration.verify(batch)
    with Session(migration.engine) as session:
        member = session.exec(select(MigrationMember)).one()
        candidate = read_candidate(migration.root, member.candidate_path, member.candidate_sha256)
    assert candidate.document.cues[0].translation == '今天天气很好。'
    assert candidate.metadata.tags == ('fixture',)
    assert candidate.metadata.archived_at is not None
    assert candidate.history['legacy_metadata']['archived'] is True
    assert candidate.history['legacy_source_fingerprint']
    assert candidate.context.checked(candidate.context.transcript).read_text().find('0.95') >= 0


def test_workstation_adapter_reads_independent_sqlite_copy_and_preserves_source_bytes(tmp_path: Path) -> None:
    fixture = make_editor_fixture(tmp_path / 'source', media_fixture(tmp_path / 'media'))
    from app.arctime.subtitle_document import DocumentStore
    from app.arctime.subtitle_style import SubtitleStyle
    directory = fixture.editor / fixture.artifacts.source.task_id
    directory.mkdir()
    documents = DocumentStore(artifacts=lambda directory: fixture.artifacts)
    original = documents.load(directory, SubtitleStyle())
    saved = documents.save(directory, original.model_copy(update={'cues': [original.cues[0].model_copy(update={'text': '已保存的工作站改稿'})]}))
    roots = SourceRoots(tasks=fixture.root / 'old-data/tasks', settings=fixture.editor, database=fixture.root / 'old-data')
    migration = Migrator(database(tmp_path), tmp_path / 'new-tasks', tmp_path / 'new-settings')
    source_id = fixture.artifacts.source.source_instance_id
    migration.register(source_id, roots, origin='workstation')
    before = fixture.current_source_hashes()
    batch = prepare_workstation(migration, source_id, roots, database_name='tasks.sqlite3', legacy_id=fixture.artifacts.source.legacy_id)
    migration.verify(batch)
    assert fixture.current_source_hashes() == before
    with Session(migration.engine) as session:
        member = session.exec(select(MigrationMember)).one()
        candidate = read_candidate(migration.root, member.candidate_path, member.candidate_sha256)
    assert candidate.metadata.created_at is not None and candidate.document.cues[0].translation == '統一テスト字幕'
    assert candidate.document.revision == saved.revision and candidate.document.cues[0].text == '已保存的工作站改稿'


def test_registered_external_media_root_does_not_depend_on_current_host_catalog(tmp_path: Path) -> None:
    import json
    from app.models import Artifact
    from sqlmodel import create_engine
    fixture = make_editor_fixture(tmp_path / 'source', media_fixture(tmp_path / 'media'))
    subprocess.run([tool_path('ffmpeg'), '-v', 'error', '-nostdin', '-y', '-f', 'lavfi', '-i',
        'color=blue:size=1280x720:rate=30:duration=6', '-c:v', 'libx264', '-preset', 'ultrafast',
        str(tmp_path / 'media/source.mp4')], check=True, capture_output=True, timeout=30)
    engine = create_engine('sqlite:///' + str(fixture.root / 'old-data/tasks.sqlite3'))
    with Session(engine) as session:
        source = session.exec(select(Artifact).where(Artifact.kind == 'source_video')).one()
        source.metadata_json = json.dumps({'import_mode': 'reference', 'root_id': 'historical-only-root', 'relative_path': 'source.mp4'})
        session.add(source)
        session.commit()
    engine.dispose()
    roots = SourceRoots(tasks=fixture.root / 'old-data/tasks', settings=fixture.editor,
        database=fixture.root / 'old-data', media=tmp_path / 'media')
    before = fixture.current_source_hashes()
    migration = Migrator(database(tmp_path), tmp_path / 'new-tasks', tmp_path / 'new-settings')
    source_id = fixture.artifacts.source.source_instance_id
    migration.register(source_id, roots, origin='workstation')
    batch = prepare_workstation(migration, source_id, roots, database_name='tasks.sqlite3', legacy_id=fixture.artifacts.source.legacy_id)
    migration.verify(batch)
    assert fixture.current_source_hashes() == before
    with Session(migration.engine) as session:
        member = session.exec(select(MigrationMember)).one()
        candidate = read_candidate(migration.root, member.candidate_path, member.candidate_sha256)
    assert any(member.role == 'media' for member in candidate.files)
    assert candidate.context.video.sha256 != fixture.artifacts.source.video.sha256
    assert candidate.context.checked(candidate.context.video).read_bytes() == (tmp_path / 'media/source.mp4').read_bytes()
    assert len(candidate.history['artifact']) == 5


def test_explicit_collection_relocation_resolves_old_registered_paths_without_changing_identity(tmp_path: Path) -> None:
    import shutil
    fixture = make_editor_fixture(tmp_path / 'source', media_fixture(tmp_path / 'media'))
    roots = SourceRoots(tasks=fixture.root / 'old-data/tasks', settings=fixture.editor, database=fixture.root / 'old-data')
    migration = Migrator(database(tmp_path), tmp_path / 'new-tasks', tmp_path / 'new-settings')
    source_id = fixture.artifacts.source.source_instance_id
    migration.register(source_id, roots, origin='workstation')
    from app.services.migration_snapshot import generation, inventory
    checksum = generation(inventory(roots), roots.public_runtime)
    moved = tmp_path / 'relocated-collection'
    shutil.copytree(fixture.root, moved)
    relocated = roots.model_copy(update={'tasks': moved / 'old-data/tasks', 'settings': moved / 'editor', 'database': moved / 'old-data'})
    migration.register(source_id, relocated, origin='workstation', mode='relocate', expected_generation=checksum)
    batch = prepare_workstation(migration, source_id, relocated, database_name='tasks.sqlite3', legacy_id=fixture.artifacts.source.legacy_id)
    migration.verify(batch)
    with Session(migration.engine) as session:
        member = session.exec(select(MigrationMember)).one()
        candidate = read_candidate(migration.root, member.candidate_path, member.candidate_sha256)
        assert member.task_id == fixture.artifacts.source.task_id and candidate.source_id == source_id
    assert fixture.current_source_hashes() == fixture.source_hashes
