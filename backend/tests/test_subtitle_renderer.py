import os
from pathlib import Path
import subprocess
import shutil

import pytest

from app.arctime.subtitle_style import SubtitleStyle, TextStyle, render_ass
from app.services.subtitles import SubtitleSegment


FFMPEG = os.environ.get('SUBTITLE_TEST_FFMPEG') or (
    '/opt/homebrew/opt/ffmpeg@7/bin/ffmpeg' if Path('/opt/homebrew/opt/ffmpeg@7/bin/ffmpeg').is_file()
    else shutil.which('ffmpeg')
)


@pytest.fixture(scope='module', autouse=True)
def require_libass():
    if not FFMPEG or not shutil.which(FFMPEG):
        pytest.skip('Renderer prerequisite missing: install FFmpeg with libass or set SUBTITLE_TEST_FFMPEG.')
    filters = subprocess.run([FFMPEG, '-hide_banner', '-filters'], capture_output=True, text=True, check=True)
    if ' ass ' not in filters.stdout:
        pytest.skip('Renderer prerequisite missing: selected FFmpeg has no libass ass filter.')


def render(tmp_path, name, document):
    source = tmp_path / f'{name}.ass'
    source.write_text(document)
    target = tmp_path / f'{name}.rgb'
    result = subprocess.run([FFMPEG, '-v', 'error', '-f', 'lavfi', '-i', 'color=black:s=640x360:d=1',
                             '-vf', f'ass={source}', '-frames:v', '1', '-pix_fmt', 'rgb24', '-f', 'rawvideo', str(target)],
                            capture_output=True, check=True)
    (tmp_path / f'{name}.stderr').write_bytes(result.stderr)
    return target.read_bytes()


def test_word_joiner_preserves_literal_backslash_glyphs(tmp_path):
    style = SubtitleStyle(original=TextStyle(font='Courier New', size=96, margin=50))
    document = render_ass([SubtitleSegment('1', 0, 1, r'path\p\q')], None, style, 640, 360)
    rendered = render(tmp_path, 'encoded', document)
    literal = document.rsplit(',,', 1)[0] + ',,' + r'path\p\q' + '\n'
    expected = render(tmp_path, 'literal', literal)
    assert rendered == expected


def test_literal_control_letters_stay_on_one_line(tmp_path):
    style = SubtitleStyle(original=TextStyle(font='Courier New', size=96, margin=50))
    document = render_ass([SubtitleSegment('1', 0, 1, r'\N\n\h')], None, style, 640, 360)
    pixels = render(tmp_path, 'control-letters', document)
    rows = [y for y in range(360) if any(pixels[y * 640 * 3:(y + 1) * 640 * 3])]
    assert 15 < len(rows) < 35
    assert '\u2060' in document


def test_literal_control_prefix_renders_the_backslash_glyph(tmp_path):
    style = SubtitleStyle(original=TextStyle(font='Courier New', size=96, margin=50, outline=0))
    document = render_ass([SubtitleSegment('1', 0, 1, r'\N')], None, style, 640, 360)
    prefix = document.rsplit(',,', 1)[0] + ',,' + r'{\an7\pos(300,300)}'
    encoded_text = document.rsplit(',,', 1)[1].partition('}')[2]
    actual = render(tmp_path, 'escaped-control', prefix + encoded_text)
    reference = render(tmp_path, 'literal-slash', prefix + '\\\n')
    occupied = [i // 3 % 640 for i in range(0, len(reference), 3) if any(reference[i:i + 3])]
    assert occupied
    left, right = min(occupied), max(occupied)
    for y in range(360):
        start, stop = (y * 640 + left) * 3, (y * 640 + right + 1) * 3
        assert actual[start:stop] == reference[start:stop]


def test_bilingual_collision_does_not_detach_background(tmp_path):
    text = SubtitleSegment('1', 0, 1, 'Wide text')
    translated = TextStyle(size=60, margin=80, background_opacity=1, background_color='#FF0000', outline_color='#00FF00')
    single = render_ass([text], None, SubtitleStyle(original=translated), 640, 360)
    bilingual = render_ass([text], [text], SubtitleStyle(original=TextStyle(size=100, color='#000000', margin=80), translation=translated), 640, 360)
    reference = render(tmp_path, 'single', single)
    assert reference == render(tmp_path, 'bilingual', bilingual)
    colors = list(zip(reference[0::3], reference[1::3], reference[2::3]))
    assert any(r > 150 and g < 40 and b < 40 for r, g, b in colors)
    assert any(g > r + 40 and g > b + 40 for r, g, b in colors)


def test_wide_latin_has_clear_horizontal_edges(tmp_path):
    style = SubtitleStyle(original=TextStyle(font='Arial', size=200, margin=40))
    document = render_ass([SubtitleSegment('1', 0, 1, 'W' * 15)], None, style, 640, 360)
    pixels = render(tmp_path, 'wide-latin', document)
    occupied = [i // 3 % 640 for i in range(0, len(pixels), 3) if any(pixels[i:i + 3])]
    assert occupied
    assert min(occupied) > 5
    assert max(occupied) < 634
