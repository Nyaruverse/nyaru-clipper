from __future__ import annotations

import json
import re
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Literal, Mapping

from pydantic import BaseModel, ConfigDict, JsonValue, SecretStr, StrictStr, ValidationError

from app.arctime import media, translation
from app.arctime.chatgpt_auth import ChatGPTAuth
from app.arctime.companion_models import validated_api_key

if TYPE_CHECKING:
    from app.services.global_documents import GlobalDocuments


class PublicPreferences(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    deepseek_model: str
    llm_provider: Literal['deepseek', 'chatgpt']
    chatgpt_model: str


class LLMConfig:
    """Mutable provider settings shared by the CLI and companion manager."""

    def __init__(self, root: Path, *, settings_root: Path | None = None, credential_root: Path | None = None,
                 preferences: GlobalDocuments | None = None):
        self.root = root.expanduser().resolve()
        self.settings_root = (settings_root or self.root).expanduser().resolve()
        self.credential_root = (credential_root or self.root).expanduser().resolve()
        self.preferences = preferences
        self.api_key: SecretStr | None = None
        self.translation_model = translation.MODEL
        self.llm_provider = 'deepseek'
        self.chatgpt_model = ''
        self.chatgpt = ChatGPTAuth(self.credential_root)
        self.config_path = self.credential_root / 'config.json'
        self.config_error: str | None = None
        try:
            if self.config_path.is_symlink():
                raise ValueError('配置文件不能是符号链接')
            if self.config_path.exists():
                if self.config_path.stat().st_size > 16384:
                    raise ValueError('配置文件过大')
                config = json.loads(self.config_path.read_text(encoding='utf-8'))
                if not isinstance(config, dict) or 'deepseek_api_key' not in config:
                    raise ValueError('配置格式无效')
                if config['deepseek_api_key'] != '':
                    self.api_key = validated_api_key(config['deepseek_api_key'])
                selected = config.get('deepseek_model', translation.MODEL)
                if selected not in translation.MODELS:
                    raise ValueError('翻译模型无效')
                self.translation_model = selected
                provider = config.get('llm_provider', 'deepseek')
                if provider not in {'deepseek', 'chatgpt'}:
                    raise ValueError('供应商配置无效')
                self.llm_provider = provider
                model = config.get('chatgpt_model', '')
                if not isinstance(model, str) or (model and not re.fullmatch(r'[A-Za-z0-9._-]{1,128}', model)):
                    raise ValueError('订阅模型配置无效')
                self.chatgpt_model = model
        except (OSError, ValueError, UnicodeError):
            self.config_error = '无法读取翻译配置；请检查 runs/config.json 或重新保存 Key／模型'
        self.load_preferences()

    def load_preferences(self) -> None:
        if self.preferences is not None:
            content = self.preferences.read('llm/preferences.json')
            if content is not None:
                value = PublicPreferences.model_validate_json(content)
                self.translation_model, self.llm_provider, self.chatgpt_model = value.deepseek_model, value.llm_provider, value.chatgpt_model


class _JobModel(BaseModel):
    model_config = ConfigDict(frozen=True, hide_input_in_errors=True)
    saozi_model: StrictStr | None = None
    llm_model: StrictStr | None = None
    llm_provider: Literal['deepseek', 'chatgpt'] | None = None


def job_model(manager: LLMConfig, saved: Mapping[str, JsonValue]) -> str:
    try:
        identity = _JobModel.model_validate(saved)
    except ValidationError:
        raise ValueError('任务供应商或模型配置无效') from None
    model = identity.saozi_model or identity.llm_model
    if model:
        provider = 'chatgpt' if model.startswith('chatgpt:') else 'deepseek'
        if identity.llm_provider and identity.llm_provider != provider:
            raise ValueError('任务供应商与模型不一致')
        return model
    if identity.llm_provider:
        return 'chatgpt:' + manager.chatgpt_model if identity.llm_provider == 'chatgpt' else manager.translation_model
    return selected_model(manager)


def selected_model(manager: LLMConfig) -> str:
    if manager.config_error:
        raise ValueError(manager.config_error)
    return 'chatgpt:' + manager.chatgpt_model if manager.llm_provider == 'chatgpt' else manager.translation_model


def configured(manager: LLMConfig) -> bool:
    if manager.llm_provider == 'chatgpt':
        status = manager.chatgpt.status()
        return bool(status['connected'] and status['sharing'] and manager.chatgpt_model)
    return manager.api_key is not None and manager.config_error is None and manager.translation_model in translation.MODELS


def require_key(manager: LLMConfig, model: str) -> SecretStr:
    if model.startswith('chatgpt:'):
        status = manager.chatgpt.status()
        if not model.removeprefix('chatgpt:') or not status['connected'] or not status['sharing']:
            raise ValueError('请先登录 ChatGPT 并允许使用订阅额度，再选择模型')
        return SecretStr('')
    if model not in translation.MODELS:
        raise ValueError('此模型已禁用；DeepSeek 仅支持 Flash')
    if manager.config_error or manager.api_key is None:
        raise ValueError('请先保存有效 DeepSeek Flash API Key')
    return manager.api_key


def requester(manager: LLMConfig, model: str) -> Callable[[str, str], str] | None:
    if model.startswith('chatgpt:'):
        from app.arctime.chatgpt_provider import ChatGPTProvider
        return ChatGPTProvider(model.removeprefix('chatgpt:'), manager.chatgpt.token)
    return None


def persist(manager: LLMConfig) -> None:
    if manager.config_path.is_symlink():
        raise ValueError('配置文件不能是符号链接，请检查 runs/config.json')
    if manager.preferences is not None:
        from app.arctime.workflow import exclusive_lock
        manager.credential_root.mkdir(parents=True, exist_ok=True, mode=0o700)
        with exclusive_lock(manager.credential_root / '.config.lock'):
            current = json.loads(manager.config_path.read_bytes()) if manager.config_path.exists() else {}
            key = manager.api_key.get_secret_value() if manager.api_key else ''
            if current.get('deepseek_api_key', '') != key:
                current['deepseek_api_key'] = key
                media.write_json(manager.config_path, current)
        value = PublicPreferences(deepseek_model=manager.translation_model, llm_provider=manager.llm_provider, chatgpt_model=manager.chatgpt_model)
        body = value.model_dump_json().encode()
        with manager.preferences.mutation():
            if manager.preferences.read('llm/preferences.json') != body:
                manager.preferences.write('llm/preferences.json', body)
        return
    media.write_json(manager.config_path, {
        'deepseek_api_key': manager.api_key.get_secret_value() if manager.api_key else '',
        'deepseek_model': manager.translation_model,
        'llm_provider': manager.llm_provider,
        'chatgpt_model': manager.chatgpt_model,
    })
