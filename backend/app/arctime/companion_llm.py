from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from pydantic import SecretStr

from app.arctime import media, translation

if TYPE_CHECKING:
    from app.arctime.companion_manager import JobManager


def selected_model(manager: JobManager) -> str:
    return 'chatgpt:' + manager.chatgpt_model if manager.llm_provider == 'chatgpt' else manager.translation_model


def configured(manager: JobManager) -> bool:
    if manager.llm_provider == 'chatgpt':
        status = manager.chatgpt.status()
        return bool(status['connected'] and status['sharing'] and manager.chatgpt_model)
    return manager.api_key is not None and manager.config_error is None and manager.translation_model in translation.MODELS


def require_key(manager: JobManager, model: str) -> SecretStr:
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


def requester(manager: JobManager, model: str) -> Callable[[str, str], str] | None:
    if model.startswith('chatgpt:'):
        from app.arctime.chatgpt_provider import ChatGPTProvider
        return ChatGPTProvider(model.removeprefix('chatgpt:'), manager.chatgpt.token)
    return None


def persist(manager: JobManager) -> None:
    if manager.config_path.is_symlink():
        raise ValueError('配置文件不能是符号链接，请检查 runs/config.json')
    media.write_json(manager.config_path, {
        'deepseek_api_key': manager.api_key.get_secret_value() if manager.api_key else '',
        'deepseek_model': manager.translation_model,
        'llm_provider': manager.llm_provider,
        'chatgpt_model': manager.chatgpt_model,
    })
