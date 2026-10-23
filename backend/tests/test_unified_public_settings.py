import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.api.schemas.operations import RecordingOperation
from app.arctime.companion_llm import PublicPreferences
from app.arctime.companion_models import JobInput
from app.arctime.migration_cli import main
from app.services.public_runtime_settings import PUBLIC_FIELDS, PublicRuntimeSettings
from app.services.unified_runtime import initialize, open_runtime
from app.settings import Settings


def test_public_snapshot_preserves_fields_without_secret_copy_and_freezes_admission(tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch) -> None:
    credentials = tmp_path / 'credentials'
    credentials.mkdir()
    private = credentials / 'config.json'
    private.write_text('{"deepseek_api_key":"SYNTHETIC_PRIVATE_CANARY","deepseek_model":"deepseek-flash"}')
    original = private.read_bytes()
    model = tmp_path / 'model.bin'
    model.write_bytes(b'fixture, no inference')
    manifest = initialize(tmp_path / 'candidate', credentials, model, threads=3)
    snapshot = tmp_path / 'public.json'
    monkeypatch.setenv('APP_WHISPERX_BATCH_SIZE', '3')
    assert main(['--runtime', str(manifest), 'capture-public', '--output', str(snapshot)]) == 0
    assert private.read_bytes() == original and b'SYNTHETIC_PRIVATE_CANARY' not in snapshot.read_bytes()
    public = PublicRuntimeSettings.model_validate_json(snapshot.read_bytes())
    assert set(public.settings) == PUBLIC_FIELDS and public.cpp_model == model and public.cpp_threads == 3
    host = open_runtime(manifest)
    with host.globals.mutation():
        host.globals.write('runtime/settings.json', snapshot.read_bytes())
    monkeypatch.setenv('APP_WHISPERX_BATCH_SIZE', '99')
    payload = RecordingOperation(kind='process_recording', task_id='a' * 32, engine='whisper.cpp',
        request=JobInput(url='https://fixture.invalid', ranges=[('0', '2')]))
    captured = host.configuration(payload)
    assert captured['whisperx_batch_size'] == 3 and captured['threads'] == 3
    assert 'deepseek_api_key' not in captured and 'bilibili_cookie_path' not in captured
    assert json.loads(snapshot.read_bytes())['companion']['deepseek_model'] == 'deepseek-flash'
    host.engine.dispose()


def test_public_package_rejects_credentials_and_incomplete_default_inference(tmp_path: Path) -> None:
    value = dict(settings=Settings().model_dump(mode='json', include=PUBLIC_FIELDS),
        companion=PublicPreferences(deepseek_model='deepseek-flash', llm_provider='deepseek', chatgpt_model=''),
        cpp_model=tmp_path / 'model.bin', cpp_threads=2)
    value['settings']['deepseek_api_key'] = 'NEVER_ARCHIVE'
    with pytest.raises(ValidationError, match='credential fields prohibited'):
        PublicRuntimeSettings.model_validate(value)
    value['settings'] = {}
    with pytest.raises(ValidationError, match='complete public host settings'):
        PublicRuntimeSettings.model_validate(value)
