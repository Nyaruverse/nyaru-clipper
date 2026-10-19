from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session

from app.db import get_session
from app.repositories import runtime_config as runtime_config_repo
from app.services.runtime_capabilities import get_cached_runtime_capabilities

router = APIRouter(prefix="/runtime", tags=["runtime"])


@router.get("/capabilities")
def runtime_capabilities() -> dict[str, object]:
    return get_cached_runtime_capabilities()


class DeepSeekConfigStatus(BaseModel):
    configured: bool
    source: str | None
    updated_at: str | None = None


class DeepSeekConfigUpdate(BaseModel):
    api_key: str = Field(min_length=1)


def _deepseek_status(session: Session) -> DeepSeekConfigStatus:
    env_configured = runtime_config_repo.resolve_effective_deepseek_api_key(session, None) is not None
    from app.settings import get_settings

    env_key = get_settings().deepseek_api_key
    if env_key is not None and env_key.get_secret_value().strip():
        return DeepSeekConfigStatus(configured=True, source="environment")
    stored_at = runtime_config_repo.runtime_config_updated_at(session, runtime_config_repo.DEEPSEEK_API_KEY_CONFIG_KEY)
    return DeepSeekConfigStatus(
        configured=env_configured,
        source="database" if env_configured else None,
        updated_at=stored_at.isoformat() if stored_at is not None else None,
    )


@router.get("/config/deepseek")
def get_deepseek_config(session: Session = Depends(get_session)) -> DeepSeekConfigStatus:
    """Report whether DeepSeek proofreading is configured, never exposing the key."""
    return _deepseek_status(session)


@router.put("/config/deepseek")
def put_deepseek_config(payload: DeepSeekConfigUpdate, session: Session = Depends(get_session)) -> DeepSeekConfigStatus:
    """Store a WebUI-managed DeepSeek API key used when the environment has none."""
    trimmed = payload.api_key.strip()
    if not trimmed:
        raise HTTPException(status_code=422, detail="api_key must not be blank")
    runtime_config_repo.set_runtime_config_value(
        session,
        runtime_config_repo.DEEPSEEK_API_KEY_CONFIG_KEY,
        trimmed,
    )
    return _deepseek_status(session)


@router.delete("/config/deepseek")
def delete_deepseek_config(session: Session = Depends(get_session)) -> DeepSeekConfigStatus:
    """Remove the WebUI-managed DeepSeek API key."""
    runtime_config_repo.clear_runtime_config_value(session, runtime_config_repo.DEEPSEEK_API_KEY_CONFIG_KEY)
    return _deepseek_status(session)
