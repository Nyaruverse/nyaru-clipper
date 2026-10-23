from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_validator

from app.arctime.companion_llm import PublicPreferences
from app.settings import Settings, get_settings


PUBLIC_FIELDS = frozenset(Settings.model_fields) - {'deepseek_api_key', 'bilibili_cookie_path'}


class PublicSettingsError(ValueError):
    pass


class PublicRuntimeSettings(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    settings: dict[str, JsonValue]
    companion: PublicPreferences
    cpp_model: Path
    cpp_threads: int = Field(ge=1, le=64)

    @field_validator('settings')
    @classmethod
    def complete_public_fields(cls, value: dict[str, JsonValue]) -> dict[str, JsonValue]:
        if set(value) != PUBLIC_FIELDS:
            raise PublicSettingsError('explicit complete public host settings required; credential fields prohibited')
        validated = Settings(**value, deepseek_api_key=None, bilibili_cookie_path=None, _env_file=None)
        return validated.model_dump(mode='json', include=PUBLIC_FIELDS)

    @field_validator('cpp_model')
    @classmethod
    def explicit_model(cls, value: Path) -> Path:
        if not value.is_absolute():
            raise PublicSettingsError('explicit model path required')
        return value


def effective_settings(content: bytes | None) -> Settings:
    if content is None:
        return get_settings()
    public = PublicRuntimeSettings.model_validate_json(content)
    current = get_settings()
    return Settings(**{**public.settings, 'deepseek_api_key': current.deepseek_api_key,
        'bilibili_cookie_path': current.bilibili_cookie_path}, _env_file=None)
