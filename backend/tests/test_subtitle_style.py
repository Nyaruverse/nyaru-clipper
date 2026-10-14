import pytest
from pydantic import ValidationError

from app.arctime.subtitle_style import SubtitleStyle, TextStyle, layout_cues, render_ass, wrap_text
from app.services.subtitles import SubtitleSegment


@pytest.mark.parametrize('values', [dict(size=float('nan')), dict(size=True), dict(size=0), dict(outline=-1), dict(background_opacity=2), dict(color='red'), dict(font='Arial,evil'), dict(font='A\nB'), dict(font='{x}'), dict(margin=1081)])
def test_invalid_style_rejected(values):
    with pytest.raises(ValidationError):
        TextStyle(**values)


@pytest.mark.parametrize('version', [True, 1.0, '1', 2])
def test_version_requires_integer_one(version):
    with pytest.raises(ValidationError):
        SubtitleStyle(version=version)


def test_unicode_multiline_pairing_and_reference_canvas():
    original = [SubtitleSegment('1', 1.235, 2.999, '中文\n第二行')]
    translated = [SubtitleSegment('1', 1.235, 2.999, '日本語')]
    result = render_ass(original, translated, SubtitleStyle(), 1080, 1920)
    assert 'PlayResX: 608' in result
    assert 'PlayResY: 1080' in result
    assert '0:00:01.24,0:00:03.00,Original' in result
    assert '中文\\N第二行' in result
    assert '0:00:01.24,0:00:03.00,Translation' in result
    assert result.count('Dialogue:') == 2


@pytest.mark.parametrize('translated', [[], [SubtitleSegment('1', 0, 2, '訳')]])
def test_mismatched_translations_fail(translated):
    with pytest.raises(ValueError):
        render_ass([SubtitleSegment('1', 1, 2, '原文')], translated, SubtitleStyle(), 1920, 1080)


@pytest.mark.parametrize('text', ['null\x00byte', 'control\x85byte'])
def test_unsafe_text_fails_visibly(text):
    with pytest.raises(ValueError):
        render_ass([SubtitleSegment('1', 0, 1, text)], None, SubtitleStyle(), 1920, 1080)


def test_ass_syntax_is_literal_text():
    result = render_ass([SubtitleSegment('1', 0, 1, '{\\pos(0,0)} literal\\Ntext')], None, SubtitleStyle(), 1920, 1080)
    assert '\\{\\\u2060pos(0,0)\\} literal\\\u2060Ntext' in result


def test_empty_clip_produces_valid_ass():
    result = render_ass([], [], SubtitleStyle(), 1920, 1080)
    assert '[Events]' in result
    assert 'Dialogue:' not in result


def test_video_canvas_keeps_arctime_positions_and_fonts_in_bounds():
    cues = [SubtitleSegment('1', 0, 1, 'Hello')]
    result = render_ass(cues, cues, SubtitleStyle(), 640, 360, video_canvas=True)
    assert 'PlayResX: 640\nPlayResY: 360' in result
    assert 'Style: Original,Arial,16,' in result
    assert 'Style: Translation,Arial,13.3333,' in result
    assert r'\pos(320,328)' in result
    assert r'\pos(320,346.667)' in result


def test_background_is_independent_from_outline():
    style = SubtitleStyle(original=TextStyle(background_opacity=.5, background_color='#123456'))
    result = render_ass([SubtitleSegment('1', 0, 1, 'Hello')], None, style, 1920, 1080)
    assert '&H80563412' in result
    assert 'OriginalBackground' in result
    assert result.count('Dialogue:') == 2


def test_wrap_preserves_characters_and_explicit_newlines():
    assert wrap_text('中文AB\nC', 20, 88) == '中文\nAB\nC'
    assert wrap_text('e\u0301e', 20, 88) == 'e\u0301e'


@pytest.mark.parametrize('position', ['top', 'bottom'])
def test_bilingual_layout_reserves_multiline_height(position):
    style = SubtitleStyle(original=TextStyle(position=position, size=50, margin=40),
                          translation=TextStyle(position=position, size=40, margin=40))
    source, target, source_margin, target_margin = layout_cues('原\n文', '訳\n文', style, 1920)
    assert (source, target) == ('原\n文', '訳\n文')
    if position == 'bottom':
        assert source_margin == 144
        assert target_margin == 40
    else:
        assert source_margin == 40
        assert target_margin == 168


def test_text_and_box_use_identical_explicit_anchors():
    style = SubtitleStyle(original=TextStyle(background_opacity=1))
    document = render_ass([SubtitleSegment('1', 0, 1, 'Hello')], None, style, 1920, 1080)
    events = [line.split(',,')[-1] for line in document.splitlines() if line.startswith('Dialogue:')]
    assert events == [r'{\an2\pos(960,984)}Hello', r'{\an2\pos(960,984)}Hello']


@pytest.mark.parametrize('position', ['top', 'bottom'])
def test_vertical_overflow_rejected(position):
    style = SubtitleStyle(original=TextStyle(position=position, size=200, margin=40),
                          translation=TextStyle(position=position, size=200, margin=40))
    with pytest.raises(ValueError, match='fit'):
        render_ass([SubtitleSegment('1', 0, 1, 'line\n' * 3)], [SubtitleSegment('1', 0, 1, 'line\n' * 3)], style, 1920, 1080)
