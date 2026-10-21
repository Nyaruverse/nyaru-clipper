from __future__ import annotations

import time
from dataclasses import asdict
from pathlib import Path
from typing import TYPE_CHECKING
from fastapi import HTTPException
from app.arctime import media, translation, workflow

if TYPE_CHECKING:
    from app.arctime.companion_manager import JobManager


def job_detail(manager: JobManager, job_id: str, *, include_segments: bool = True) -> dict:
    directory = manager.directory(job_id)
    with manager.lock:
        live = dict(manager.active) if manager.active and manager.active["id"] == job_id else None
        last = dict(manager.last) if manager.last and manager.last["id"] == job_id else None
    job_path = directory / "job.json"
    job = manager.read_json(job_path) if job_path.is_file() else {}
    saved = manager.read_json(directory / "gui.json")
    translated = manager.read_json(directory / "translation.json")
    if not job and not live and not last and not saved:
        raise HTTPException(404, "任务不存在")
    record = live or last or saved
    state = "completed" if job.get("state") == "completed" else record.get("state", "interrupted")
    if not live and state not in {"completed", "failed"}:
        state = "interrupted"
    clips = []
    for index, item in enumerate(job.get("completed_clips", [])):
        selection = job.get("selection", [])[index]
        clips.append({"video": item["video"], "subtitles": item["subtitles"], **selection})
    transcript = directory / "subtitles.srt"
    segments = [asdict(cue) for cue in media.read_subtitles(transcript)] if include_segments and transcript.is_file() and not transcript.is_symlink() and transcript.read_text().strip() else []
    translation_state = translated.get("state", "not_started")
    translation_error = translated.get("error")
    if live and (live.get("state") == "translating" or (live.get("live") and translation_state == "translating")):
        translation_state = "translating"
    elif translation_state == "translating":
        translation_state = "interrupted"
    if last and last.get("translation_error"):
        translation_state = "failed"
        translation_error = translation_error or last["translation_error"]
    expected = {"subtitles.ja-zh.srt"} | {Path(c["video"]).stem + ".ja-zh.srt" for c in job.get("completed_clips", [])}
    artifacts = translated.get("artifacts", {})
    bilingual_files = []
    if translation_state != "not_started":
        try:
            valid = set(artifacts) <= expected and all(
                media.fingerprint(workflow._path(directory, name)) == checksum for name, checksum in artifacts.items())
            if translation_state == "completed":
                valid = valid and set(artifacts) == expected
        except (OSError, ValueError):
            valid = False
        if valid:
            bilingual_files = sorted(artifacts)
        else:
            translation_state = "failed"
            translation_error = "双语字幕缺失或校验失败；原结果已保留，请检查任务"
    for clip in clips:
        name = Path(clip["video"]).stem + ".ja-zh.srt"
        clip["bilingual_subtitles"] = name if name in bilingual_files else None
    bilingual_path = directory / "subtitles.ja-zh.srt"
    bilingual_segments = ([asdict(cue) for cue in media.read_subtitles(bilingual_path)]
                          if include_segments and "subtitles.ja-zh.srt" in bilingual_files and bilingual_path.read_text().strip() else [])
    default_message = "处理完成" if state == "completed" else "处理已中断，可恢复已下载任务"
    if state == "completed" and record.get("state") != "completed":
        record = {**record, "message": default_message, "error": None}
    message = record.get("message", default_message)
    if job.get('capture_end_reason') == 'live_ended' and '直播已结束' not in message:
        message = '直播已结束；' + message
    return {"id": job_id, "state": state, "phase": job.get("state", state), "message": message,
            "error": record.get("error"), "started_at": record.get("started_at", directory.stat().st_mtime if directory.exists() else time.time()),
            "duration": job.get("duration"), "mode": "saozi" if job.get("saozi") or record.get("saozi") else "highlights" if job.get("highlight_count") else "ranges",
            "live": bool(job.get("live") or record.get("live")), "can_stop": bool(live and live.get("live") and not manager.stop_event.is_set()),
            "saozi_model": job.get("saozi_model"),
            'llm_provider': job.get('llm_provider', 'chatgpt' if str(job.get('saozi_model', '')).startswith('chatgpt:') else 'deepseek'),
            "capture_warning": job.get("capture_warning"), "discontinuities": job.get("discontinuities", []),
            "capture_end_reason": job.get("capture_end_reason"),
            "subtitle_template": job.get('subtitle_template'), "subtitle_style_error": job.get('subtitle_style_error'),
            "clips": clips, "segments": segments, "has_source": bool(job.get("video")),
            "language": job.get("asr", {}).get("language", "auto"), "bilingual_segments": bilingual_segments,
            "bilingual_files": bilingual_files,
            "subtitle_export_busy": bool(live and (live.get("state") == "subtitle_export" or live.get('auto_subtitle_export'))),
            "translation": {"state": translation_state, "error": translation_error, "done": translated.get("done", 0),
                            "total": translated.get("total", len(segments)),
                            "model": translated.get("identity", {}).get("model") or (live or {}).get("model") or job.get('saozi_model') or job.get('llm_model') or translation.MODEL,
                            "message": live.get("message") if live and translation_state == "translating" else None},
            "can_resume": not live and (state in {"failed", "interrupted"} or bool(job.get('subtitle_style_error'))) and (bool(job.get("video")) or bool(job.get("live")))}
