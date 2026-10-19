from __future__ import annotations

from datetime import datetime

from sqlmodel import Session, select

from app.models import RuntimeConfig, utc_now

DEEPSEEK_API_KEY_CONFIG_KEY = "deepseek_api_key"


def get_runtime_config_value(session: Session, key: str) -> str | None:
    """Return the stored runtime config value, or None when unset."""
    record = session.get(RuntimeConfig, key)
    if record is None or not record.value:
        return None
    return record.value


def set_runtime_config_value(session: Session, key: str, value: str) -> RuntimeConfig:
    """Insert or update one runtime config entry with a fresh timestamp."""
    record = session.get(RuntimeConfig, key)
    if record is None:
        record = RuntimeConfig(key=key, value=value, updated_at=utc_now())
    else:
        record.value = value
        record.updated_at = utc_now()
    session.add(record)
    session.commit()
    return record


def clear_runtime_config_value(session: Session, key: str) -> bool:
    """Delete one runtime config entry; return whether it existed."""
    record = session.get(RuntimeConfig, key)
    if record is None:
        return False
    session.delete(record)
    session.commit()
    return True


def resolve_effective_deepseek_api_key(session: Session, configured_key: str | None) -> str | None:
    """Prefer the process/env-configured key, falling back to the WebUI-managed one."""
    if configured_key:
        return configured_key
    stored = get_runtime_config_value(session, DEEPSEEK_API_KEY_CONFIG_KEY)
    if stored:
        return stored
    return None


def runtime_config_updated_at(session: Session, key: str) -> datetime | None:
    record = session.get(RuntimeConfig, key)
    if record is None:
        return None
    return record.updated_at
