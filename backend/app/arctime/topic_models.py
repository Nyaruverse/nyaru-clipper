"""Topic contracts adapted from 69d3fa0/topic_segments.py; heuristic quality is unvalidated."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class TopicError(ValueError):
    pass


class TopicModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)


class TopicAnalyzeOptions(TopicModel):
    start_seconds: float | None = Field(default=None, ge=0)
    end_seconds: float | None = Field(default=None, gt=0)
    max_segments: int = Field(default=100, ge=1, le=100, strict=True)

    @model_validator(mode="after")
    def ordered_range(self) -> TopicAnalyzeOptions:
        if self.end_seconds is not None and self.end_seconds <= (
            self.start_seconds or 0
        ):
            raise TopicError("结束时间必须大于开始时间")
        return self


class TopicExportRange(TopicModel):
    index: int = Field(strict=True, ge=0, le=99)
    start_seconds: float = Field(ge=0)
    end_seconds: float = Field(gt=0)

    @model_validator(mode="after")
    def ordered_range(self) -> TopicExportRange:
        if self.end_seconds <= self.start_seconds:
            raise TopicError("结束时间必须大于开始时间")
        return self


class TopicClipOptions(TopicModel):
    indices: list[Annotated[int, Field(strict=True, ge=0, le=99)]] = Field(
        min_length=1, max_length=100
    )
    mode: Literal["separate", "combined"] = "separate"
    variant: Literal["original", "zh", "bilingual"] = "bilingual"
    ranges: list[TopicExportRange] = Field(default_factory=list, max_length=100)

    @model_validator(mode="after")
    def unique_indices(self) -> TopicClipOptions:
        if len(set(self.indices)) != len(self.indices) or any(
            index < 0 or index > 100 for index in self.indices
        ):
            raise TopicError("切片索引必须唯一且在 0–100 范围内；顺序按所选顺序保留")
        range_indices = [item.index for item in self.ranges]
        if len(set(range_indices)) != len(range_indices):
            raise TopicError("切片范围索引必须唯一")
        if not set(range_indices).issubset(self.indices):
            raise TopicError("切片范围只能覆盖所选索引")
        return self


class DanmakuEntry(TopicModel):
    seconds: float = Field(ge=0, le=604800)
    text: str = Field(min_length=1, max_length=2000)
    user: str = Field(default="", max_length=128)


class DanmakuStore(TopicModel):
    source: Literal["ass", "xml"] | None = None
    streamer: str | None = Field(default=None, max_length=128)
    entries: list[DanmakuEntry] = Field(default_factory=list, max_length=100000)


class ScoringConfig(TopicModel):
    revision: Literal[1] = 1
    risk_terms: list[str] = Field(
        default_factory=lambda: [
            "政治",
            "政府",
            "选举",
            "首相",
            "总统",
            "开盒",
            "人肉搜索",
            "住址",
            "家庭住址",
            "电话号码",
            "手机号码",
            "身份证",
            "真实姓名",
            "本名",
            "户籍",
            "未成年",
            "色情",
            "裸聊",
            "裸体",
            "性行为",
            "自杀",
            "自残",
            "毒品",
            "吸毒",
            "贩毒",
            "枪支",
            "恐怖袭击",
            "選挙",
            "大統領",
            "個人情報",
            "住所",
            "電話番号",
            "身分証明書",
            "自殺",
            "自傷",
            "薬物",
            "麻薬",
            "わいせつ",
            "テロ",
        ]
    )
    profile_terms: dict[str, float] = Field(default_factory=dict)
    streamer: str | None = None


class TopicSegment(TopicModel):
    index: int
    start_id: int
    end_id: int
    start_seconds: float
    end_seconds: float
    cue_count: int
    title: str
    summary: str
    preview: str
    analyzed: bool = True
    dm_count: int | None = None
    dm_rate: float | None = None
    dm_users: int | None = None
    dm_peak: int | None = None
    dm_peak_time: float | None = None
    dm_repeat: float | None = None
    score: int | None = None
    grade: str | None = None
    loudness_db: float | None = None
    laugh_rate: float | None = None
    meme_hits: int | None = None
    meme_rate: float | None = None
    hot_words: list[str] = Field(default_factory=list)
    risk_terms: list[str] = Field(default_factory=list)
    risk: bool = False
    dm_shape: str | None = None
    dm_shape_score: float | None = None


class TopicQuote(TopicModel):
    text: str
    start: float
    score: int


class TopicSegmentStore(TopicModel):
    state: str = "completed"
    operation_id: str | None = None
    document_revision: int | None = None
    document_sha256: str | None = None
    error: str | None = None
    created_at: float = 0
    total_cues: int = 0
    covered_cues: int = 0
    truncated: bool = False
    range_start: float | None = None
    range_end: float | None = None
    scored_at: float | None = None
    scoring: Literal["unavailable", "danmaku_text", "danmaku_text_audio"] = (
        "unavailable"
    )
    audio_state: Literal["available", "truncated", "unavailable"] = "unavailable"
    streamer: str | None = None
    vocabulary: list[str] = Field(default_factory=list)
    extracted_terms: dict[str, float] = Field(default_factory=dict)
    quotes: list[TopicQuote] = Field(default_factory=list)
    segments: list[TopicSegment] = Field(default_factory=list)
