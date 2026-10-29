from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.services.subtitles import SubtitleSegment

_COLOR = r"^#[0-9A-Fa-f]{6}$"
FONT_FAMILY_SAFE = re.compile(r"^[^\x00-\x1f,{}:\\]{1,64}$")
TEMPLATE_NAME = re.compile(r"^[^\x00-\x1f/\\]{1,32}$")
MAX_TEMPLATES = 20
MAX_OUTLINES = 3
MAX_SHAPES = 20
PLAY_RES_X = 1920
PLAY_RES_Y = 1080


class OutlineLayer(BaseModel):
    color: str = Field(default="#000000", pattern=_COLOR)
    width: float = Field(default=2.0, ge=0.5, le=20)


class TextStyle(BaseModel):
    font_family: str = Field(default="Microsoft YaHei", max_length=64)
    font_size: int = Field(default=48, ge=8, le=200)
    text_color: str = Field(default="#FFFFFF", pattern=_COLOR)
    background_color: str = Field(default="#000000", pattern=_COLOR)
    background_opacity: float = Field(default=0.0, ge=0, le=1)
    outlines: list[OutlineLayer] = Field(default_factory=lambda: [OutlineLayer()], max_length=MAX_OUTLINES)
    pos_x: float = Field(default=50.0, ge=0, le=100)
    pos_y: float = Field(default=92.0, ge=0, le=100)
    align: Literal["left", "center", "right"] = "center"

    def validate_font(self) -> "TextStyle":
        if not FONT_FAMILY_SAFE.fullmatch(self.font_family):
            raise ValueError("字体名称无效")
        return self

    @model_validator(mode="before")
    @classmethod
    def migrate_v1(cls, data: object) -> object:
        """旧版（outline_width/outline_color/position/vertical_margin）自动迁移。"""
        if not isinstance(data, dict) or "outline_width" not in data:
            return data
        data = dict(data)
        width = data.pop("outline_width", 2.0)
        color = data.pop("outline_color", "#000000")
        position = data.pop("position", "bottom")
        margin = data.pop("vertical_margin", 60)
        try:
            width = max(0.5, min(20.0, float(width)))
        except (TypeError, ValueError):
            width = 2.0
        data["outlines"] = [{"color": color if isinstance(color, str) else "#000000", "width": width}]
        try:
            margin = max(0, min(500, int(margin)))
        except (TypeError, ValueError):
            margin = 60
        y = margin / PLAY_RES_Y * 100
        data["pos_y"] = round(100 - y, 2) if position == "bottom" else round(max(y, 4.0), 2)
        data["pos_x"] = 50.0
        data["align"] = "center"
        return data


class SubtitleStyleConfig(BaseModel):
    original: TextStyle = Field(default_factory=lambda: TextStyle(pos_y=78.0))
    translated: TextStyle = Field(default_factory=lambda: TextStyle(font_size=64, pos_y=92.0))
    # 图层开关：关闭后预览与烧录合成都不再绘制对应字幕层
    show_original: bool = True
    show_translated: bool = True


class Shape(BaseModel):
    """矩形图形：x/y 为中心点百分比（与字幕锚点一致），width/height 为画布百分比。"""
    x: float = Field(default=50.0, ge=0, le=100)
    y: float = Field(default=50.0, ge=0, le=100)
    width: float = Field(default=40.0, ge=1, le=100)
    height: float = Field(default=20.0, ge=1, le=100)
    radius: int = Field(default=0, ge=0, le=200)  # 圆角半径，1080p 像素
    fill_color: str = Field(default="#000000", pattern=_COLOR)
    fill_opacity: float = Field(default=0.5, ge=0, le=1)
    outline_color: str = Field(default="#FFFFFF", pattern=_COLOR)
    outline_width: float = Field(default=0.0, ge=0, le=40)  # 1080p 像素


class ShapesUpdate(BaseModel):
    shapes: list[Shape] = Field(default_factory=list, max_length=MAX_SHAPES)


class StyleStore(BaseModel):
    version: int = 2
    current: SubtitleStyleConfig = Field(default_factory=SubtitleStyleConfig)
    templates: dict[str, SubtitleStyleConfig] = Field(default_factory=dict)
    shapes: list[Shape] = Field(default_factory=list, max_length=MAX_SHAPES)
    shapes_templates: dict[str, list[Shape]] = Field(default_factory=dict)


def load_style_store(path: Path) -> StyleStore:
    try:
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 65536:
            return StyleStore()
        return StyleStore.model_validate(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, ValueError, json.JSONDecodeError):
        return StyleStore()


def _ass_color(hex_color: str, opacity: float = 1.0) -> str:
    red = int(hex_color[1:3], 16)
    green = int(hex_color[3:5], 16)
    blue = int(hex_color[5:7], 16)
    alpha = 255 - round(max(0.0, min(1.0, opacity)) * 255)
    return f"&H{alpha:02X}{blue:02X}{green:02X}{red:02X}"


def _hex_rgb(hex_color: str) -> tuple[int, int, int]:
    return (int(hex_color[1:3], 16), int(hex_color[3:5], 16), int(hex_color[5:7], 16))


