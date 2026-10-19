from __future__ import annotations

import re
from urllib.parse import urlsplit
from pydantic import BaseModel, Field, SecretStr, model_validator
from app.arctime import media


class TranslationConfig(BaseModel):
    api_key: SecretStr | None = None
    model: str | None = Field(default=None, max_length=128)


class GlossarySettings(BaseModel):
    collect_candidates: bool


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
    saozi: bool = False
    live: bool = False
    language: str = Field(default="auto", pattern=r"^[a-z]{2,8}$")
    subtitle_template_id: str | None = Field(default=None, pattern=r'^(?:[0-9a-f]{32}|nyaru|default|white)$')

    @model_validator(mode="after")
    def validate_selection(self):
        if self.subtitle_template_id and not self.live:
            raise ValueError('自动字幕模板仅用于实时录播')
        self.url = self.url.strip()
        if self.live and re.fullmatch(r"[1-9][0-9]*", self.url):
            self.url = "https://live.bilibili.com/" + self.url
        if not self.live and re.fullmatch(r"BV[A-Za-z0-9]{10}", self.url):
            self.url = "https://www.bilibili.com/video/" + self.url
        parsed = urlsplit(self.url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError("请输入不含账号密码的 HTTP(S) 视频链接")
        if sum((bool(self.ranges), self.highlights is not None, self.saozi)) > 1:
            raise ValueError("指定时间段、高光与臊子模式互斥，最多选择一个")
        # 全为 False 时表示「完整视频」模式：仅生成完整字幕不切片
        mode = "saozi" if self.saozi else "highlights" if self.highlights is not None else "ranges" if self.ranges else "full"
        if self.live and (not self.saozi or parsed.hostname != "live.bilibili.com"
                          or parsed.port is not None or parsed.query or parsed.fragment
                          or not re.fullmatch(r"/(?:blanc/)?[1-9]\d*/?", parsed.path)):
            raise ValueError("实时臊子请输入 Bilibili 直播间链接，如 https://live.bilibili.com/12345")
        for start, end in self.ranges:
            if media.parse_time(start) >= media.parse_time(end):
                raise ValueError("结束时间必须大于开始时间")
        return self

