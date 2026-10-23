from __future__ import annotations

import subprocess
import tempfile
import unicodedata
import regex
from pathlib import Path

from app.arctime.subtitle_document import Emphasis, SubtitleDocument
from app.arctime.subtitle_style import TextStyle, _color, _text, _timestamp, alignment_for, automatic_layout, centiseconds


def _lines(text: str, spans: list[Emphasis], style: TextStyle, width: float, matte: bool = False, background: bool = False, widths: list[float] | None = None) -> list[str]:
    lines = ['']
    used = 0.0
    formatting = None
    span_index = 0
    available = max(1, width * style.max_width / 100 - style.margin_left - style.margin_right - 2 * style.padding)
    for cluster in regex.finditer(r'\X', text):
        if cluster.group() in ('\r', '\n', '\r\n'):
            if widths is not None:
                widths.append(used)
            lines.append('')
            used = 0
            formatting = None
            continue
        advance = sum(max(0, style.size * 1.2 + style.spacing) * style.scale_x / 100
                      for char in cluster.group() if not unicodedata.category(char).startswith('M'))
        if used and used + advance > available:
            if widths is not None:
                widths.append(used)
            lines.append('')
            used = 0
            formatting = None
        for index, char in enumerate(cluster.group(), start=cluster.start()):
            while span_index < len(spans) and spans[span_index].end <= index:
                span_index += 1
            span = spans[span_index] if span_index < len(spans) and spans[span_index].start <= index else None
            color, bold = (span.color, span.bold) if span else (style.color, style.bold)
            if matte:
                color = '#FFFFFF'
            tag = ''
            if spans and formatting != (color, bold):
                tag = f'{{\\1c&H{color[5:7]}{color[3:5]}{color[1:3]}&\\b{int(bold)}}}'
                if background:
                    tag = f'{{\\b{int(bold)}}}'
                formatting = color, bold
            lines[-1] += tag + _text(char)
        used += advance
    if widths is not None:
        widths.append(used)
    return lines


def render_document_ass(document: SubtitleDocument, bilingual: bool, *, matte: bool = False) -> str:
    def paint(color: str, opacity: float = 1) -> str:
        return _color('#FFFFFF' if matte else color, opacity)
    width, height = document.width, document.height
    scale = height / 1080
    header = ['[Script Info]', 'ScriptType: v4.00+', f'PlayResX: {width}', f'PlayResY: {height}',
              'WrapStyle: 2', 'ScaledBorderAndShadow: yes', '', '[V4+ Styles]',
              'Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding']
    events = []
    for index, cue in enumerate(document.cues):
        original = cue.original_style or document.style.original
        translated = cue.translation_style or document.style.translation
        languages = [('Original', cue.text, cue.original_emphasis, original)]
        if bilingual:
            languages.append(('Translation', cue.translation, cue.translation_emphasis, translated))
        layouts = []
        metrics = []
        for name, text, emphasis, style in languages:
            if text and not style.hidden:
                widths: list[float] = []
                lines = _lines(text, emphasis, style, width / scale, matte, widths=widths)
                layouts.append((name, lines, style))
                metrics.append((len(lines), style, max(widths)))
        backgrounds = {name: _lines(text, emphasis, style, width / scale, matte, background=True)
                       for name, text, emphasis, style in languages if style.background_opacity}
        anchors = automatic_layout(metrics, width / scale)
        for (language, lines, style), anchor in zip(layouts, anchors, strict=True):
            name = f'{language}{index}'
            alignment = alignment_for(style)
            column, row = (alignment - 1) % 3, (alignment - 1) // 3
            x = style.x if style.x is not None else (style.margin_left * scale if column == 0 else (width + (style.margin_left - style.margin_right) * scale) / 2 if column == 1 else width - style.margin_right * scale)
            y = style.y if style.y is not None else anchor * scale
            size, step = style.size * scale, style.size * style.line_height * style.scale_y / 100 * scale
            color = paint(style.color, style.opacity)
            attributes = f'{-int(style.bold)},{-int(style.italic)},{-int(style.underline)},0,{style.scale_x:g},{style.scale_y:g},{style.spacing * scale:g},{style.rotation:g}'
            tail = f'{alignment},0,0,0,1'
            header.append(f'Style: {name},{style.font},{size:g},{color},{color},{paint(style.outline_color, style.opacity)},{paint(style.shadow_color, style.opacity)},{attributes},1,{style.outline * scale:g},{style.shadow * scale:g},{tail}')
            if style.background_opacity:
                background = paint(style.background_color, style.background_opacity)
                header.append(f'Style: {name}Background,{style.font},{size:g},&HFFFFFFFF,&HFFFFFFFF,{background},{background},{attributes},3,{(style.outline + style.padding) * scale:g},0,{tail}')
            timing = f'{_timestamp(cue.start_seconds)},{_timestamp(cue.end_seconds)}'
            for line_index, text in enumerate(lines):
                offset = line_index if row == 2 else line_index - (len(lines) - 1) / 2 if row == 1 else line_index - len(lines) + 1
                tags = f'{{\\an{alignment}\\pos({x:g},{y + offset * step:g})\\org({x:g},{y:g})\\frz{style.rotation:g}\\fscx{style.scale_x:g}\\fscy{style.scale_y:g}}}'
                if style.background_opacity:
                    # Emphasis retains metrics but must not paint glyphs on the background layer.
                    events.append(f'Dialogue: 0,{timing},{name}Background,,0,0,0,,{tags}{backgrounds[language][line_index]}')
                events.append(f'Dialogue: 1,{timing},{name},,0,0,0,,{tags}{text}')
    return '\n'.join([*header, '', '[Events]', 'Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text', *events, ''])


def preview_png(document: SubtitleDocument, time: float, bilingual: bool) -> bytes:
    from app.arctime.subtitle_encoding import has_libass, subtitle_ffmpeg
    binary = subtitle_ffmpeg()
    if not has_libass(binary):
        raise ValueError('当前 FFmpeg 不支持 libass 字幕预览')
    # Render only the active static cues at time zero, avoiding long seeks and animations.
    cues = [cue.model_copy(update={'start_seconds': 0., 'end_seconds': 1.}) for cue in document.cues
            if centiseconds(cue.start_seconds) <= time * 100 < centiseconds(cue.end_seconds)]
    frame = document.model_copy(update={'cues': cues})
    with tempfile.TemporaryDirectory(prefix='nyaru-subtitle-preview-') as temporary:
        working = Path(temporary)
        (working / 'subtitle.ass').write_text(render_document_ass(frame, bilingual), encoding='utf-8')
        (working / 'matte.ass').write_text(render_document_ass(frame, bilingual, matte=True), encoding='utf-8')
        # FFmpeg's ass alpha=1 squares translucent alpha; render a white matte instead.
        result = subprocess.run([binary, '-v', 'error', '-nostdin', '-f', 'lavfi', '-i',
            f'color=c=black:s={document.width}x{document.height}:r=1,format=rgba',
            '-filter_complex', 'split[color][matte];[color]ass=filename=subtitle.ass[rgb];'
            '[matte]ass=filename=matte.ass,format=gray[alpha];'
            '[rgb][alpha]alphamerge,unpremultiply=inplace=1', '-frames:v', '1', '-c:v', 'png',
            '-pix_fmt', 'rgba', '-f', 'image2pipe', '-'], cwd=working, capture_output=True, timeout=30, check=False)
        if result.returncode or not result.stdout.startswith(b'\x89PNG\r\n\x1a\n'):
            raise ValueError('字幕预览渲染失败，请检查字体与 FFmpeg')
        return result.stdout
