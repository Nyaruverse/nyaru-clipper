from __future__ import annotations

import json
import platform
import subprocess
from pathlib import Path

from app.arctime import media
from app.arctime.subtitle_document import Cue, SubtitleDocument, clip_document
from app.arctime.subtitle_encoding import subtitle_ffmpeg
from app.arctime.subtitle_render import preview_png, render_document_ass
from app.arctime.subtitle_style import SubtitleStyle, TextStyle
from app.services.subtitles import SubtitleSegment, render_srt
from unification_fixtures import build_state


def build_media(root: Path) -> Path:
    root.mkdir(mode=0o700)
    contract_path = Path(__file__).parent / 'fixtures/unification/contract.json'
    contract = json.loads(contract_path.read_bytes())
    binary = subtitle_ffmpeg()
    commands: list[list[str]] = []

    def run(command: list[str]) -> None:
        commands.append(command)
        subprocess.run(command, check=True, capture_output=True, timeout=300)

    for speech in contract['media']['speech']:
        run(['say', '-v', speech['voice'], '-r', '160', '-o', str(root / f"{speech['language']}.aiff"), speech['text']])
    source = root / 'source.mp4'
    run([binary, '-v', 'error', '-nostdin', '-n', '-f', 'lavfi', '-i', 'color=c=0x202030:s=1280x720:r=30',
         '-i', str(root / 'ja.aiff'), '-i', str(root / 'zh.aiff'), '-filter_complex',
         '[1:a]adelay=1000:all=1[ja];[2:a]adelay=21000:all=1[zh];'
         '[ja][zh]amix=inputs=2:duration=longest,apad,atrim=end=150.033333333[a]',
         '-map', '0:v', '-map', '[a]', '-frames:v', '4501', '-t', '150.033333333',
         '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '18', '-g', '30', '-pix_fmt', 'yuv420p',
         '-c:a', 'aac', '-movflags', '+faststart', str(source)])
    live = root / 'live'
    live.mkdir()
    for index, duration in enumerate([20] * 7 + [7]):
        run([binary, '-v', 'error', '-nostdin', '-n', '-ss', str(index * 20), '-i', str(source),
             '-t', str(duration), '-c:v', 'copy', '-c:a', 'aac', '-af', 'asetpts=PTS-STARTPTS',
             str(live / f'chunk-{index:05d}.mp4')])
    (live / 'closed.csv').write_text(''.join(
        f'chunk-{index:05d}.mp4,{index * 20},{index * 20 + duration}\n'
        for index, duration in enumerate([20] * 7 + [7])), encoding='utf-8')
    media.write_json(live / 'discontinuity-fixture.json', {
        'status': 'fixture_only', 'missing_source_interval': [60, 65],
        'source_ranges': [[index * 20 + (5 if index >= 3 else 0),
                           index * 20 + duration + (5 if index >= 3 else 0)]
                          for index, duration in enumerate([20] * 7 + [7])],
    })
    style = SubtitleStyle(original=TextStyle(font='Arial', size=48., x=640., y=640.))
    original = SubtitleDocument(source_fingerprint=media.fingerprint(source), revision=0, style=style,
        width=1280, height=720, fps=30., duration=4501 / 30,
        cues=[Cue(id='cue-000001', start_seconds=2., end_seconds=4., text=contract['product']['text'])])
    document = clip_document(original, 1., 6.)
    expected = root / 'expected'
    expected.mkdir()
    media.write_json(expected / 'document.json', document.model_dump())
    (expected / 'subtitle.ass').write_text(render_document_ass(document, False), encoding='utf-8')
    (expected / 'subtitle.srt').write_text(render_srt([
        SubtitleSegment(cue.id, cue.start_seconds, cue.end_seconds, cue.text) for cue in document.cues]), encoding='utf-8')
    (expected / 'preview.png').write_bytes(preview_png(document, 1., False))
    run([binary, '-v', 'error', '-nostdin', '-n', '-ss', '1', '-i', str(source), '-t', '5',
         '-vf', f"ass=filename='{expected / 'subtitle.ass'}'", '-c:v', 'ffv1', '-an', str(expected / 'reference.mkv')])
    for frame in contract['product']['sample_frames']:
        run([binary, '-v', 'error', '-nostdin', '-n', '-i', str(expected / 'reference.mkv'),
             '-vf', f'select=eq(n\\,{frame}),format=rgb24', '-frames:v', '1', str(expected / f'frame-{frame:04d}.png')])
    build_state(root / 'state', source)
    font = Path('/System/Library/Fonts/Supplemental/Arial.ttf')
    if not font.is_file():
        message = 'Pinned Arial font file is unavailable; fixture bundle is incomplete'
        raise FileNotFoundError(message)
    version = subprocess.run([binary, '-version'], capture_output=True, text=True, check=True, timeout=10).stdout.splitlines()[0]
    files = {str(path.relative_to(root)): media.fingerprint(path) for path in sorted(root.rglob('*'))
             if path.is_file() and 'credentials' not in path.relative_to(root).parts}
    media.write_json(root / 'manifest.json', {
        'status': 'prepared_fixture', 'contract_sha256': media.fingerprint(contract_path),
        'platform': platform.platform(), 'ffmpeg': version, 'font': {'family': 'Arial', 'sha256': media.fingerprint(font)},
        'commands': [[part.replace(str(root), '<fixture>') for part in command] for command in commands],
        'files': files, 'speech_review': 'unknown', 'gpu_acceptance': 'not_run',
        'color_conversion': 'FFmpeg format=rgb24; 8-bit RGB; fixed ROI from contract',
        'reference_only': True,
    })
    return root
