import pytest

from app.arctime import subtitle_templates


FORMAT = 'Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding'


def ass_content(*, height=720, primary='&H800000FF', extra=''):
    return (f'[Script Info]\nPlayResX: 1280\nPlayResY: {height}\n[V4+ Styles]\nFormat: {FORMAT}\n'
            f'Style: 日文,Arial,32,{primary},&H00FFFFFF,&H00000000,&H0000FF00,-1,0,-1,0,100,110,2,5,1,2,1,8,30,40,50,1\n'
            f'{extra}').encode('utf-8-sig')


def test_reads_bgr_alpha_and_scales_script_pixels_to_1080():
    result = subtitle_templates.inspect_ass(ass_content())
    item = result.styles[0]
    assert item.name == '日文'
    assert item.style.size == 48
    assert item.style.color == '#FF0000'
    assert item.style.opacity == pytest.approx(127 / 255)
    assert item.style.outline == 3 and item.style.margin == 75
    assert item.style.bold and item.style.underline
    assert item.style.align == 8 and item.style.position == 'top'
    assert item.style.margin_left == 45 and item.style.margin_right == 60


def test_inspection_never_imports_dialogue_text_or_inline_effects():
    result = subtitle_templates.inspect_ass(ass_content(extra='[Events]\nDialogue: 0,0:00:00.00,0:00:01.00,日文,,0,0,0,,{\\pos(10,20)\\fad(200,200)}private words\n'))
    assert result.warnings
    assert 'private words' not in result.model_dump_json()


@pytest.mark.parametrize('content', [b'bad', ass_content(height=0), ass_content(primary='garbage'),
                                    ass_content().replace(b'Arial', b'{evil}'), b'x' * (1024 * 1024 + 1)],
                         ids=['not-ass', 'zero-resolution', 'bad-color', 'unsafe-font', 'too-large'])
def test_malformed_or_oversized_ass_is_rejected(content):
    with pytest.raises(ValueError):
        subtitle_templates.inspect_ass(content)


def test_reordered_fields_utf16_and_decimal_color():
    content = '[Script Info]\nPlayResX: 1920\nPlayResY: 1080\n[V4+ Styles]\nFormat: Fontname,Name,Fontsize,PrimaryColour,Alignment\nStyle: Arial,Main,50,255,2\n'
    parsed = subtitle_templates.inspect_ass(content.encode('utf-16'))
    assert parsed.styles[0].style.color == '#FF0000'
    assert parsed.styles[0].style.size == 50


def test_duplicate_style_names_are_rejected():
    content = ass_content()
    content += next(line for line in content.splitlines(keepends=True) if line.startswith(b'Style:'))
    with pytest.raises(ValueError, match='重复'):
        subtitle_templates.inspect_ass(content)
