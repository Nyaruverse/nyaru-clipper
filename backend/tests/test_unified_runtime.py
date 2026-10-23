from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.arctime.gui import create_app
from app.arctime.unified_host import NativeHost
from app.models_unified import UnifiedOperation
from app.services.task_operations import OperationConflict
from app.services.task_operations import set_admissions
from app.services.unified_runtime import initialize, open_runtime


def test_cli_queue_changes_survive_an_independent_reopen(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    from app.arctime.unified_cli import main
    model = tmp_path / 'model.bin'
    model.write_bytes(b'no inference')
    manifest = initialize(tmp_path / 'candidate', tmp_path / 'credentials', model)
    assert main(['start', '--runtime', str(manifest)]) == 0
    host = open_runtime(manifest)
    from app.models_unified import UnifiedRuntime
    with Session(host.engine) as session:
        assert session.get(UnifiedRuntime, 1).paused is False
    host.engine.dispose()
    assert main(['pause', '--runtime', str(manifest)]) == 0
    host = open_runtime(manifest)
    with Session(host.engine) as session:
        assert session.get(UnifiedRuntime, 1).paused is True
    host.engine.dispose()


def test_lan_binding_preserves_same_origin_and_rejects_public_or_wildcard_hosts(tmp_path: Path) -> None:
    from app.services.host_binding import private_host
    for address in ('0.0.0.0', '8.8.8.8', '169.254.1.2'):
        with pytest.raises(OperationConflict):
            private_host(address)
    assert private_host('192.168.1.10') == '192.168.1.10'
    model = tmp_path / 'model.bin'
    model.write_bytes(b'no inference')
    host = open_runtime(initialize(tmp_path / 'candidate', tmp_path / 'credentials', model))
    with TestClient(create_app(host.root, model=model, host=host, bind_host='192.168.1.10'), base_url='http://192.168.1.10') as client:
        assert client.get('/api/v2/operations').status_code == 200
        assert client.get('/api/v2/operations', headers={'origin': 'https://evil.invalid'}).status_code == 403
        assert client.get('/api/v2/operations', headers={'host': 'evil.invalid'}).status_code == 400
    host.engine.dispose()


def test_runtime_entry_retains_credentials_and_rejects_missing_db_or_root_rebinding(tmp_path: Path) -> None:
    credentials = tmp_path / 'credentials'
    credentials.mkdir()
    private = credentials / 'config.json'
    private.write_text('{"deepseek_api_key":"SYNTHETIC_FIXTURE_KEY","deepseek_model":"deepseek-flash"}')
    original = private.read_bytes()
    model = tmp_path / 'model.bin'
    model.write_bytes(b'fixture-only; inference forbidden')
    manifest = initialize(tmp_path / 'candidate', credentials, model)
    host = open_runtime(manifest)
    with Session(host.engine) as session:
        set_admissions(session, paused=False)
        session.commit()
    assert host.executor.iteration(host.dispatch) is None
    with Session(host.engine) as session:
        set_admissions(session, paused=True)
        session.commit()
    with TestClient(create_app(host.root, model=model, host=host)) as client:
        assert client.get('/companion-api/config').json()['translation_configured'] is True
        empty = client.post('/companion-api/jobs/upload', params={'saozi': False, 'ranges': '[["1","3"]]'}, content=b'')
        assert empty.status_code == 422
        queue = client.get('/api/v2/operations').json()
        operation = queue['operations'][0]
        assert operation['state'] == 'failed' and operation['failure_code'] == 'upload_incomplete_reselect_file'
        assert client.post('/api/v2/operations/' + operation['id'] + '/retry').status_code == 409
        assert not list(host.root.glob('*/gui.json'))
        assert client.post('/companion-api/llm-config', json={'provider': 'deepseek', 'model': 'deepseek-flash'}).status_code == 200
        assert private.read_bytes() == original
        assert host.globals.read('llm/preferences.json') is not None
    changed = tmp_path / 'unexpected-tasks'
    with pytest.raises(OperationConflict, match='root roles changed'):
        NativeHost(host.engine, task_root=changed, settings_root=host.settings_root,
            credential_root=credentials, guard_root=host.guard_root, model=model)
    assert not changed.exists()
    with Session(host.engine) as session:
        assert session.exec(select(UnifiedOperation)).one().attempt == 0
    host.engine.dispose()
    database = manifest.parent / 'db/unified.sqlite3'
    database.rename(database.with_suffix('.retained'))
    with pytest.raises(OperationConflict, match='automatic recreation'):
        open_runtime(manifest)
    assert not database.exists()
