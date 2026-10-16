from __future__ import annotations

import hashlib
import json
import math
import os
import subprocess
import tempfile
from dataclasses import asdict
from pathlib import Path

from app.arctime import media, saozi
from app.arctime.workflow import _publish_text, write_manifest
from app.services.subtitles import SubtitleSegment, render_srt


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def save(directory, job):
    job['live_checkpoint_sha256'] = digest({k: job[k] for k in ('chunks', 'selection', 'duration')})
    write_manifest(directory, job)


def verify(directory, job, adapter, selector):
    if (job.get('subtitle_template') or job.get('subtitle_template_sha256')) and (
            job.get('subtitle_template_sha256') != digest(job.get('subtitle_template'))):
        raise ValueError('直播字幕模板快照已改变，请保留任务并检查')
    if (job.get('version') != 2 or not job.get('live') or job.get('asr') != adapter.identity()
            or job.get('saozi_model') != selector.model
            or job.get('saozi_prompt_sha256') != digest(saozi.PROMPT)):
        raise ValueError('直播恢复配置不一致')
    if job.get('live_checkpoint_sha256') != digest({k: job[k] for k in ('chunks', 'selection', 'duration')}):
        raise ValueError('直播检查点已改变')
    for chunk in job['chunks']:
        path = directory / chunk['path']
        if (path.is_symlink() or path.parent.is_symlink() or not path.resolve().is_relative_to(directory.resolve())
                or media.fingerprint(path) != chunk['sha256']):
            raise ValueError('录制块已改变')
    for clip in job['completed_clips']:
        for key in ('video', 'subtitles'):
            path = directory / clip[key]
            if path.name != clip[key] or path.is_symlink() or media.fingerprint(path) != clip[key + '_sha256']:
                raise ValueError('已输出切片发生变化，保留原文件')
    expected_text = transcript_text(job)
    for name, checksum in job['artifacts'].items():
        path = directory / name
        if (path.name != name or path.is_symlink() or (media.fingerprint(path) != checksum
                and path.read_text(encoding='utf-8') != expected_text.get(name))):
            raise ValueError('全局字幕已改变，保留原文件')
    if job.get('video') and (job['video'] != 'source.mp4' or (directory / 'source.mp4').is_symlink()
            or media.fingerprint(directory / 'source.mp4') != job['video_sha256']):
        raise ValueError('完整录像已改变')


def cues_for(job):
    return [SubtitleSegment(str(i), **row) for i, row in enumerate(
        (cue for chunk in job['chunks'] for cue in chunk['cues']))]


def recognize(directory, job, path, adapter):
    if path.is_symlink() or path.parent.is_symlink() or not path.resolve().is_relative_to(directory.resolve()):
        raise ValueError('录制块路径无效')
    length = media.probe_video(path)
    cache = path.parent / (path.stem + '-recognition')
    if cache.is_symlink():
        raise ValueError('识别缓存路径无效')
    cache.mkdir(exist_ok=True)
    try:
        cues = adapter.transcribe(path, cache, length)
    except ValueError as exc:
        if str(exc) != 'No speech was recognized; check the source audio and language':
            raise
        cues = []
    if any(not math.isfinite(c.start_seconds) or not math.isfinite(c.end_seconds)
           or not 0 <= c.start_seconds < c.end_seconds <= length or not c.text.strip() for c in cues):
        raise ValueError('直播字幕时间或内容无效')
    offset = job['duration']
    rows = [{'start_seconds': c.start_seconds + offset, 'end_seconds': c.end_seconds + offset,
             'text': c.text} for c in cues]
    job['chunks'].append({'path': str(path.relative_to(directory)), 'sha256': media.fingerprint(path),
                          'start': offset, 'duration': length, 'cues': rows})
    job['duration'] += length
    save(directory, job)
    publish_transcript(directory, job)


def transcript_text(job):
    cues = cues_for(job)
    return {'subtitles.srt': render_srt(cues), 'transcript.txt': '\n'.join(c.text for c in cues) + '\n',
            'transcript.json': json.dumps({'asr': job['asr'], 'segments': [asdict(c) for c in cues]},
                                         ensure_ascii=False, indent=2, allow_nan=False)}


