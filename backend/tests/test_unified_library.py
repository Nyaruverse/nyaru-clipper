from pathlib import Path

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.arctime.gui import create_app
from app.arctime.unified_host import NativeHost
from app.services.migration_groups import create_group, rollback_category
from test_unified_operations import database


def test_shared_library_has_sql_filters_metadata_cas_and_group_wide_r2(tmp_path: Path) -> None:
    model = tmp_path / 'model.bin'
    model.write_bytes(b'fixture-only')
    host = NativeHost(database(tmp_path), task_root=tmp_path / 'tasks', settings_root=tmp_path / 'settings',
        credential_root=tmp_path / 'credentials', guard_root=tmp_path / 'guard', model=model)
    with TestClient(create_app(host.root, model=model, host=host)) as client:
        created = client.post('/companion-api/jobs', json={'url': 'https://fixture.invalid/source', 'ranges': [['1', '3']], 'language': 'ja'})
        assert created.status_code == 202, created.text
        task_id = created.json()['id']
        initial = client.get('/api/v2/library').json()['items'][0]
        with Session(host.engine) as session:
            group_id = create_group(session).id
            session.commit()
        saved = client.patch('/api/v2/library/' + task_id, json={'expected_version': initial['version'], 'title': '标题%_迁移', 'tags': ['零', '双语']})
        assert saved.status_code == 200, saved.text
        assert saved.json()['tags'] == ['双语', '零']
        assert client.get('/api/v2/library', params={'search': '%_'}).json()['total'] == 1
        assert client.get('/api/v2/library', params={'tag': '双语'}).json()['total'] == 1
        stale = client.patch('/api/v2/library/' + task_id, json={'expected_version': initial['version'], 'title': 'stale overwrite'})
        assert stale.status_code == 409
        archived = client.patch('/api/v2/library/' + task_id, json={'expected_version': saved.json()['version'], 'archived': True})
        assert archived.status_code == 200, archived.text
        assert client.get('/api/v2/library').json()['total'] == 0
        assert client.get('/api/v2/library?include_archived=true').json()['items'][0]['title'] == '标题%_迁移'
        with Session(host.engine) as session:
            assert rollback_category(session, group_id) == 'R2'
