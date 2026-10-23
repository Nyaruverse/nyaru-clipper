from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from uuid import uuid4

import pytest
from sqlmodel import Session, select

from app.arctime.subtitle_document import SubtitleDocument
from app.arctime.subtitle_style import SubtitleStyle
from app.arctime.subtitle_templates import TemplateStore
from app.models import Task, TaskTagLink, utc_now
from app.models_migration import MigrationGroup, MigrationMember
from app.models_unified import DocumentVersion, TaskBinding
from app.services.global_documents import GlobalDocuments
from app.services.migration_groups import rollback_category, withdraw_group
from app.services.migration_snapshot import SourceRoots, TaskMetadata
from app.services.source_seal import Supervisor
from app.services.task_artifacts import ArtifactFile, WorkstationArtifacts, resolve_workstation
from app.services.task_documents import Documents
from app.services.task_migration import Migrator
from app.services.task_operations import OperationConflict
from app.services.unified_files import file_sha256
from app.services.public_runtime_settings import PUBLIC_FIELDS, PublicRuntimeSettings
from app.arctime.companion_llm import PublicPreferences
from app.settings import Settings
from test_unified_operations import database


def source_fixture(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    source_id = uuid4()
    old = tmp_path / 'old'
    tasks, settings = old / 'tasks', old / 'settings'
    directory = tasks / 'abcdef123456'
    directory.mkdir(parents=True)
    settings.mkdir()
    (old / '.gui.lock').touch()
    (directory / '.lock').touch()
    (directory / 'source.mp4').write_bytes(b'not-decoded-in-control-test')
    (directory / 'subtitles.srt').write_text('1\n00:00:01,000 --> 00:00:03,000\n原文\n')
    (directory / 'transcript.json').write_text(json.dumps({'segments': [{'id': '1', 'start_seconds': 1., 'end_seconds': 3., 'text': '原文',
        'words': [{'text': '原文', 'start_seconds': 1., 'end_seconds': 3., 'confidence': .95}]}]}))
    reference = lambda name: ArtifactFile(path=name, sha256=file_sha256(directory / name))
    source = WorkstationArtifacts(source_instance_id=source_id, legacy_id=directory.name, root=directory, duration=5.,
        video=reference('source.mp4'), transcript=reference('transcript.json'), subtitles=reference('subtitles.srt'), source_language='zh')
    monkeypatch.setattr('app.arctime.subtitle_encoding.video_metadata', lambda path: (1280, 720, 30.))
    context = resolve_workstation(source)
    document = context.document(SubtitleStyle()).model_copy(update={'revision': 7})
    document = document.model_copy(update={'cues': [document.cues[0].model_copy(update={'text': '已保存的编辑', 'translation': '保存済み'})]})
    store = TemplateStore(settings)
    project = store.save_project('工程', 'fixture.atpj', b'project-fixture-bytes')
    style = store.save_style('样式', SubtitleStyle(), project.id)
    store.save_studio_settings(store.load_studio_settings().model_copy(update={'default_template_id': style.id, 'language': 'zh'}))
    metadata = TaskMetadata(title='迁移标题', source_url='https://fixture.invalid/source', normalized_source_url='https://fixture.invalid/source',
        created_at=utc_now(), updated_at=utc_now(), tags=('字幕',), highlight_filtering_enabled=False)
    public = PublicRuntimeSettings(settings=Settings().model_dump(mode='json', include=PUBLIC_FIELDS),
        companion=PublicPreferences(deepseek_model='deepseek-v4-flash', llm_provider='deepseek', chatgpt_model=''),
        cpp_model=tmp_path / 'existing-model.bin', cpp_threads=6)
    return source_id, old, SourceRoots(tasks=tasks, settings=settings, public_runtime=public), context, document, metadata


@pytest.mark.skipif(sys.platform != 'darwin', reason='Actual persistent immutable seal profile')
def test_prepare_verify_activate_is_atomic_idempotent_and_preserves_edit_and_globals(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source_id, old, roots, context, document, metadata = source_fixture(tmp_path, monkeypatch)
    engine = database(tmp_path)
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2] / 'scripts'))
    from build_unified_recovery import freeze
    bundle = freeze(tmp_path / 'independent-recovery', legacy_helper=True)
    migration = Migrator(engine, tmp_path / 'new-tasks', tmp_path / 'new-settings',
        recovery_bundle=bundle, recovery_bundle_sha256=file_sha256(bundle))
    group_id = migration.register(source_id, roots, origin='companion')
    batch = migration.prepare(source_id, context, document, metadata=metadata, history={'failure': 'fixture_timeout'})
    assert migration.prepare(source_id, context, document, metadata=metadata, history={'failure': 'fixture_timeout'}) == batch
    with Session(engine) as session:
        assert session.get(TaskBinding, context.source.task_id).state == 'prepared'
    migration.verify(batch)
    credentials = tmp_path / 'credentials'
    credentials.mkdir()
    credentials.joinpath('secret-fixture').write_bytes(b'synthetic-auth-keep-out')
    locks = (old / '.gui.lock', roots.tasks / 'abcdef123456/.lock')
    try:
        with Supervisor((old,), tmp_path / 'guard', credentials, group_id, locks) as supervisor:
            supervisor.seal()
            migration.activate(batch, supervisor)
            migration.activate(batch, supervisor)
            with Session(engine) as session:
                binding = session.get(TaskBinding, context.source.task_id)
                assert binding.state == 'activated'
                migrated = WorkstationArtifacts.model_validate_json(binding.context_json)
                assert migrated.root == migration.root and migrated.media_root is None
                assert resolve_workstation(migrated).cues[0].words[0].confidence == .95
                assert session.get(Task, binding.task_id).title == metadata.title
                assert session.get(TaskTagLink, (binding.task_id, '字幕')) is not None
                assert rollback_category(session, group_id) == 'R1'
            saved = Documents(engine, migration.root).load(migrated.task_id, resolve_workstation(migrated).document(SubtitleStyle()))
            assert saved.revision == 7 and saved.cues[0].text == '已保存的编辑'
            store = TemplateStore(migration.settings_root, documents=GlobalDocuments(engine, migration.settings_root))
            assert len(store.list_projects()) == 1 and len(store.list_styles()) == 4
            assert store.load_studio_settings().language == 'zh'
            assert store.load_studio_settings().default_template_id == store.list_styles()[-1].id
            globals = GlobalDocuments(engine, migration.settings_root)
            imported = PublicRuntimeSettings.model_validate_json(globals.read('runtime/settings.json'))
            assert imported == roots.public_runtime
            assert globals.read('llm/preferences.json') == imported.companion.model_dump_json().encode()
            assert not any(b'synthetic-auth-keep-out' in path.read_bytes() for path in migration.root.rglob('*') if path.is_file())
            migration.thaw(group_id, supervisor)
            receipt = json.loads((supervisor.guard_root / 'thaw-allowed.json').read_bytes())
            assert receipt['category'] == 'R1' and len(receipt['members']) == 1
            assert receipt['permission_profile'] == 'darwin-immutable' and receipt['seal_sha256']
            with Session(engine) as session:
                assert session.get(MigrationGroup, group_id).state == 'thawed'
        next_group = migration.register(source_id, roots, origin='companion')
        assert next_group != group_id
        next_batch = migration.prepare(source_id, context, document, metadata=metadata)
        migration.verify(next_batch)
        with Supervisor((old,), tmp_path / 'guard-next', credentials, next_group, locks) as supervisor:
            supervisor.seal()
            migration.activate(next_batch, supervisor)
            saved = Documents(engine, migration.root).load(migrated.task_id, resolve_workstation(migrated).document(SubtitleStyle()))
            assert saved.revision == 8 and saved.cues[0].text == '已保存的编辑'
            with Session(engine) as session:
                assert len(session.exec(select(DocumentVersion)).all()) == 2
                assert session.get(MigrationGroup, group_id).state == 'thawed'
                assert rollback_category(session, next_group) == 'R1'
            migration.thaw(next_group, supervisor)
    finally:
        for path in sorted([old, *old.rglob('*')], key=lambda path: len(path.parts)):
            os.chflags(path, 0)
            path.chmod(0o700 if path.is_dir() else 0o600)


