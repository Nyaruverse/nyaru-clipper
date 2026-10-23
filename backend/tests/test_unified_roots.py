from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from app.arctime.gui import create_app
from app.arctime.subtitle_style import SubtitleStyle, TextStyle
from app.arctime.subtitle_templates import StudioSettings, TemplateStore, WorkflowDefaults


def test_task_root_change_keeps_settings_bindings_and_protected_credentials_offline(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    credentials, settings = tmp_path / 'private-authorization', tmp_path / 'settings'
    credentials.mkdir()
    config = credentials / 'config.json'
    config.write_text(json.dumps({'deepseek_api_key': 'synthetic-canary-do-not-copy', 'deepseek_model': 'deepseek-flash'}))
    config.chmod(0o600)
    before = config.read_bytes()
    templates = TemplateStore(settings)
    style = SubtitleStyle(original=TextStyle(color='#12AB34'))
    templates.save_defaults(style)
    template = templates.save_style('独立设置', style, workflow=WorkflowDefaults(language='zh', mode='highlights', highlights=7))
    templates.save_studio_settings(StudioSettings(default_template_id=template.id, language='zh', mode='highlights', highlights=7))

    def no_network(*args, **kwargs):
        raise AssertionError('network must not be contacted')

    monkeypatch.setattr(httpx.HTTPTransport, 'handle_request', no_network)
    for name in ['tasks-a', 'tasks-b']:
        root = tmp_path / name
        with TestClient(create_app(root, settings_root=settings, credential_root=credentials)) as client:
            status = client.get('/companion-api/config')
            assert status.status_code == 200 and status.json()['llm_configured'] is True
            assert 'synthetic-canary' not in status.text
            defaults = client.get('/companion-api/subtitle-settings').json()
            assert defaults['style'] == style.model_dump()
            assert next(row for row in defaults['templates'] if row['id'] == template.id)['workflow']['highlights'] == 7
            assert client.get('/companion-api/studio-settings').json()['default_template_id'] == template.id
        assert not (root / 'config.json').exists()
        assert not (root / '.chatgpt').exists()
    assert config.read_bytes() == before and config.stat().st_mode & 0o777 == 0o600