def render_shape_pngs(shapes: list[Shape], directory: Path, stem: str,
                      *, width: int = PLAY_RES_X, height: int = PLAY_RES_Y) -> list[Path]:
    """把矩形图形渲染为视频实际分辨率的透明 PNG，供 ffmpeg overlay 叠加到字幕下层。"""
    from PIL import Image, ImageDraw
    scale = height / PLAY_RES_Y  # 圆角/描边按 1080p 像素定义，随视频分辨率等比缩放
    paths: list[Path] = []
    for index, shape in enumerate(shapes):
        image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        center_x, center_y = shape.x / 100 * width, shape.y / 100 * height
        half_w, half_h = shape.width / 100 * width / 2, shape.height / 100 * height / 2
        box = [center_x - half_w, center_y - half_h, center_x + half_w, center_y + half_h]
        fill = (*_hex_rgb(shape.fill_color), round(shape.fill_opacity * 255))
        outline = None
        line_width = 1
        if shape.outline_width > 0:
            outline = (*_hex_rgb(shape.outline_color), 255)
            line_width = max(1, round(shape.outline_width * scale))
        draw.rounded_rectangle(box, radius=round(shape.radius * scale), fill=fill, outline=outline, width=line_width)
        path = directory / f".{stem}.shape{index}.png"
        image.save(path)
        paths.append(path)
    return paths


_ALIGN_CODE = {"left": 4, "center": 5, "right": 6}  # 中部对齐，配合 \pos 精确锚点


def _style_base(name: str, ts: TextStyle) -> str:
    """BorderStyle=1 的文字层样式；位置/描边/背景通过 Dialogue 覆写。"""
    return (
        f"Style: {name},{ts.font_family},{ts.font_size},"
        f"{_ass_color(ts.text_color)},{_ass_color(ts.text_color)},"
        f"{_ass_color('#000000')},&H00000000,"
        f"-1,0,0,0,100,100,0,0,1,0,0,{_ALIGN_CODE[ts.align]},40,40,0,1"
    )


def _box_style(name: str, ts: TextStyle) -> str:
    """BorderStyle=3 的背景块样式；文字透明，仅绘制背景框。"""
    bg = _ass_color(ts.background_color, ts.background_opacity)
    transparent = "&HFF000000"
    padding = max(4, round(ts.font_size * 0.15))  # 与预览 span 内边距一致
    return (
        f"Style: {name},{ts.font_family},{ts.font_size},"
        f"{transparent},{transparent},{bg},{bg},"
        f"0,0,0,0,100,100,0,0,3,{padding},0,{_ALIGN_CODE[ts.align]},40,40,0,1"
    )


def _format_ass_time(seconds: float) -> str:
    centiseconds = max(0, round(seconds * 100))
    hours, remainder = divmod(centiseconds, 360000)
    minutes, remainder = divmod(remainder, 6000)
    secs, cs = divmod(remainder, 100)
    return f"{hours}:{minutes:02d}:{secs:02d}.{cs:02d}"


def _escape_ass_text(text: str) -> str:
    return text.replace("\\", r"\\").replace("{", r"\{").replace("}", r"\}").replace("\n", r"\N")


def _pos_tag(ts: TextStyle) -> str:
    x = round(ts.pos_x / 100 * PLAY_RES_X)
    y = round(ts.pos_y / 100 * PLAY_RES_Y)
    return rf"\pos({x},{y})"


def _cue_events(events: list, layer: int, start: str, end: str, base: str, ts: TextStyle, text: str) -> int:
    """按 背景框 → 外层描边 → 内层描边 → 正文 的顺序写入，返回下一个可用层号。"""
    escaped = _escape_ass_text(text)
    pos = _pos_tag(ts)
    if ts.background_opacity > 0:
        events.append(f"Dialogue: {layer},{start},{end},{base}Box,,0,0,0,,{{{pos}}}{escaped}")
        layer += 1
    outlines = ts.outlines
    cumulative = 0.0
    widths: list[float] = []
    for outline in outlines:
        cumulative += outline.width
        widths.append(cumulative)
    # 由外到内：底层描边宽度为各层宽度累加，填充色为该层描边色
    for index in range(len(outlines) - 1, -1, -1):
        outline = outlines[index]
        tags = rf"{pos}\bord{round(widths[index], 2)}\1c&HFF&\3c{_ass_color(outline.color)}&"
        events.append(f"Dialogue: {layer},{start},{end},{base},,0,0,0,,{{{tags}}}{escaped}")
        layer += 1
    events.append(rf"Dialogue: {layer},{start},{end},{base},,0,0,0,,{{{pos}\bord0}}{escaped}")
    return layer + 1


def render_ass(segments: list[SubtitleSegment], translated: list[str] | None,
               style: SubtitleStyleConfig, variant: Literal["bilingual", "zh", "original"]) -> str:
    if variant in {"bilingual", "zh"}:
        if translated is None or len(translated) != len(segments):
            raise ValueError("译文数量与字幕不匹配，无法生成烧录字幕")
    style_lines = [_style_base("Original", style.original), _box_style("OriginalBox", style.original),
                   _style_base("Translated", style.translated), _box_style("TranslatedBox", style.translated)]
    header = "\n".join([
        "[Script Info]",
        "ScriptType: v4.00+",
        f"PlayResX: {PLAY_RES_X}",
        f"PlayResY: {PLAY_RES_Y}",
        "WrapStyle: 2",
        "ScaledBorderAndShadow: yes",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
        "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
        "Alignment, MarginL, MarginR, MarginV, Encoding",
        *style_lines,
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ])
    events: list[str] = []
    layer = 0
    for index, cue in enumerate(segments):
        start = _format_ass_time(cue.start_seconds)
        end = _format_ass_time(cue.end_seconds)
        if variant in {"bilingual", "original"} and style.show_original:
            layer = _cue_events(events, layer, start, end, "Original", style.original, cue.text)
        if variant in {"bilingual", "zh"} and style.show_translated:
            layer = _cue_events(events, layer, start, end, "Translated", style.translated, translated[index])
    return header + "\n" + "\n".join(events) + "\n"
