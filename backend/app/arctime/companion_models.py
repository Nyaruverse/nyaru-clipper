from __future__ import annotations

from urllib.parse import urlsplit
from pydantic import BaseModel, Field, SecretStr, model_validator
from app.arctime import media


class TranslationConfig(BaseModel):
    api_key: SecretStr | None = None
    model: str | None = Field(default=None, max_length=128)


def validated_api_key(value: object) -> SecretStr:
    if not isinstance(value, str):
        raise ValueError("请输入有效 API Key")
    value = value.strip()
    if not value or len(value) > 512 or any(ord(c) < 33 or ord(c) > 126 for c in value):
        raise ValueError("请输入有效 API Key")
    return SecretStr(value)


class JobInput(BaseModel):
    url: str = Field(max_length=8192)
    ranges: list[tuple[str, str]] = Field(default_factory=list, max_length=100)
    highlights: int | None = Field(default=None, ge=1, le=100)
    language: str = Field(default="auto", pattern=r"^[a-z]{2,8}$")

    @model_validator(mode="after")
    def validate_selection(self):
        parsed = urlsplit(self.url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError("请输入不含账号密码的 HTTP(S) 视频链接")
        if bool(self.ranges) == (self.highlights is not None):
            raise ValueError("请选择指定时间段或高光模式")
        for start, end in self.ranges:
            if media.parse_time(start) >= media.parse_time(end):
                raise ValueError("结束时间必须大于开始时间")
        return self
