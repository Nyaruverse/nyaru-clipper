from __future__ import annotations

import json
from datetime import timezone
from typing import TYPE_CHECKING

from pydantic import JsonValue
from sqlmodel import Session, select

from app.arctime.workstation_projection import project_artifacts
from app.arctime.migrated_selection import migrated_selection
from app.models_unified import UnifiedOperation
from app.models import Task

if TYPE_CHECKING:
    from app.arctime.unified_host import NativeHost


def job_view(host: NativeHost, task_id: str, *, include_segments: bool) -> dict[str, JsonValue]:
    with Session(host.engine) as session:
        rows = session.exec(select(UnifiedOperation).where(UnifiedOperation.task_id == task_id)
            .order_by(UnifiedOperation.created_at.desc())).all()
        primary = next((row for row in rows if row.kind in {'process_recording', 'process_live'}), None)
        latest = rows[0] if rows else None
        state = primary.state if primary else 'succeeded'
        started = primary.created_at.replace(tzinfo=timezone.utc).timestamp() if primary else 0.
        body = json.loads(primary.snapshot_json).get('input', {}) if primary else {}
        request = body.get('request', {})
        failure = primary.failure_code if primary else None
        task = session.get(Task, task_id)
        if primary is None and task is not None:
            started = task.created_at.replace(tzinfo=timezone.utc).timestamp()
    unavailable = False
    selection = None
    try:
        context = host.context(task_id)
        if context is not None and primary is None:
            selection = migrated_selection(host, context)
    except (ValueError, OSError):
        context, unavailable = None, True
    if context is not None:
        result = project_artifacts(context, include_segments=include_segments).model_dump(mode='json')
        try:
            document = host.documents.load(task_id, context.document(host.templates.load_defaults()))
        except (ValueError, OSError):
            result.update(state='failed', message='已登记字幕无法读取；原文件与记录已保留', error='document_source_unavailable',
                can_resume=False, operation_state=state, started_at=started)
            return result
        language = context.source.source_language
        if language in {'ja', 'zh'}:
            done = sum(bool(cue.translation.strip()) for cue in document.cues)
            total = len(document.cues)
            suffix = f'.saved.{language}-' + ('zh' if language == 'ja' else 'ja')
            result['bilingual_suffix'] = suffix if done else ''
            result['bilingual_segments'] = [{'id': cue.id, 'start_seconds': cue.start_seconds, 'end_seconds': cue.end_seconds,
                'text': cue.text + '\n' + cue.translation} for cue in document.cues] if include_segments and done else []
            result['bilingual_files'] = ['subtitles' + suffix + '.srt'] if done else []
            for index, clip in enumerate(result['clips'], start=1):
                clip['bilingual_subtitles'] = f'clip-{index:03d}{suffix}.srt' if done else None
                if done:
                    result['bilingual_files'].append(clip['bilingual_subtitles'])
            result['translation'] = {'state': 'completed' if done == total and total else 'partial' if done else 'not_started',
                'done': done, 'total': total, 'error': None, 'model': 'saved-document',
                'message': f'已保存译文 {done}/{total} 条'}
        if selection is not None:
            for clip, bounds in zip(result['clips'], selection.selection):
                clip.update(score=bounds.score, reasons=list(bounds.reasons))
    else:
        result = {'id': task_id, 'state': state, 'phase': state, 'message': '', 'error': None,
            'duration': None, 'has_source': False, 'segments': [], 'clips': [], 'bilingual_segments': [],
            'bilingual_files': [], 'language': request.get('language', 'auto'), 'bilingual_suffix': '',
            'translation': {'state': 'not_started', 'done': 0, 'total': 0, 'error': None, 'model': 'existing-result'}}
        from app.arctime.native_live import clips
        partial = clips(host, task_id)
        result['clips'] = [{'video': f'clip-{clip.clip_index:03d}.mp4', 'subtitles': f'clip-{clip.clip_index:03d}.srt',
            'start': clip.start, 'end': clip.end, 'score': None, 'reasons': []} for clip in partial]
        for item, clip in zip(result['clips'], partial, strict=True):
            if clip.bilingual_publication_id and clip.source_language in {'ja', 'zh'}:
                suffix = '.ja-zh' if clip.source_language == 'ja' else '.zh-ja'
                item['bilingual_subtitles'] = f'clip-{clip.clip_index:03d}{suffix}.srt'
                result['bilingual_files'].append(item['bilingual_subtitles'])
                result['bilingual_suffix'] = suffix
                result['translation']['state'] = 'partial'
    result.update(started_at=started, live=selection.live if selection is not None else bool(request.get('live')),
        mode=selection.processing_mode if selection is not None else 'saozi' if request.get('saozi') else
        'highlights' if request.get('highlights') else 'ranges', can_stop=task_id in host.live_events,
        can_resume=primary is not None and state in {'failed', 'interrupted', 'cancelled'} and not unavailable
            and failure != 'upload_incomplete_reselect_file', operation_state=state)
    if unavailable:
        result.update(state='failed', message='已登记结果无法读取；原文件与记录已保留', error='artifact_source_unavailable')
    elif state in {'queued', 'paused', 'running'}:
        result.update(state='preparing' if state == 'running' else state,
            message={'queued': '任务已排队', 'paused': '任务已暂停', 'running': '正在处理，进度由统一队列管理'}[state])
    elif context is not None:
        result.update(state='completed', message='视频与字幕已就绪，可以编辑' if state == 'succeeded' else
            '视频与字幕已保留；部分处理未完成，请查看队列', error=failure)
    else:
        result.update(state='failed' if state in {'failed', 'cancelled'} else 'interrupted',
            message='处理未完成；已有数据已保留，可在队列检查后恢复', error=failure)
    if latest is not None:
        result['latest_operation_state'] = latest.state
    return result
