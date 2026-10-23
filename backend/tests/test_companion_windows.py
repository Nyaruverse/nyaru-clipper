"""Platform boundaries needed by the native Windows companion."""
import os
import json
from pathlib import Path
import subprocess
import sys

import pytest

from app.arctime import media, workflow
from app.arctime.chatgpt_auth import ChatGPTAuth
from app.arctime.companion_manager import JobManager


def test_windows_legacy_execution_slot_excludes_and_releases(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from app.services import runtime_guard

    monkeypatch.setattr(runtime_guard, 'os', SimpleNamespace(name='nt'))
    with runtime_guard.execution_slot(tmp_path):
        with pytest.raises(runtime_guard.SlotBusy):
            with runtime_guard.execution_slot(tmp_path):
                pytest.fail('A second executor acquired the same slot')
    with runtime_guard.execution_slot(tmp_path):
        pass


def test_windows_legacy_execution_slot_preserves_body_errors(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from app.services import runtime_guard

    monkeypatch.setattr(runtime_guard, 'os', SimpleNamespace(name='nt'))
    with pytest.raises(RuntimeError, match='operation failed'):
        with runtime_guard.execution_slot(tmp_path):
            raise RuntimeError('operation failed')


@pytest.mark.parametrize('cleanup_fails', [False, True])
def test_windows_terminal_status_follows_owned_upload_cleanup(tmp_path, monkeypatch, cleanup_fails):
    from types import SimpleNamespace
    import threading
    from app.arctime import companion_manager

    monkeypatch.setattr(companion_manager, 'os', SimpleNamespace(name='nt'))
    monkeypatch.setattr(media, 'json_io_lock', threading.RLock(), raising=False)
    job_id = 'abcdef123456'
    (tmp_path / job_id).mkdir()
    upload_path = tmp_path / '.saozi-upload-test'
    upload_path.write_bytes(b'fixture')
    with upload_path.open('rb') as stream:
        upload = workflow.OwnedUpload.from_descriptor(upload_path, tmp_path, stream.fileno())
    manager = JobManager(tmp_path, tmp_path / 'unused-model.bin', 4)
    manager.active = {'id': job_id, 'state': 'preparing', 'message': 'test'}
    monkeypatch.setattr(workflow, 'resume_run', lambda *args, **kwargs: {'completed_clips': [{}]})
    original_write = media.write_json
    terminal_writes = []

    def observe(path, record):
        if record.get('state') in {'completed', 'failed'}:
            terminal_writes.append((record['state'], upload_path.exists()))
        original_write(path, record)

    def denied_cleanup(self):
        raise PermissionError('upload remains busy')

    monkeypatch.setattr(media, 'write_json', observe)
    if cleanup_fails:
        monkeypatch.setattr(workflow.OwnedUpload, 'cleanup', denied_cleanup)
    try:
        manager.run(job_id, None, owned_upload=upload)
        expected = [('failed', True)] if cleanup_fails else [('completed', False)]
        assert terminal_writes == expected
        assert manager.active is None
    finally:
        manager.executor.shutdown()
        manager.chatgpt.close()


def test_job_lock_excludes_another_process_and_releases(tmp_path):
    lock = tmp_path / 'companion.lock'
    code = (
        'from pathlib import Path; from app.arctime.workflow import exclusive_lock; '
        f'\nwith exclusive_lock(Path({str(lock)!r})): pass'
    )
    def attempt():
        return subprocess.run([sys.executable, '-X', 'utf8', '-c', code],
                              cwd=Path(__file__).resolve().parents[1],
                              capture_output=True, text=True, encoding='utf-8')

    with workflow.exclusive_lock(lock):
        blocked = attempt()
        assert blocked.returncode != 0
        assert 'busy in another companion process' in blocked.stderr
    released = attempt()
    assert released.returncode == 0, released.stderr


@pytest.mark.skipif(os.name != 'nt', reason='Windows credential protection boundary')
def test_windows_chatgpt_is_unavailable_without_creating_credentials(tmp_path):
    auth = ChatGPTAuth(tmp_path)
    try:
        status = auth.status()
        assert status['connected'] is False
        assert 'unavailable on Windows' in status['error']
        assert not (tmp_path / '.chatgpt').exists()
    finally:
        auth.close()


@pytest.mark.skipif(os.name != 'nt', reason='Windows rename sharing semantics')
def test_json_publication_recovers_from_a_temporarily_busy_target(tmp_path, monkeypatch):
    path = tmp_path / 'job.json'
    media.write_json(path, {'state': 'transcribing'})
    replace = os.replace
    calls = []

    def temporarily_busy(source, target):
        calls.append(target)
        if len(calls) == 1:
            assert json.loads(path.read_text()) == {'state': 'transcribing'}
            raise PermissionError('target is held by a Windows reader')
        return replace(source, target)

    monkeypatch.setattr(media.os, 'replace', temporarily_busy)
    media.write_json(path, {'state': 'completed'})
    assert json.loads(path.read_text()) == {'state': 'completed'}


@pytest.mark.skipif(os.name != 'nt', reason='Windows rename sharing semantics')
def test_json_publication_preserves_old_record_when_target_remains_busy(tmp_path, monkeypatch):
    path = tmp_path / 'job.json'
    media.write_json(path, {'state': 'transcribing'})

    def denied(source, target):
        raise PermissionError('target remains inaccessible')

    monkeypatch.setattr(media.os, 'replace', denied)
    with pytest.raises(PermissionError):
        media.write_json(path, {'state': 'completed'})
    assert json.loads(path.read_text()) == {'state': 'transcribing'}
    assert list(tmp_path.iterdir()) == [path]


@pytest.mark.parametrize('persistent', [False, True])
def test_status_write_failure_always_releases_active_job(tmp_path, monkeypatch, persistent):
    job_id = 'abcdef123456'
    (tmp_path / job_id).mkdir()
    manager = JobManager(tmp_path, tmp_path / 'unused-model.bin', 4)
    manager.active = {'id': job_id, 'state': 'preparing', 'message': 'test'}
    monkeypatch.setattr(workflow, 'resume_run', lambda *args, **kwargs: {'completed_clips': [{}]})
    original_write = media.write_json

    def write(path, record):
        if persistent or record.get('state') == 'completed':
            raise PermissionError('status file is inaccessible')
        original_write(path, record)

    monkeypatch.setattr(media, 'write_json', write)
    try:
        if persistent:
            with pytest.raises(PermissionError):
                manager.run(job_id, None)
        else:
            manager.run(job_id, None)
        assert manager.active is None
        assert manager.last['state'] == 'failed'
    finally:
        manager.executor.shutdown()
        manager.chatgpt.close()