def publish_transcript(directory, job):
    contents = transcript_text(job)
    for name, text in contents.items():
        if (directory / name).is_symlink():
            raise ValueError('全局字幕路径无效')
        _publish_text(directory / name, text)
    job.update(subtitles='subtitles.srt', artifacts={name: media.fingerprint(directory / name) for name in contents})
    save(directory, job)


def concatenate(directory, chunks, target):
    if target.is_symlink():
        raise ValueError('合并录像路径无效')
    with tempfile.TemporaryDirectory(prefix='.live-merge-', dir=directory) as work:
        work = Path(work)
        listing = work / 'inputs.txt'
        listing.write_text(''.join("file '" + str((directory / c['path']).resolve()).replace("'", "'\\''") + "'\n" for c in chunks))
        output = work / 'source.mp4'
        result = subprocess.run([media.tool_path('ffmpeg'), '-nostdin', '-v', 'error', '-f', 'concat',
                                 '-safe', '0', '-i', str(listing), '-c', 'copy', '-movflags', '+faststart', str(output)],
                                capture_output=True, timeout=600, check=False)
        if result.returncode:
            raise ValueError('合并已关闭录制块失败，原文件已保留')
        actual = media.probe_video(output)
        expected = sum(c['duration'] for c in chunks)
        if abs(actual - expected) > max(.5, expected * .01):
            raise ValueError('合并录像时间轴不一致，原文件已保留')
        os.replace(output, target)


def export_pending(directory, job, notify):
    cues = cues_for(job)
    pending = job['selection'][len(job['completed_clips']):]
    if not pending:
        return
    source = directory / '.live-buffer.mp4'
    chunks = [chunk for chunk in job['chunks'] if chunk['start'] + chunk['duration'] > pending[0]['start']
              and chunk['start'] < pending[-1]['end']]
    offset = chunks[0]['start']
    local_cues = media.clip_subtitles(cues, offset, chunks[-1]['start'] + chunks[-1]['duration'])
    concatenate(directory, chunks, source)
    try:
        for clip in pending:
            index = len(job['completed_clips']) + 1
            target = directory / f'clip-{index:03d}.mp4'
            subtitle = target.with_suffix('.srt')
            if target.is_symlink() or subtitle.is_symlink():
                raise ValueError('切片路径无效')
            if target.exists():
                expected = render_srt(media.clip_subtitles(cues, clip['start'], clip['end']))
                length = clip['end'] - clip['start']
                if (not subtitle.is_file() or subtitle.read_text() != expected
                        or abs(media.probe_video(target) - length) > max(.5, length * .05)):
                    raise ValueError('已发布切片与检查点不一致，保留原文件')
            else:
                media.export_clip(source, target, clip['start'] - offset, clip['end'] - offset, local_cues)
            job['completed_clips'].append({'video': target.name, 'subtitles': subtitle.name,
                'video_sha256': media.fingerprint(target), 'subtitles_sha256': media.fingerprint(subtitle)})
            save(directory, job)
            notify(f'直播切片 {index} 已导出；已识别 {job["duration"]:.1f} 秒')
    finally:
        source.unlink(missing_ok=True)


def finalize(directory, job):
    if not job['chunks']:
        raise ValueError('没有可处理的已关闭直播录制块')
    source = directory / 'source.mp4'
    if source.is_symlink():
        raise ValueError('完整录像路径无效')
    if not source.exists():
        concatenate(directory, job['chunks'], source)
    elif abs(media.probe_video(source) - job['duration']) > max(.5, job['duration'] * .01):
        raise ValueError('已保存完整录像时间轴不一致')
    publish_transcript(directory, job)
    job.update(video=source.name, video_sha256=media.fingerprint(source), subtitles='subtitles.srt',
        artifacts={name: media.fingerprint(directory / name) for name in ('subtitles.srt', 'transcript.txt', 'transcript.json')},
        state='completed')
    save(directory, job)
