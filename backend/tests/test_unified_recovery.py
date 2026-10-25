from __future__ import annotations

import importlib
import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import pytest
from sqlmodel import Session

from app.arctime.subtitle_render import render_document_ass
from app.arctime.subtitle_style import SubtitleStyle, TextStyle
from app.arctime.subtitle_templates import TemplateStore
from app.services.global_documents import GlobalDocuments
from app.services.task_artifacts import resolve_workstation
from app.services.task_documents import Documents
from app.services.task_operations import bind_task, runtime
from test_unified_artifacts import frozen_source
from test_unified_operations import database


def scripts(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2] / 'scripts'))
    return importlib.import_module('recovery_storage')


def release_fixture(root: Path) -> None:
    if sys.platform == 'darwin':
        for path in [root, *root.rglob('*')]:
            if path.exists():
                os.chflags(path, 0)
                path.chmod(0o700 if path.is_dir() else 0o600)


def recovery_fixture(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from app.arctime import subtitle_encoding
    monkeypatch.setattr(subtitle_encoding, 'video_metadata', lambda path: (1280, 720, 30.))
    db_root = tmp_path / 'db'
    db_root.mkdir()
    engine = database(db_root)
    roots = {name: tmp_path / name for name in ['task_root', 'settings_root', 'global_package_root', 'migration_registry', 'guard_root']}
    roots['unified_db'] = db_root
    for path in roots.values():
        path.mkdir(exist_ok=True)
    credentials = tmp_path / 'private-authorization'
    credentials.mkdir()
    (credentials / 'config.json').write_text('SECRET_CANARY_FAKE_AUTHORIZATION')
    (roots['guard_root'] / '.heavy.lock').touch()
    source = frozen_source(tmp_path)
    for reference in source.files:
        target = roots['task_root'] / reference.path
        target.parent.mkdir(exist_ok=True, parents=True)
        target.write_bytes(source.checked(reference).read_bytes())
    source = source.model_copy(update={'root': roots['task_root']})
    context = resolve_workstation(source)
    with Session(engine) as session:
        binding = bind_task(session, source.source_instance_id, source.legacy_id, 'generation', origin='native')
        binding.context_json = source.model_dump_json()
        session.add(binding)
        state = runtime(session)
        state.root_roles_json = json.dumps({'task': str(roots['task_root']), 'settings': str(roots['settings_root']),
            'guard': str(roots['guard_root']), 'credential': str(credentials)})
        session.add(state)
        session.commit()
    db_path = Path(engine.url.database)
    with sqlite3.connect(db_path) as connection:
        connection.execute('CREATE TABLE alembic_version(version_num TEXT NOT NULL)')
        connection.execute("INSERT INTO alembic_version VALUES ('20261022_01')")
    base = context.document(SubtitleStyle())
    saved = Documents(engine, roots['task_root']).save(source.task_id, base.model_copy(update={
        'style': SubtitleStyle(original=TextStyle(outline_layers=[{'color': '#00FF00', 'width': 6}])),
        'cues': [base.cues[0].model_copy(update={'text': '最后保存的原文', 'translation': '最後に保存した訳文'})]}), base=base)
    globals = GlobalDocuments(engine, roots['settings_root'])
    templates = TemplateStore(roots['settings_root'], documents=globals)
    style = templates.save_style('新版模板', SubtitleStyle())
    templates.save_style('只有全局修改', style.style, template_id=style.id, expected_revision=1)
    from app.services.task_operations import enqueue_operation, set_admissions
    from app.services.task_execution import Executor
    with Session(engine) as session:
        enqueue_operation(session, source.task_id, 'export', {'input': {'kind': 'control-export'}, 'config': {}})
        set_admissions(session, paused=False)
        session.commit()
    def publish_control(execution):
        result = execution.staging('control') / 'subtitle.srt'
        result.write_text('1\n00:00:00,000 --> 00:00:01,000\n已登记导出\n')
        execution.publish('reader-control-export', {'subtitles': result})
    Executor(engine, roots['task_root'], roots['guard_root']).iteration(publish_control)
    with Session(engine) as session:
        set_admissions(session, paused=True)
        session.commit()
    engine.dispose()
    recipe = {'version': 1, 'root_group_id': str(uuid4()), 'roots': {name: str(path) for name, path in roots.items()},
        'credential_root': str(credentials), 'locks': [str(roots['guard_root'] / '.heavy.lock')], 'database': db_path.name}
    return recipe, roots, saved


def test_independent_reader_exports_latest_document_and_global_only_writes_without_candidate(tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch) -> None:
    storage = scripts(monkeypatch)
    builder = importlib.import_module('build_unified_recovery')
    recipe, roots, saved = recovery_fixture(tmp_path, monkeypatch)
    bundle = builder.freeze(tmp_path / 'frozen-reader')
    recipe['reader_bundle'] = {'path': str(bundle), 'sha256': storage.sha(bundle)}
    try:
        manifest = storage.snapshot(recipe, tmp_path / 'snapshot', install_seal=True)
        output = tmp_path / 'exports'
        program = '''import runpy,sys
def guard(event,args):
    if event == 'import' and (args[0] == 'app' or args[0].startswith('app.') or args[0] in ('torch','whisperx')):
        raise RuntimeError('candidate or model import prohibited')
    if event in ('socket.connect','subprocess.Popen'):
        raise RuntimeError('network or subprocess prohibited')
    if event == 'open' and isinstance(args[0],str) and 'private-authorization' in args[0]:
        raise RuntimeError('credential body access prohibited')
sys.addaudithook(guard)
sys.argv=sys.argv[1:]
runpy.run_path(sys.argv[0],run_name='__main__')
'''
        result = subprocess.run([str(bundle.parent / 'runtime/bin/python3.11'), '-I', '-S', '-B', '-c', program,
            str(bundle.parent / 'reader.py'), '--mode', 'read-only', '--manifest', str(manifest), '--output-root', str(output),
            '--bundle', str(bundle)], capture_output=True, text=True, timeout=90)
        assert result.returncode == 0, result.stderr + result.stdout
        report = json.loads((output / 'verification.json').read_bytes())
        assert report['complete'] is True and report['documents'] == 1
        index = json.loads((output / 'task-index.json').read_bytes())
        directory = output / 'tasks' / index[0]['task_id']
        assert json.loads((directory / 'document.json').read_bytes()) == saved.model_dump(mode='json')
        assert '最后保存的原文\n最後に保存した訳文' in (directory / 'subtitles.srt').read_text()
        assert (directory / 'subtitles.ass').read_text() == render_document_ass(saved, True)
        styles = list((output / 'settings/templates/styles').glob('*.json'))
        assert len(styles) == 1 and json.loads(styles[0].read_bytes())['name'] == '只有全局修改'
        assert all(b'SECRET_CANARY_FAKE_AUTHORIZATION' not in path.read_bytes() for path in (tmp_path / 'snapshot').rglob('*') if path.is_file())
        publications = json.loads((output / 'publication-index.json').read_bytes())
        assert len(publications) == 1 and publications[0]['task_id'] == index[0]['task_id']
        member = publications[0]['outputs'][0]
        assert '已登记导出' in (output / 'registered' / member['target']).read_text()
        before = storage.inventory(tmp_path / 'snapshot')
        reader = importlib.import_module('unified_recovery')
        with pytest.raises(storage.RecoveryError, match='overlap'):
            reader.read_only(manifest, roots['task_root'] / 'forbidden', bundle)
        assert storage.inventory(tmp_path / 'snapshot') == before
    finally:
        release_fixture(tmp_path)


def test_snapshot_failure_keeps_originals_and_never_advertises_complete(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    storage = scripts(monkeypatch)
    recipe, roots, saved = recovery_fixture(tmp_path, monkeypatch)
    builder = importlib.import_module('build_unified_recovery')
    bundle = builder.freeze(tmp_path / 'frozen-reader')
    recipe['reader_bundle'] = {'path': str(bundle), 'sha256': storage.sha(bundle)}
    before = {name: storage.inventory(path) for name, path in roots.items()}
    original = storage.shutil.copyfile

    def fail(source, target):
        if 'snapshot/roots' in str(target):
            raise OSError('injected ENOSPC')
        return original(source, target)

    monkeypatch.setattr(storage.shutil, 'copyfile', fail)
    try:
        with pytest.raises(OSError):
            storage.snapshot(recipe, tmp_path / 'snapshot', install_seal=True)
        assert not (tmp_path / 'snapshot/complete.json').exists()
        assert {name: storage.inventory(path) for name, path in roots.items()} == before
    finally:
        release_fixture(tmp_path)


@pytest.mark.skipif(sys.platform != 'darwin', reason='Persistent immutable profile')
def test_interrupted_snapshot_seal_resumes_from_original_modes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    storage = scripts(monkeypatch)
    protection = importlib.import_module('recovery_protection')
    root = tmp_path / 'source'
    root.mkdir(mode=0o750)
    (root / 'first').write_text('one')
    (root / 'second').write_text('two')
    original = {str(path): (path.stat().st_mode & 0o777, path.stat().st_flags) for path in [root, *root.rglob('*')]}
    change_flags = os.chflags
    calls = 0
    def interrupted(path, flags):
        nonlocal calls
        change_flags(path, flags)
        calls += 1
        if calls == 1:
            raise OSError('injected process death after first protection member')
    monkeypatch.setattr(protection.os, 'chflags', interrupted)
    journal = tmp_path / 'original-protection.json'
    try:
        with pytest.raises(OSError, match='injected'):
            protection.seal([root], journal, install=True)
        monkeypatch.setattr(protection.os, 'chflags', change_flags)
        with pytest.raises(storage.RecoveryError, match='original pinned journal'):
            protection.seal([root], tmp_path / 'unsafe-new.json', install=True)
        copied = tmp_path / 'resumed-protection.json'
        protection.seal([root], copied, install=True, resume=journal)
        assert copied.read_bytes() == journal.read_bytes()
        entries = json.loads(copied.read_bytes())['entries']
        assert {item['path']: (item['mode'], item['flags']) for item in entries} == original
        assert all(path.stat().st_flags & __import__('stat').UF_IMMUTABLE for path in [root, *root.rglob('*')])
    finally:
        monkeypatch.setattr(protection.os, 'chflags', change_flags)
        release_fixture(root)


