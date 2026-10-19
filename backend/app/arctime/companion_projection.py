from __future__ import annotations

import time
import os
from dataclasses import asdict
from pathlib import Path
from typing import TYPE_CHECKING
from fastapi import HTTPException
from app.arctime import media, translation, workflow
from app.arctime.local_features_api import read_burns

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
    if os.name == "nt":
        state = ("completed" if job.get("state") == "completed" and
                 (not live or live.get("live") or live.get("state") == "translating")
                 else record.get("state", "interrupted"))
    else:
        state = "completed" if job.get("state") == "completed" else record.get("state", "interrupted")
    if not live and state not in {"completed", "failed", "cancelled"}:
        state = "interrupted"
    with manager.lock:
        active_burns = set(getattr(manager, "burning", set()))
    all_burns = read_burns(directory).get("clips", {})
    clips = []
    for index, item in enumerate(job.get("completed_clips", [])):
        selection = job.get("selection", [])[index]
        burns = {}
        for variant, entry in (all_burns.get(item["video"]) or {}).items():
            if isinstance(entry, dict) and entry.get("state") == "burning" and (job_id, item["video"], variant) not in active_burns:
                entry = {"state": "failed", "file": None, "error": "合成已中断，请重新生成"}
            burns[variant] = entry
        clips.append({"video": item["video"], "subtitles": item["subtitles"], **selection, "burns": burns})
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
    if translation_state == "completed":
        translation.ensure_zh_srt(directory)
        translated = manager.read_json(directory / "translation.json")
        artifacts = translated.get("artifacts", {})
    if translation_state != "not_started":
        try:
            # 纯译文 SRT（本地功能）也会登记进 artifacts，需并入合法集合（旧版行为，勿回退）
            zh_names = {name for name in artifacts if name.endswith(".zh.srt")}
            valid = set(artifacts) <= expected | zh_names and all(
                media.fingerprint(workflow._path(directory, name)) == checksum for name, checksum in artifacts.items())
            if translation_state == "completed":
                valid = valid and expected <= set(artifacts)
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
    zh_path = directory / "subtitles.zh.srt"
    zh_segments = ([asdict(cue) for cue in media.read_subtitles(zh_path)]
                   if include_segments and translation_state == "completed" and zh_path.is_file()
                   and not zh_path.is_symlink() and zh_path.read_text().strip() else [])
    default_message = "处理完成" if state == "completed" else "处理已中断，可恢复已下载任务"
    if state == "completed" and record.get("state") != "completed":
        record = {**record, "message": default_message, "error": None}
    return {"id": job_id, "state": state, "phase": job.get("state", state), "message": record.get("message", default_message),
            "error": record.get("error"), "started_at": record.get("started_at", directory.stat().st_mtime if directory.exists() else time.time()),
            "duration": job.get("duration"), "mode": "saozi" if job.get("saozi") or record.get("saozi") else "highlights" if job.get("highlight_count") else "ranges",
            "live": bool(job.get("live") or record.get("live")), "can_stop": bool(live and live.get("live") and not manager.stop_event.is_set()),
            "saozi_model": job.get("saozi_model"),
            'llm_provider': job.get('llm_provider', 'chatgpt' if str(job.get('saozi_model', '')).startswith('chatgpt:') else 'deepseek'),
            "capture_warning": job.get("capture_warning"), "discontinuities": job.get("discontinuities", []),
            "subtitle_template": job.get('subtitle_template'), "subtitle_style_error": job.get('subtitle_style_error'),
            "clips": clips, "segments": segments, "has_source": bool(job.get("video")),
            "language": job.get("asr", {}).get("language", "auto"), "bilingual_segments": bilingual_segments,
            "zh_segments": zh_segments,
            "bilingual_files": bilingual_files,
            "subtitle_export_busy": bool(live and live.get("state") == "subtitle_export"),
            "translation": {"state": translation_state, "error": translation_error, "done": translated.get("done", 0),
                            "total": translated.get("total", len(segments)),
                            "model": translated.get("identity", {}).get("model") or (live or {}).get("model") or job.get('saozi_model') or job.get('llm_model') or translation.MODEL,
                            "message": live.get("message") if live and translation_state == "translating" else None},
            "can_resume": not live and (state in {"failed", "interrupted", "cancelled"} or bool(job.get('subtitle_style_error'))) and (bool(job.get("video")) or bool(job.get("live")))}
