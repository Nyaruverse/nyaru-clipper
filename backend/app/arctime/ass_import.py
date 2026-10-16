import math
import re

from pydantic import BaseModel, ConfigDict, ValidationError

from app.arctime.subtitle_style import TextStyle


class ImportedStyle(BaseModel):
    model_config = ConfigDict(frozen=True)
    name: str
    style: TextStyle


class AssInspection(BaseModel):
    model_config = ConfigDict(frozen=True)
    styles: list[ImportedStyle]
    warnings: list[str]


def _color(value: str) -> tuple[str, float]:
    if re.fullmatch(r'&[Hh][0-9a-fA-F]{1,8}&?', value):
        number = int(value[2:].rstrip('&'), 16)
    elif re.fullmatch(r'-?\d{1,10}', value) and -(2 ** 31) <= int(value) <= 2 ** 32 - 1:
        number = int(value) & 0xFFFFFFFF
    else:
        raise ValueError('ASS 颜色无效，请使用标准 ASS 颜色值')
    return f'#{number & 255:02X}{(number >> 8) & 255:02X}{(number >> 16) & 255:02X}', 1 - (number >> 24) / 255


def inspect_ass(content: bytes) -> AssInspection:
    if len(content) > 1024 * 1024:
        raise ValueError('ASS 文件不能超过 1 MiB')
    try:
        text = content.decode('utf-16' if content.startswith((b'\xff\xfe', b'\xfe\xff')) else 'utf-8-sig')
    except UnicodeError:
        raise ValueError('ASS 编码无效，请从 ArcTime 导出 UTF-8 或 UTF-16 ASS') from None
    if '\x00' in text:
        raise ValueError('ASS 包含无效控制字符')
    section = ''
    resolution: dict[str, str] = {}
    fields: list[str] = []
    rows: list[dict[str, str]] = []
    warnings = ['只读取样式表；逐句定位、淡入淡出、动画、卡拉 OK 和正文内覆盖标签不作为模板导入。']
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith('[') and line.endswith(']'):
            section = line.casefold()
            continue
        key, separator, value = line.partition(':')
        if not separator or line.startswith(';'):
            continue
        key = key.strip().casefold()
        value = value.strip()
        if section == '[script info]' and key in {'playresx', 'playresy'}:
            resolution[key] = value
        if section == '[v4+ styles]':
            if key == 'format':
                fields = [field.strip().casefold() for field in value.split(',')]
                if len(set(fields)) != len(fields):
                    raise ValueError('ASS 样式字段重复')
            if key == 'style':
                values = [item.strip() for item in value.split(',')]
                if not fields or len(values) != len(fields) or not {'name', 'fontname', 'fontsize', 'primarycolour'} <= set(fields):
                    raise ValueError('ASS 样式表字段缺失或格式无效')
                rows.append(dict(zip(fields, values, strict=True)))
                if len(rows) > 256:
                    raise ValueError('ASS 样式不能超过 256 个')
    try:
        width, height = int(resolution['playresx']), int(resolution['playresy'])
        if not 1 <= width <= 32768 or not 1 <= height <= 32768:
            raise ValueError
    except (KeyError, ValueError):
        raise ValueError('ASS 缺少有效 PlayResX/PlayResY，请在 ArcTime 设置画面分辨率后导出') from None
    scale = 1080 / height
    styles: list[ImportedStyle] = []
    names: set[str] = set()
    for row in rows:
        name = row['name']
        if not name or len(name) > 100 or any(ord(char) < 32 for char in name):
            raise ValueError('ASS 样式名称无效')
        if name in names:
            raise ValueError('ASS 样式名称重复，请先重命名')
        names.add(name)
        def number(key: str, default: float) -> float:
            value = float(row.get(key, str(default)))
            if not math.isfinite(value):
                raise ValueError('ASS 样式数值必须为有限数')
            return value
        try:
            color, opacity = _color(row['primarycolour'])
            outline_color, outline_opacity = _color(row.get('outlinecolour', '&H00000000'))
            shadow_color, shadow_opacity = _color(row.get('backcolour', '&H00000000'))
            alignment = number('alignment', 2)
            border = number('borderstyle', 1)
            if alignment != int(alignment) or border not in {1, 3}:
                raise ValueError('ASS 对齐或边框类型不支持')
            style = TextStyle(font=row['fontname'], size=number('fontsize', 48) * scale,
                color=color, opacity=opacity, outline_color=outline_color,
                outline=number('outline', 2) * scale if border == 1 else 0.,
                shadow=number('shadow', 0) * scale, shadow_color=shadow_color,
                background_color=outline_color, background_opacity=outline_opacity if border == 3 else 0.,
                padding=number('outline', 0) * scale if border == 3 else 0.,
                bold=number('bold', 0) != 0, italic=number('italic', 0) != 0,
                underline=number('underline', 0) != 0, align=int(alignment),
                position='top' if alignment >= 7 else 'bottom', margin=number('marginv', 0) * scale,
                margin_left=number('marginl', 20 / scale) * scale,
                margin_right=number('marginr', 20 / scale) * scale,
                scale_x=number('scalex', 100), scale_y=number('scaley', 100),
                spacing=number('spacing', 0) * scale, rotation=number('angle', 0))
            if number('strikeout', 0) or outline_opacity != opacity or shadow_opacity != opacity or border == 3:
                warnings.append(f'「{name}」：删除线未导入；独立描边／阴影透明度及不透明底板将按本软件渲染方式近似。')
            if style.margin_left + style.margin_right >= width * scale:
                raise ValueError('左右边距超出画布')
        except (ValueError, ValidationError):
            raise ValueError(f'ASS 样式「{name}」有无效或超出支持范围的参数，请检查字体、颜色、字号、边距及缩放') from None
        styles.append(ImportedStyle(name=name, style=style))
    if not styles:
        raise ValueError('未找到 ASS V4+ 样式表')
    return AssInspection(styles=styles, warnings=warnings)
