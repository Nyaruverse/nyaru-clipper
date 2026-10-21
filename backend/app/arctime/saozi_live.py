from __future__ import annotations

import json
from pathlib import Path
from threading import Event
from typing import Callable

from app.arctime.local_asr import LocalASR
from app.arctime.saozi import SaoziSelector

from app.arctime import live_state, saozi
from app.arctime.live_capture import LiveCapture
from app.arctime.workflow import exclusive_lock
from app.arctime.subtitle_templates import StyleTemplate


def run_live(directory: Path, selector: SaoziSelector, adapter: LocalASR, stop: Event,
             progress: Callable[[str], None] | None, url: str | None = None,
             *, capture: LiveCapture | None = None,
             bilingual: Callable[[Path, bool], set[str] | None] | None = None,
             style_template: StyleTemplate | None = None,
             styled: Callable[[Path, dict, list[dict] | None], None] | None = None) -> dict:
    directory = directory.resolve()
    notify = progress or (lambda message: None)
    with exclusive_lock(directory / '.lock'):
        manifest = directory / 'job.json'
        if manifest.is_symlink():
            raise ValueError('直播任务路径无效')
        if manifest.exists():
            job = json.loads(manifest.read_text())
            live_state.verify(directory, job, adapter, selector)
            if url is not None:
                raise ValueError('恢复只处理已有录制，重新连接请创建新任务')
            if job['state'] == 'completed':
                if bilingual:
                    bilingual(directory, True)
                if styled:
                    styled(directory, job, None)
                return job
        else:
            job = {'version': 2, 'saozi': True, 'live': True, 'state': 'recording',
                   'asr': adapter.identity(), 'saozi_model': selector.model, 'duration': 0.,
                   'llm_provider': 'chatgpt' if selector.model.startswith('chatgpt:') else 'deepseek',
                   'llm_model': selector.model,
                   'saozi_prompt_sha256': live_state.digest(saozi.PROMPT),
                   'ranges': [], 'highlight_count': None, 'selection': [], 'completed_clips': [],
                   'artifacts': {}, 'chunks': [], 'discontinuities': []}
            if style_template:
                job['subtitle_template'] = style_template.model_dump()
                job['subtitle_template_sha256'] = live_state.digest(job['subtitle_template'])
            live_state.save(directory, job)
        recorder = capture or (LiveCapture(url, directory, stop) if url else None)

        clips_by_video = {clip['video']: clip for clip in job['completed_clips']}

        def publish(final: bool, added: list[dict] | None) -> None:
            clips_by_video.update((clip['video'], clip) for clip in added or [])
            translated = bilingual(directory, final) if bilingual else None
            if styled:
                changed = None if added is None else list({
                    **{clip['video']: clip for clip in added},
                    **{name: clips_by_video[name] for name in translated or set() if name in clips_by_video},
                }.values())
                styled(directory, job, changed)

        def choose(final):
            start = job['selection'][-1]['end'] if job['selection'] else 0.
            while start < job['duration']:
                notify(f'正在分析直播切点；已识别 {job["duration"]:.1f} 秒')
                clip = selector.choose(live_state.cues_for(job), start, job['duration'], final=final)
                if clip is None:
                    if final:
                        raise ValueError('直播尾段切点未完成')
                    break
                if (clip['start'] != start or not start < clip['end'] <= min(start + 120, job['duration'])
                        or (clip['end'] - start < 60 and not (final and clip['end'] == job['duration']))):
                    raise ValueError('直播切点无效')
                job['selection'].append(clip)
                live_state.save(directory, job)
                start = clip['end']
                previous = len(job['completed_clips'])
                live_state.export_pending(directory, job, notify)
                publish(False, job['completed_clips'][previous:])

        try:
            if job['chunks']:
                live_state.publish_transcript(directory, job)
            live_state.export_pending(directory, job, notify)
            if job['completed_clips']:
                clips_by_video.update((clip['video'], clip) for clip in job['completed_clips'])
                publish(False, None)
            paths = recorder.chunks() if recorder else LiveCapture.recorded(directory)
            seen = {c['path'] for c in job['chunks']}
            for path in paths:
                relative = str(path.relative_to(directory))
                if relative in seen:
                    continue
                if job['chunks'] and Path(job['chunks'][-1]['path']).parent != Path(relative).parent:
                    choose(True)
                    job['discontinuities'].append(job['duration'])
                    notify('直播发生断流；已单独保留断流前尾段，缺失区间无法恢复')
                live_state.recognize(directory, job, path, adapter)
                if job['chunks'][-1].get('video_decode_error'):
                    notify(job['capture_warning'])
                seen.add(relative)
                backlog = max(0, len(LiveCapture.recorded(directory)) - len(seen))
                notify(f'录制中；已识别 {job["duration"]:.1f} 秒，积压 {backlog} 个已关闭录制块')
                choose(False)
            if recorder:
                recorder.close()
                if getattr(recorder, 'end_reason', None) == 'live_ended':
                    notify('直播已结束，正在完成尾段翻译及导出')
                if recorder.error:
                    notify(recorder.error)
            choose(True)
            live_state.finalize(directory, job)
            publish(True, [])
            return job
        except BaseException:
            job['state'] = 'live_failed'
            live_state.save(directory, job)
            raise
        finally:
            if recorder:
                recorder.close()
                if getattr(recorder, 'end_reason', None):
                    job['capture_end_reason'] = recorder.end_reason
                if recorder.error:
                    job['capture_warning'] = '; '.join(dict.fromkeys(
                        warning for warning in [job.get('capture_warning'), recorder.error] if warning))
                if getattr(recorder, 'end_reason', None) or recorder.error:
                    live_state.save(directory, job)
