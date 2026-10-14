from __future__ import annotations

import json
import re
import subprocess
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from pathlib import Path

from fastapi import HTTPException
from pydantic import SecretStr
from app.arctime import media, translation, workflow
from app.arctime.local_asr import LocalASR
from app.arctime.companion_models import JobInput, validated_api_key
from app.arctime.subtitle_exports import export_artifact


class JobManager:
    def __init__(self, root: Path, model: Path, threads: int):
        self.root = root.expanduser().resolve()
        self.model = model
        self.threads = threads
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="local-companion")
        self.lock = threading.Lock()
        self.active: dict | None = None
        self.last: dict | None = None
        self.api_key: SecretStr | None = None
        self.translation_model = translation.MODEL
        self.config_path = self.root / "config.json"
        self.config_error: str | None = None
        try:
            if self.config_path.is_symlink():
                raise ValueError("配置文件不能是符号链接")
            if self.config_path.exists():
                if self.config_path.stat().st_size > 16384:
                    raise ValueError("配置文件过大")
                config = json.loads(self.config_path.read_text(encoding="utf-8"))
                if not isinstance(config, dict) or "deepseek_api_key" not in config:
                    raise ValueError("配置格式无效")
                if config["deepseek_api_key"] != "":
                    self.api_key = validated_api_key(config["deepseek_api_key"])
                selected_model = config.get("deepseek_model", translation.MODEL)
                if selected_model not in translation.MODELS:
                    raise ValueError("翻译模型无效")
                self.translation_model = selected_model
        except (OSError, ValueError, UnicodeError):
            self.config_error = "无法读取翻译配置；请检查 runs/config.json 或重新保存 Key／模型"

    def directory(self, job_id: str) -> Path:
        path = self.root / job_id
        if not re.fullmatch(r"[0-9a-f]{12}", job_id) or path.is_symlink():
            raise HTTPException(404, "任务不存在")
        return path

    def submit(self, request: JobInput | None, job_id: str | None = None) -> str:
        with self.lock:
            if self.active:
                raise HTTPException(409, "已有任务正在处理，请等待完成后再开始")
            job_id = job_id or uuid.uuid4().hex[:12]
            self.active = {"id": job_id, "state": "preparing", "message": "正在检查本地环境", "started_at": time.time(), "error": None}
            self.executor.submit(self.run, job_id, request)
        return job_id

    def submit_translation(self, job_id: str) -> str:
        record = self.detail(job_id)
        if record["state"] != "completed":
            raise HTTPException(409, "请等待视频任务完成后再生成双语字幕")
        with self.lock:
            if self.active:
                raise HTTPException(409, "已有任务正在处理，请等待完成")
            if self.config_error:
                raise HTTPException(409, "请先修复翻译配置，再生成双语字幕")
            if not self.api_key:
                raise HTTPException(409, "请先输入 DeepSeek API Key")
            if self.last and self.last["id"] == job_id:
                self.last = None
            model = record["translation"]["model"] if record["translation"]["state"] != "not_started" else self.translation_model
            self.active = {"id": job_id, "state": "translating", "message": "准备日译中", "error": None, "model": model}
            self.executor.submit(self.run_translation, job_id, self.api_key, model)
        return job_id

    def run_translation(self, job_id: str, key: SecretStr, model: str):
        def progress(message: str):
            with self.lock:
                self.active["message"] = message
        try:
            translation.translate_run(self.directory(job_id), key, progress=progress, model=model)
        except Exception:
            with self.lock:
                self.active["translation_error"] = "翻译未完成；检查字幕、API Key 或网络后重试，原结果已保留"
        finally:
            with self.lock:
                self.last = self.active
                self.active = None

    def update(self, state: str, message: str, error: str | None = None):
        with self.lock:
            self.active.update(state=state, message=message, error=error)
            record = dict(self.active)
        directory = self.directory(record["id"])
        if state == "failed":
            directory.mkdir(mode=0o700, exist_ok=True)
        if directory.is_dir():
            media.write_json(directory / "gui.json", record)

    def run(self, job_id: str, request: JobInput | None):
        try:
            directory = self.directory(job_id)
            if request:
                adapter = LocalASR(self.model, request.language, self.threads)
                ranges = [(media.parse_time(start), media.parse_time(end)) for start, end in request.ranges]
                directory = workflow.create_run(request.url, self.root, ranges, request.highlights, adapter, run_id=job_id,
                                                progress=lambda message: self.update("downloading", message))
            else:
                adapter = None

            def progress(message: str):
                stage = json.loads((directory / "job.json").read_text())["state"]
                self.update(stage, message)

            job = workflow.resume_run(directory, adapter, progress=progress)
            message = f"处理完成，已导出 {len(job['completed_clips'])} 个切片"
            if not job["completed_clips"]:
                message = "未发现达到阈值的高光；完整视频和字幕已保留"
            self.update("completed", message)
        except Exception as exc:
            error = "外部工具执行超时，请重试；已完成结果会保留" if isinstance(exc, subprocess.TimeoutExpired) else str(exc)
            self.update("failed", "处理失败", error)
        finally:
            with self.lock:
                self.last = self.active
                self.active = None

    def detail(self, job_id: str, *, include_segments: bool = True) -> dict:
        directory = self.directory(job_id)
        with self.lock:
            live = dict(self.active) if self.active and self.active["id"] == job_id else None
            last = dict(self.last) if self.last and self.last["id"] == job_id else None
        job_path = directory / "job.json"
        job = self.read_json(job_path) if job_path.is_file() else {}
        saved = self.read_json(directory / "gui.json")
        translated = self.read_json(directory / "translation.json")
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
        segments = [asdict(cue) for cue in media.read_subtitles(transcript)] if include_segments and transcript.is_file() and not transcript.is_symlink() else []
        translation_state = translated.get("state", "not_started")
        translation_error = translated.get("error")
        if live and live.get("state") == "translating":
            translation_state = "translating"
        elif translation_state == "translating":
            translation_state = "interrupted"
        if last and last.get("translation_error"):
            translation_state = "failed"
            translation_error = translation_error or last["translation_error"]
        if translation_state == "completed":
            expected = {"subtitles.ja-zh.srt"} | {Path(c["video"]).stem + ".ja-zh.srt" for c in job.get("completed_clips", [])}
            artifacts = translated.get("artifacts", {})
            try:
                valid = set(artifacts) == expected and all(
                    media.fingerprint(workflow._path(directory, name)) == artifacts[name] for name in expected)
            except (OSError, ValueError):
                valid = False
            if not valid:
                translation_state = "failed"
                translation_error = "双语字幕缺失或校验失败；原结果已保留，请检查任务"
        bilingual_path = directory / "subtitles.ja-zh.srt"
        bilingual_segments = ([asdict(cue) for cue in media.read_subtitles(bilingual_path)]
                              if include_segments and translation_state == "completed" and bilingual_path.is_file() and not bilingual_path.is_symlink() else [])
        default_message = "处理完成" if state == "completed" else "处理已中断，可恢复已下载任务"
        if state == "completed" and record.get("state") != "completed":
            record = {**record, "message": default_message, "error": None}
        return {"id": job_id, "state": state, "phase": job.get("state", state), "message": record.get("message", default_message),
                "error": record.get("error"), "started_at": record.get("started_at", directory.stat().st_mtime if directory.exists() else time.time()),
                "duration": job.get("duration"), "mode": "highlights" if job.get("highlight_count") else "ranges",
                "clips": clips, "segments": segments, "has_source": bool(job.get("video")),
                "language": job.get("asr", {}).get("language", "auto"), "bilingual_segments": bilingual_segments,
                "subtitle_export_busy": bool(live and live.get("state") == "subtitle_export"),
                "translation": {"state": translation_state, "error": translation_error, "done": translated.get("done", 0),
                                "total": translated.get("total", len(segments)),
                                "model": translated.get("identity", {}).get("model") or (live or {}).get("model") or self.translation_model,
                                "message": live.get("message") if live and live.get("state") == "translating" else None},
                "can_resume": not live and state in {"failed", "interrupted"} and bool(job.get("video"))}

    @staticmethod
    def read_json(path: Path) -> dict:
        if path.is_symlink():
            raise HTTPException(404, "无效任务文件")
        try:
            value = json.loads(path.read_text())
            return value if isinstance(value, dict) else {}
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def artifact(self, job_id: str, name: str) -> Path:
        directory = self.directory(job_id)
        if re.fullmatch(r"styled-[0-9a-f]{20}\.(ass|mp4|zip)", name):
            return export_artifact(directory, name)
        job = self.read_json(directory / "job.json")
        allowed = set(job.get("artifacts", {}))
        if job.get("video"):
            allowed.add(job["video"])
        for clip in job.get("completed_clips", []):
            allowed.update((clip["video"], clip["subtitles"]))
        translated = self.read_json(directory / "translation.json")
        if translated.get("state") == "completed":
            bilingual_names = {"subtitles.ja-zh.srt"} | {Path(clip["video"]).stem + ".ja-zh.srt" for clip in job.get("completed_clips", [])}
            allowed.update(bilingual_names & set(translated.get("artifacts", {})))
        path = directory / name
        if name not in allowed or Path(name).name != name or path.is_symlink() or not path.is_file():
            raise HTTPException(404, "结果文件不存在")
        return path
