from collections.abc import Sequence
from decimal import Decimal, ROUND_HALF_UP
import math
import re
import unicodedata
import regex
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.services.subtitles import SubtitleSegment


class OutlineLayer(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True, strict=True, allow_inf_nan=False)
    color: str = Field(pattern=r'^#[0-9A-Fa-f]{6}$')
    width: float = Field(ge=0, le=20)


class TextStyle(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True, strict=True, allow_inf_nan=False)
    font: str = Field(default='Arial', min_length=1, max_length=100)
    size: float = Field(default=48, ge=8, le=200)
    color: str = Field(default='#FFFFFF', pattern=r'^#[0-9A-Fa-f]{6}$')
    outline_color: str = Field(default='#000000', pattern=r'^#[0-9A-Fa-f]{6}$')
    outline: float = Field(default=2, ge=0, le=20)
    outline_layers: list[OutlineLayer] = Field(default_factory=list, max_length=2)
    background_color: str = Field(default='#000000', pattern=r'^#[0-9A-Fa-f]{6}$')
    background_opacity: float = Field(default=0, ge=0, le=1)
    position: Literal['top', 'bottom'] = 'bottom'
    margin: float = Field(default=96, ge=0, le=1080)
    margin_left: float = Field(default=20, ge=0, le=32768)
    margin_right: float = Field(default=20, ge=0, le=32768)

    bold: bool = False
    italic: bool = False
    underline: bool = False
    opacity: float = Field(default=1, ge=0, le=1)
    spacing: float = Field(default=0, ge=-10, le=100)
    line_height: float = Field(default=1.2, ge=.5, le=3)
    align: int = Field(default=2, ge=1, le=9)
    x: float | None = Field(default=None, ge=0, le=32768)
    y: float | None = Field(default=None, ge=0, le=32768)
    rotation: float = Field(default=0, ge=-360, le=360)
    scale_x: float = Field(default=100, ge=10, le=400)
    scale_y: float = Field(default=100, ge=10, le=400)
    shadow: float = Field(default=0, ge=0, le=20)
    shadow_color: str = Field(default='#000000', pattern=r'^#[0-9A-Fa-f]{6}$')
    padding: float = Field(default=0, ge=0, le=40)
    max_width: float = Field(default=100, ge=10, le=100)
    hidden: bool = False

    @field_validator('font')
    @classmethod
    def safe_font(cls, value: str) -> str:
        if not value.strip() or re.search(r'[,{}\\\x00-\x1f\x7f-\x9f]', value):
            raise ValueError('Font must be a plain font family name without ASS delimiters or controls.')
        return value


class SubtitleStyle(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True, strict=True)
    version: Literal[1] = 1
    original: TextStyle = Field(default_factory=TextStyle)
    translation: TextStyle = Field(default_factory=lambda: TextStyle(size=40, color='#FFFF00', margin=40))

    @field_validator('version', mode='before')
    @classmethod
    def integer_version(cls, value: int) -> int:
        if type(value) is not int:
            raise ValueError('Style version must be integer 1.')
        return value


def _color(value: str, opacity: float = 1) -> str:
    return f'&H{round(255 * (1 - opacity)):02X}{value[5:7]}{value[3:5]}{value[1:3]}'


def centiseconds(seconds: float) -> int:
    return int((Decimal(str(seconds)) * 100).quantize(Decimal('1'), rounding=ROUND_HALF_UP))


def _timestamp(seconds: float) -> str:
    ticks = centiseconds(seconds)
    hours, rest = divmod(ticks, 360000)
    minutes, rest = divmod(rest, 6000)
    secs, centis = divmod(rest, 100)
    return f'{hours}:{minutes:02}:{secs:02}.{centis:02}'


def _text(value: str) -> str:
    if re.search(r'[\x00-\x09\x0b\x0c\x0e-\x1f\x7f-\x9f]', value):
        raise ValueError('Subtitle contains unsupported control characters; edit the text before ASS export.')
    # A zero-width word joiner prevents literal backslashes becoming ASS escapes.
    escapes = {'\\': '\\\u2060', '{': r'\{', '}': r'\}', '\n': r'\N'}
    return ''.join(escapes.get(char, char) for char in value.replace('\r\n', '\n').replace('\r', '\n'))


