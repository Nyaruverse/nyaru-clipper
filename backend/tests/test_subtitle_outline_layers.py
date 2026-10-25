from pathlib import Path

import pytest
from pydantic import ValidationError

from app.arctime.subtitle_document import Cue, SubtitleDocument
from app.arctime.subtitle_render import render_document_ass
from app.arctime.subtitle_style import SubtitleStyle, TextStyle
from test_subtitle_renderer import render


def test_multiple_outline_colors_survive_real_libass_rendering(tmp_path: Path):
    style = TextStyle(size=120, outline=3, outline_color='#00FF00',
        outline_layers=[{'color': '#FF0000', 'width': 10}])
    document = SubtitleDocument(source_fingerprint='a' * 64, revision=0,
        width=640, height=360, duration=1, fps=25, style=SubtitleStyle(original=style),
        cues=[Cue(id='cue-000001', start_seconds=0, end_seconds=1, text='AB')])

    pixels = render(tmp_path, 'layered', render_document_ass(document, False))

    colors = list(zip(pixels[0::3], pixels[1::3], pixels[2::3]))
    assert any(r > 150 and g < 50 and b < 50 for r, g, b in colors)
    assert any(g > 150 and r < 50 and b < 50 for r, g, b in colors)
    assert any(min(r, g, b) > 200 for r, g, b in colors)


def test_old_style_without_extra_outlines_remains_readable():
    old = TextStyle().model_dump()
    old.pop('outline_layers', None)

    loaded = TextStyle.model_validate(old)

    assert loaded.outline_layers == []
    assert loaded.outline == 2


@pytest.mark.parametrize('layers', [
    [{'color': '#FFFFFF', 'width': 2}] * 3,
    [{'color': '#FFFFFF', 'width': float('nan')}],
    [{'color': '#FFFFFF', 'width': -1}],
    [{'color': 'invalid', 'width': 2}],
])
def test_extra_outline_input_is_bounded(layers):
    with pytest.raises(ValidationError):
        TextStyle(outline_layers=layers)
