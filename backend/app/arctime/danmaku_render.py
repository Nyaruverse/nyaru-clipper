"""把弹幕条目渲染成 ASS，供切片/烧录时叠加在字幕层下方。

坐标基于 1920×1080（与字幕样式一致）；滚动弹幕为匀速（约 8 秒穿过全屏），
观感与 B站一致。顶部/底部弹幕统一按滚动处理，避免遮挡字幕。
SC（醒目留言）从文本前缀「【SC ¥」识别，渲染为带底框的固定卡片。
"""
from __future__ import annotations

import re
from dataclasses import dataclass

PLAY_RES_X = 1920
PLAY_RES_Y = 1080
SCROLL_SPEED = 240.0     # px/s：B站观感一致的匀速
SC_HOLD = 8.0            # SC 卡片停留秒数
_SC_LINE = re.compile(r"^【SC ¥(\d+(?:\.\d+)?)】(.*)$", re.S)

_ASS_TAG = re.compile(r"\{[^}]*\}")


@dataclass(frozen=True)
class DanmakuStyle:
    """font_size 为 1080p 基准字号；area_height 为弹幕区域占屏幕高度百分比。"""

    font_size: int = 40
    area_height: int = 60


def _ass_time(seconds: float) -> str:
    centiseconds = max(0, round(seconds * 100))
    hours, remainder = divmod(centiseconds, 360000)
    minutes, remainder = divmod(remainder, 6000)
    secs, cs = divmod(remainder, 100)
    return f"{hours}:{minutes:02d}:{secs:02d}.{cs:02d}"


def _ass_color(value: int) -> str:
    """B站颜色是十进制 RGB，ASS 内联色为 &HBBGGRR&。"""
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = 0xFFFFFF
    if not 0 <= number <= 0xFFFFFF:
        number = 0xFFFFFF
    return f"&H{number & 0xFF:02X}{(number >> 8) & 0xFF:02X}{(number >> 16) & 0xFF:02X}&"


def _escape(text: str) -> str:
    text = _ASS_TAG.sub("", text)
    return (text.replace("\\", r"\\").replace("{", r"\{").replace("}", r"\}")
            .replace("\n", " ").replace("\r", " "))


def _text_width(text: str, font_size: int) -> float:
    """估算文本像素宽度：全角按 1 字宽，半角按 0.55 字宽。"""
    units = 0.0
    for char in text:
        units += 1.0 if ord(char) > 0x2E80 else 0.55
    return units * font_size


def _style_line(name: str, size: int, border_style: int, outline: int) -> str:
    return (f"Style: {name},Microsoft YaHei,{size},&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,"
            f"0,0,0,0,100,100,0,0,{border_style},{outline},0,7,0,0,0,1")


def _entry_color(entry) -> int:
    # 老弹幕文件只有 [时间, 文本, 用户, 结束] 四项，颜色缺失时按 B站默认白色
    value = entry[5] if len(entry) > 5 else None
    return int(value) if isinstance(value, int) else 0xFFFFFF


def build_ass(entries, *, start: float, end: float, style: DanmakuStyle) -> str | None:
    """把 [start, end) 时间窗内的弹幕渲染成 ASS 文本；窗口内无弹幕时返回 None。"""
    rows: list[tuple[float, str, int]] = []
    for entry in entries:
        try:
            at = float(entry[0])
        except (TypeError, ValueError, IndexError):
            continue
        if not (start <= at < end):
            continue
        text = str(entry[1] if len(entry) > 1 else "").strip()
        if text:
            rows.append((at - start, text, _entry_color(entry)))
    if not rows:
        return None
    rows.sort(key=lambda item: item[0])

    font_size = max(12, min(96, int(style.font_size)))
    row_height = font_size * 1.2
    area_px = PLAY_RES_Y * max(10, min(100, int(style.area_height))) / 100
    tracks = max(1, int(area_px // row_height))

    events: list[str] = []
    free_at = [0.0] * tracks
    sc_events: list[str] = []
    sc_slots: list[float] = []          # 每个 SC 卡槽的释放时间
    sc_height = font_size * 2.6
    sc_slots_max = max(1, min(4, int(area_px // sc_height)))

    for at, text, color in rows:
        match = _SC_LINE.match(text)
        if match:
            # SC 卡片：停靠在弹幕区域底部，逐条向上堆叠
            slot = next((i for i, free in enumerate(sc_slots) if free <= at), None)
            if slot is None:
                if len(sc_slots) < sc_slots_max:
                    sc_slots.append(0.0)
                    slot = len(sc_slots) - 1
                else:
                    slot = min(range(len(sc_slots)), key=lambda i: sc_slots[i])
                    if sc_slots[slot] > at:
                        continue
            price, body = match.group(1), match.group(2) or ""
            sc_slots[slot] = at + SC_HOLD
            y = round(area_px - 12 - sc_height * (slot + 1))
            top = r"{\an8\pos(%d,%d)}" % (PLAY_RES_X // 2, max(0, y))
            # 卡片不换行，超长正文按画布宽度截断，避免左右溢出屏幕
            limit = max(12, int(1800 / (font_size * 0.85)))
            body = _escape(body)[:limit]
            sc_events.append(
                f"Dialogue: 1,{_ass_time(at)},{_ass_time(at + SC_HOLD)},Sc,"
                f",0,0,0,,{top}\\b900\\fs{round(font_size * 0.85)}¥{price}  {body}"
            )
            continue
        width = _text_width(text, font_size)
        track = next((i for i in range(tracks) if free_at[i] <= at), None)
        if track is None:
            continue
        # 前一条弹幕的尾部完全进入画面后，该轨道才能放下一条
        free_at[track] = at + width / SCROLL_SPEED
        span = (PLAY_RES_X + width) / SCROLL_SPEED
        y = round(track * row_height) + 2
        move = r"{\move(%d,%d,%d,%d)\c%s}" % (PLAY_RES_X, y, -round(width), y, _ass_color(color))
        events.append(f"Dialogue: 0,{_ass_time(at)},{_ass_time(at + span)},Dan,,0,0,0,,{move}{_escape(text)}")

    if not events and not sc_events:
        return None
    header = [
        "[Script Info]",
        "ScriptType: v4.00+",
        f"PlayResX: {PLAY_RES_X}",
        f"PlayResY: {PLAY_RES_Y}",
        "WrapStyle: 2",
        "ScaledBorderAndShadow: yes",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
        "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, "
        "Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        _style_line("Dan", font_size, 1, 1),
        # SC 用带内边距的底框样式（BorderStyle=3 时 Outline 即框内边距）
        _style_line("Sc", round(font_size * 0.85), 3, 10).replace("&H00000000,&H00000000",
                                                                "&H99202020,&H99202020"),
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    return "\n".join([*header, *sc_events, *events]) + "\n"