def wrap_text(text: str, size: float, width: float) -> str:
    result = []
    used = 0.0
    for char in regex.findall(r'\X', text.replace('\r\n', '\n').replace('\r', '\n')):
        if char == '\n':
            result.append(char)
            used = 0.0
            continue
        advance = sum(size * 1.2 for point in char if not unicodedata.category(point).startswith('M'))
        if used and used + advance > width - 40:
            result.append('\n')
            used = 0.0
        result.append(char)
        used += advance
    return ''.join(result)


def alignment_for(style: TextStyle) -> int:
    return 8 if style.position == 'top' and style.align == 2 and style.x is None and style.y is None else style.align


def automatic_layout(items: Sequence[tuple[int, TextStyle, float]], canvas_width: float = 1920) -> list[float]:
    """Return reference-canvas anchors, reserving visible language blocks before checking fit."""
    heights = [((count - 1) * style.line_height + max(1.2, style.line_height)) * style.size * style.scale_y / 100 for count, style, _ in items]
    rows = [(alignment_for(style) - 1) // 3 for _, style, _ in items]
    margins = [style.margin for _, style, _ in items]
    centers = [540.0 for _ in items]
    if len(items) == 2:
        for index, (_, style, _) in enumerate(items):
            other = 1 - index
            if style.x is not None or style.y is not None:
                continue
            if rows[index] == rows[other] == 1:
                centers[index] += (-1 if index == 0 else 1) * (heights[other] + 8) / 2
            elif rows[index] == rows[other] and ((rows[index] == 0 and index == 0) or (rows[index] == 2 and index == 1)):
                margins[index] = max(margins[index], margins[other] + heights[other] + 8)
    anchors = [margins[i] if rows[i] == 2 else centers[i] if rows[i] == 1 else 1080 - margins[i] for i in range(len(items))]
    for i, (_, style, text_width) in enumerate(items):
        if style.x is not None or style.y is not None or style.hidden:
            continue
        border = max([style.outline, *(layer.width for layer in style.outline_layers)])
        extent = heights[i] + border + style.padding + style.shadow
        fits = (anchors[i] + extent <= 1060 if rows[i] == 2 else
                anchors[i] - extent >= 20 if rows[i] == 0 else
                anchors[i] - extent / 2 >= 20 and anchors[i] + extent / 2 <= 1060)
        column = (alignment_for(style) - 1) % 3
        x = style.margin_left if column == 0 else (canvas_width + style.margin_left - style.margin_right) / 2 if column == 1 else canvas_width - style.margin_right
        left = -text_width * column / 2
        edge = border + style.padding + style.shadow
        if style.rotation % 360:
            top = -heights[i] * (2 - rows[i]) / 2
            angle = math.radians(style.rotation)
            corners = [(x + dx * math.cos(angle) + dy * math.sin(angle), anchors[i] - dx * math.sin(angle) + dy * math.cos(angle))
                       for dx in (left - edge, left + text_width + edge) for dy in (top - edge, top + heights[i] + edge)]
            fits = all(0 <= px <= canvas_width and 20 <= py <= 1060 for px, py in corners)
        else:
            fits = fits and x + left - edge >= 0 and x + left + text_width + edge <= canvas_width
        if not fits:
            raise ValueError('Subtitle layout does not fit the canvas; reduce font size, margins, or text length.')
    return anchors


def layout_cues(original: str, translation: str | None, style: SubtitleStyle,
                width: float) -> tuple[str, str | None, float, float]:
    source = wrap_text(original, style.original.size, width)
    target = wrap_text(translation, style.translation.size, width) if translation is not None else None
    visible = [(name, text, item) for name, text, item in (('original', source, style.original), ('translation', target, style.translation)) if text and not item.hidden]
    anchors = automatic_layout([(len(text.split('\n')), item,
        max(sum(item.size * 1.2 for point in line if not unicodedata.category(point).startswith('M')) for line in text.split('\n')))
        for _, text, item in visible], width)
    margins = {name: anchor if alignment_for(item) >= 7 else 1080 - anchor for (name, _, item), anchor in zip(visible, anchors, strict=True)}
    original_margin = margins.get('original', style.original.margin)
    translation_margin = margins.get('translation', style.translation.margin)
    return source, target, original_margin, translation_margin


def render_ass(original: Sequence[SubtitleSegment], translated: Sequence[SubtitleSegment] | None,
               style: SubtitleStyle, width: int, height: int, *, video_canvas: bool = False) -> str:
    if width <= 0 or height <= 0:
        raise ValueError('Video dimensions must be positive.')
    if translated is not None and (len(original) != len(translated) or any(
        (a.start_seconds, a.end_seconds) != (b.start_seconds, b.end_seconds)
        for a, b in zip(original, translated, strict=True)
    )):
        raise ValueError('Translation cue count and times must exactly match original cues.')
    advanced = ('outline_layers', 'bold', 'italic', 'underline', 'opacity', 'spacing', 'line_height', 'align', 'x', 'y',
                'rotation', 'scale_x', 'scale_y', 'shadow', 'shadow_color', 'padding', 'max_width', 'hidden', 'margin_left', 'margin_right')
    defaults = TextStyle()
    if any(getattr(item, key) != getattr(defaults, key) for item in (style.original, style.translation) for key in advanced):
        from app.arctime.subtitle_document import Cue, SubtitleDocument
        from app.arctime.subtitle_render import render_document_ass
        cues = [Cue(id=f'cue-{index + 1:06d}', start_seconds=cue.start_seconds, end_seconds=cue.end_seconds,
                    text=cue.text, translation=translated[index].text if translated is not None else '')
                for index, cue in enumerate(original)]
        document = SubtitleDocument(source_fingerprint='0' * 64, revision=0, style=style, cues=cues,
                                    width=width, height=height, duration=max((c.end_seconds for c in cues), default=1), fps=25)
        return render_document_ass(document, translated is not None)
    canvas_width = round(1080 * width / height)
    layouts = [layout_cues(cue.text, translated[index].text if translated is not None else None, style, canvas_width)
               for index, cue in enumerate(original)]
    scale = height / 1080 if video_canvas else 1
    output_width, output_height = (width, height) if video_canvas else (canvas_width, 1080)
    lines = ['[Script Info]', 'ScriptType: v4.00+', f'PlayResX: {output_width}',
             f'PlayResY: {output_height}', 'WrapStyle: 0', 'ScaledBorderAndShadow: yes', '', '[V4+ Styles]',
             'Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding']
    languages = [('Original', original, style.original)]
    if translated is not None:
        languages.append(('Translation', translated, style.translation))
    events = []
    for name, cues, text_style in languages:
        alignment = 8 if text_style.position == 'top' else 2
        foreground = f'{_color(text_style.color)},{_color(text_style.color)},{_color(text_style.outline_color)},{_color(text_style.background_color, text_style.background_opacity)}'
        side_margin = round(20 * scale)
        outline, margin = text_style.outline * scale, round(text_style.margin * scale)
        size = text_style.size * scale
        suffix = f',0,0,0,0,100,100,0,0,1,{outline:g},0,{alignment},{side_margin},{side_margin},{margin},1'
        lines.append(f'Style: {name},{text_style.font},{size:g},{foreground}{suffix}')
        if text_style.background_opacity:
            background = _color(text_style.background_color, text_style.background_opacity)
            lines.append(f'Style: {name}Background,{text_style.font},{size:g},&HFFFFFFFF,&HFFFFFFFF,{background},{background},0,0,0,0,100,100,0,0,3,{outline:g},0,{alignment},{side_margin},{side_margin},{margin},1')
        for index, cue in enumerate(cues):
            if not math.isfinite(cue.start_seconds) or not math.isfinite(cue.end_seconds) or not 0 <= cue.start_seconds < cue.end_seconds:
                raise ValueError('Subtitle cue times must be finite, nonnegative and increasing.')
            timing = f'{_timestamp(cue.start_seconds)},{_timestamp(cue.end_seconds)}'
            source, target, original_margin, translation_margin = layouts[index]
            wrapped = source if name == 'Original' else target
            margin = original_margin if name == 'Original' else translation_margin
            y = margin * scale if text_style.position == 'top' else output_height - margin * scale
            text = f'{{\\an{alignment}\\pos({output_width / 2:g},{y:g})}}' + _text(wrapped or '')
            if text_style.background_opacity:
                events.append(f'Dialogue: 0,{timing},{name}Background,,0,0,0,,{text}')
            events.append(f'Dialogue: 1,{timing},{name},,0,0,0,,{text}')
    lines.extend(['', '[Events]', 'Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text', *events])
    return '\n'.join(lines) + '\n'