def test_changed_source_before_activation_preserves_old_candidates_and_blocks_bad_instance(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source_id, old, roots, context, document, metadata = source_fixture(tmp_path, monkeypatch)
    engine = database(tmp_path)
    migration = Migrator(engine, tmp_path / 'new-tasks', tmp_path / 'new-settings')
    migration.register(source_id, roots, origin='companion')
    first = migration.prepare(source_id, context, document, metadata=metadata)
    (roots.settings / 'note.txt').write_text('new generation')
    second = migration.prepare(source_id, context, document, metadata=metadata)
    assert second != first
    with Session(engine) as session:
        assert len(session.exec(select(MigrationMember)).all()) == 2
    with pytest.raises(OperationConflict, match='independent'):
        migration.register(uuid4(), roots, origin='companion')
    with pytest.raises(OperationConflict, match='source instance'):
        migration.prepare(uuid4(), context, document, metadata=metadata)


@pytest.mark.skipif(sys.platform != 'darwin', reason='Actual persistent immutable seal profile')
def test_editing_a_then_cancelling_b_cannot_thaw_the_shared_source(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import shutil
    from app.services.migration_groups import cancel_batch
    source_id, old, roots, context, document, metadata = source_fixture(tmp_path, monkeypatch)
    second_root = roots.tasks / '123456abcdef'
    shutil.copytree(context.source.root, second_root)
    second = resolve_workstation(context.source.model_copy(update={'legacy_id': second_root.name, 'root': second_root}))
    engine = database(tmp_path)
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2] / 'scripts'))
    from build_unified_recovery import freeze
    bundle = freeze(tmp_path / 'reader', legacy_helper=True)
    migration = Migrator(engine, tmp_path / 'new-tasks', tmp_path / 'new-settings',
        recovery_bundle=bundle, recovery_bundle_sha256=file_sha256(bundle))
    group = migration.register(source_id, roots, origin='companion')
    batch_a = migration.prepare(source_id, context, document, metadata=metadata)
    batch_b = migration.prepare(source_id, second, second.document(SubtitleStyle()), metadata=metadata)
    migration.verify(batch_a)
    credentials = tmp_path / 'credentials'
    credentials.mkdir()
    locks = (old / '.gui.lock', context.source.root / '.lock', second_root / '.lock')
    try:
        with Supervisor((old,), tmp_path / 'guard', credentials, group, locks) as supervisor:
            supervisor.seal()
            migration.activate(batch_a, supervisor)
            with Session(engine) as session:
                binding = session.get(TaskBinding, context.source.task_id)
                migrated = resolve_workstation(WorkstationArtifacts.model_validate_json(binding.context_json))
            documents = Documents(engine, migration.root)
            saved = documents.load(migrated.source.task_id, migrated.document(SubtitleStyle()))
            saved = documents.save(migrated.source.task_id, saved.model_copy(update={'cues': [saved.cues[0].model_copy(update={'text': 'A 的新编辑'})]}),
                base=migrated.document(SubtitleStyle()))
            with Session(engine) as session:
                cancel_batch(session, batch_b)
                session.commit()
            with pytest.raises(OperationConflict, match='R2'):
                migration.thaw(group, supervisor)
            assert supervisor.verify().root_group_id == group
            assert not (supervisor.guard_root / 'thaw-allowed.json').exists()
            assert documents.load(migrated.source.task_id, migrated.document(SubtitleStyle())) == saved
            with pytest.raises(PermissionError):
                (context.source.root / 'subtitles.srt').write_text('forbidden')
            with Session(engine) as session:
                assert session.get(TaskBinding, migrated.source.task_id).state == 'activated'
                assert rollback_category(session, group) == 'R2'
    finally:
        for path in [old, *old.rglob('*')]:
            os.chflags(path, 0)
            path.chmod(0o700 if path.is_dir() else 0o600)
