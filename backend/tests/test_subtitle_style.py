import pytest
import json
from pathlib import Path
from pydantic import ValidationError

from app.arctime.subtitle_style import SubtitleStyle, TextStyle, layout_cues, render_ass, wrap_text
from app.services.subtitles import SubtitleSegment


@pytest.mark.parametrize('width, values', [(960, {'align': 1, 'margin_left': 2000}), (270, {'scale_x': 400}), (90, {})])
def test_automatic_horizontal_overflow_rejected_in_both_renderers(width, values):
    from app.arctime.subtitle_document import Cue, SubtitleDocument
    from app.arctime.subtitle_render import render_document_ass
    style = SubtitleStyle(original=TextStyle(size=200, **values))
    doc = SubtitleDocument(source_fingerprint='0' * 64, revision=0, width=width, height=540,
        duration=1, fps=25, style=style, cues=[Cue(id='cue-000001', start_seconds=0, end_seconds=1, text='W')])
    with pytest.raises(ValueError, match='fit'):
        render_ass([SubtitleSegment('1', 0, 1, 'W')], None, style, width, 540)
    with pytest.raises(ValueError, match='fit'):
        render_document_ass(doc, False)
    free = style.model_copy(update={'original': style.original.model_copy(update={'x': 40})})
    assert 'Dialogue:' in render_ass([SubtitleSegment('1', 0, 1, 'W')], None, free, width, 540)


@pytest.mark.parametrize('advanced', [{}, {'bold': True}, {'italic': True}, {'spacing': 1}, {'align': 5}, {'scale_y': 150}])
@pytest.mark.parametrize('position', ['top', 'bottom'])
def test_automatic_overflow_has_same_contract_for_style_and_document(advanced, position):
    from app.arctime.subtitle_document import Cue, SubtitleDocument
    from app.arctime.subtitle_render import render_document_ass
    text = '\n'.join(f'LINE {i:02d}' for i in range(1, 9))
    style = SubtitleStyle(original=TextStyle(size=120, margin=96, position=position, **advanced))
    document = SubtitleDocument(source_fingerprint='0' * 64, revision=0, width=960, height=540,
        duration=1, fps=25, style=style, cues=[Cue(id='cue-000001', start_seconds=0, end_seconds=1, text=text)])
    with pytest.raises(ValueError, match='fit'):
        render_ass([SubtitleSegment('1', 0, 1, text)], None, style, 960, 540)
    with pytest.raises(ValueError, match='fit'):
        render_document_ass(document, False)


def test_hidden_and_explicit_coordinates_do_not_acquire_automatic_overflow_rejection():
    text = 'LINE\n' * 15
    for advanced in [{'hidden': True}, {'x': 200}, {'y': 200}]:
        style = SubtitleStyle(original=TextStyle(size=120, **advanced))
        assert '[Events]' in render_ass([SubtitleSegment('1', 0, 1, text)], None, style, 960, 540)


def test_tight_line_spacing_still_reserves_glyph_height():
    style = SubtitleStyle(original=TextStyle(size=200, line_height=.5, margin=850))
    with pytest.raises(ValueError, match='fit'):
        render_ass([SubtitleSegment('1', 0, 1, 'A')], None, style, 960, 540)


def test_automatic_rotation_rejects_clipped_text_but_keeps_short_centered_text():
    style = SubtitleStyle(original=TextStyle(size=120, rotation=90, align=5))
    with pytest.raises(ValueError, match='fit'):
        render_ass([SubtitleSegment('1', 0, 1, 'ABCDEFGHIJKLM')], None, style, 960, 540)
    assert 'Dialogue:' in render_ass([SubtitleSegment('1', 0, 1, 'AB')], None, style, 960, 540)


@pytest.mark.parametrize('align, position', [(2, 'bottom'), (8, 'top'), (5, 'bottom')])
def test_document_override_bilingual_overflow_and_hidden_reservation(align, position):
    from app.arctime.subtitle_document import Cue, SubtitleDocument
    from app.arctime.subtitle_render import render_document_ass
    override = TextStyle(size=120, margin=96, align=align, position=position)
    cue = Cue(id='cue-000001', start_seconds=0, end_seconds=1, text='A\n' * 3 + 'A',
              translation='B\n' * 3 + 'B', original_style=override, translation_style=override)
    doc = SubtitleDocument(source_fingerprint='0' * 64, revision=0, width=960, height=540,
                           duration=1, fps=25, style=SubtitleStyle(), cues=[cue])
    assert 'Dialogue:' in render_document_ass(doc, False)
    with pytest.raises(ValueError, match='fit'):
        render_document_ass(doc, True)
    hidden = cue.model_copy(update={'translation_style': override.model_copy(update={'hidden': True})})
    assert render_document_ass(doc.model_copy(update={'cues': [hidden]}), True) == render_document_ass(doc, False)


@pytest.mark.parametrize('sample', json.loads((Path(__file__).parent / 'fixtures/grapheme-wrap.json').read_text()))
def test_grapheme_wrap_shared_samples(sample, tmp_path):
    from app.arctime.subtitle_render import _lines, render_document_ass
    from app.arctime.subtitle_document import Cue, SubtitleDocument
    expected = sample['lines']
    assert wrap_text(sample['text'], 20, 64).split('\n') == expected
    assert _lines(sample['text'], [], TextStyle(size=20), 64) == expected
    assert _lines(sample['text'], [], TextStyle(size=20), 41) == expected
    document = SubtitleDocument(source_fingerprint='a' * 64, revision=0, width=64, height=1080,
        duration=2, fps=25, style=SubtitleStyle(original=TextStyle(size=20, margin=0), translation=TextStyle(size=20, margin=0)),
        cues=[Cue(id='cue-000001', start_seconds=0, end_seconds=1, text='X', translation=sample['text'])])
    if sample['text'] == 'A👩‍💻B':
        with pytest.raises(ValueError, match='fit'):
            render_document_ass(document, True)
        document = document.model_copy(update={'width': 88})
    ass = render_document_ass(document, True)
    (tmp_path / 'grapheme.ass').write_text(ass)
    assert f'\\pos({document.width / 2:g},{1080 - (len(expected) * 24 + 8):g})' in ass


def test_grapheme_emphasis_keeps_codepoint_offsets_after_crlf():
    from app.arctime.subtitle_render import _lines
    from app.arctime.subtitle_document import Emphasis
    text = 'A\r\n👩‍💻B'
    spans = [Emphasis(start=4, end=5, color='#FF0000', bold=True)]
    lines = _lines(text, spans, TextStyle(size=20), 64)
    assert len(lines) == 3
    assert lines[1] == '{\\1c&HFFFFFF&\\b0}👩{\\1c&H0000FF&\\b1}‍{\\1c&HFFFFFF&\\b0}💻'


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
