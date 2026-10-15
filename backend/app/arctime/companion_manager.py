from __future__ import annotations

import json
import re
import subprocess
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fastapi import HTTPException
from pydantic import SecretStr
from app.arctime import companion_llm, media, translation, workflow
from app.arctime.chatgpt_auth import ChatGPTAuth
from app.arctime.local_asr import LocalASR
from app.arctime.companion_models import JobInput, validated_api_key
from app.arctime.subtitle_exports import export_artifact
from app.arctime.companion_projection import job_detail


class JobManager:
    def __init__(self, root: Path, model: Path, threads: int):
        self.root = root.expanduser().resolve()
        self.model = model
        self.threads = threads
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="local-companion")
        self.lock = threading.Lock()
        self.active: dict | None = None
        self.last: dict | None = None
        self.stop_event = threading.Event()
        self.api_key: SecretStr | None = None
        self.translation_model = translation.MODEL
        self.llm_provider = 'deepseek'
        self.chatgpt_model = ''
        self.chatgpt = ChatGPTAuth(self.root)
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
                provider = config.get('llm_provider', 'deepseek')
                if provider not in {'deepseek', 'chatgpt'}:
                    raise ValueError('供应商配置无效')
                self.llm_provider = provider
                chatgpt_model = config.get('chatgpt_model', '')
                if not isinstance(chatgpt_model, str) or (chatgpt_model and not re.fullmatch(r'[A-Za-z0-9._-]{1,128}', chatgpt_model)):
                    raise ValueError('订阅模型配置无效')
                self.chatgpt_model = chatgpt_model
        except (OSError, ValueError, UnicodeError):
            self.config_error = "无法读取翻译配置；请检查 runs/config.json 或重新保存 Key／模型"

    def directory(self, job_id: str) -> Path:
        path = self.root / job_id
        if not re.fullmatch(r"[0-9a-f]{12}", job_id) or path.is_symlink():
            raise HTTPException(404, "任务不存在")
        return path

    def submit(self, request: JobInput | None, job_id: str | None = None, *, deferred: bool = False) -> str:
        with self.lock:
            if self.active:
                raise HTTPException(409, "已有任务正在处理，请等待完成后再开始")
            job_id = job_id or uuid.uuid4().hex[:12]
            saved = self.read_json(self.directory(job_id) / "job.json")
            saozi = bool(request.saozi if request else saved.get("saozi"))
            model = saved.get('saozi_model') or saved.get('llm_model') or (
                companion_llm.selected_model(self) if request is not None else translation.MODEL)
            try:
                key = companion_llm.require_key(self, model) if saozi else self.api_key
            except ValueError as exc:
                raise HTTPException(409, str(exc)) from None
            self.stop_event.clear()
            self.active = {"id": job_id, "state": "uploading" if deferred else "preparing",
                           "message": "正在导入录像" if deferred else "正在检查本地环境", "started_at": time.time(),
                           "error": None, "live": bool(request.live if request else False), "saozi": saozi,
                           'model': model, 'llm_provider': 'chatgpt' if model.startswith('chatgpt:') else 'deepseek'}
            if not deferred:
                self.executor.submit(self.run, job_id, request, key, model)
        return job_id

    def stop(self, job_id: str) -> None:
        with self.lock:
            if not self.active or self.active["id"] != job_id or not self.active.get("live"):
                raise HTTPException(409, "没有正在录制的臊子直播任务")
            self.stop_event.set()
            self.active["message"] = "正在停止录制并处理剩余内容"

    def submit_translation(self, job_id: str) -> str:
        record = self.detail(job_id)
        if record["state"] != "completed":
            raise HTTPException(409, "请等待视频任务完成后再生成双语字幕")
        with self.lock:
            if self.active:
                raise HTTPException(409, "已有任务正在处理，请等待完成")
            saved = self.read_json(self.directory(job_id) / 'job.json')
            model = (record['translation']['model'] if record['translation']['state'] != 'not_started'
                     else saved.get('saozi_model') or saved.get('llm_model') or translation.MODEL)
            try:
                key = companion_llm.require_key(self, model)
            except ValueError as exc:
                raise HTTPException(409, str(exc)) from None
            if self.last and self.last["id"] == job_id:
                self.last = None
            self.active = {"id": job_id, "state": "translating", "message": "准备日译中", "error": None, "model": model}
            self.executor.submit(self.run_translation, job_id, key, model)
        return job_id

    def run_translation(self, job_id: str, key: SecretStr, model: str):
        def progress(message: str):
            with self.lock:
                self.active["message"] = message
        try:
            directory = self.directory(job_id)
            request_json = companion_llm.requester(self, model)
            options = {'request_json': request_json} if request_json is not None else {}
            if self.read_json(directory / "job.json").get("saozi"):
                from app.arctime.saozi_translation import translate
                translate(directory, key, progress=progress, model=model, **options)
            else:
                translation.translate_run(directory, key, progress=progress, model=model, **options)
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

    def run(self, job_id: str, request: JobInput | None, key: SecretStr | None = None,
            model: str | None = None, local_source: Path | None = None):
        try:
            directory = self.directory(job_id)
            saved = self.read_json(directory / "job.json")
            is_saozi = bool(request.saozi if request else saved.get("saozi"))
            selected = model or saved.get('saozi_model') or saved.get('llm_model') or (
                companion_llm.selected_model(self) if request is not None else translation.MODEL)
            request_json = companion_llm.requester(self, selected) if is_saozi else None
            options = {'request_json': request_json} if request_json is not None else {}
            selector = None
            if is_saozi:
                from app.arctime.saozi import SaoziSelector
                if key is None:
                    raise ValueError("臊子需要 DeepSeek API Key")
                selector = SaoziSelector(key, selected, **options)
            translation_failed = False
            def bilingual(path: Path, final: bool, *, locked: bool = True):
                nonlocal translation_failed
                if translation_failed and not final:
                    return
                from app.arctime.saozi_translation import translate
                def notify(message: str):
                    with self.lock:
                        self.active["message"] = message
                try:
                    translate(path, key, model=selector.model, final=final, locked=locked, progress=notify, **options)
                    translation_failed = False
                    with self.lock:
                        self.active.pop("translation_error", None)
                except (ValueError, OSError):
                    translation_failed = True
                    with self.lock:
                        self.active["translation_error"] = "双语字幕未完成；原文切片已保留，可继续生成双语字幕"
            if (request and request.live) or (not request and saved.get("live")):
                from app.arctime.saozi_live import run_live
                adapter = LocalASR(self.model, request.language if request else saved["asr"]["language"], self.threads)
                directory.mkdir(mode=0o700, exist_ok=True)
                job = run_live(directory, selector, adapter, self.stop_event,
                               lambda message: self.update("recording", message), url=request.url if request else None,
                               bilingual=bilingual)
                self.update("completed", f"臊子已完成，导出 {len(job['completed_clips'])} 个切片" +
                            ("；双语字幕未完成，可重试" if translation_failed else "及中日双语字幕"))
                return
            if request:
                adapter = LocalASR(self.model, request.language, self.threads)
                ranges = [(media.parse_time(start), media.parse_time(end)) for start, end in request.ranges]
                directory = workflow.create_run(request.url, self.root, ranges, request.highlights, adapter, run_id=job_id,
                                                progress=lambda message: self.update("downloading", message),
                                                saozi=request.saozi, local_source=local_source)
                snapshot = self.read_json(directory / 'job.json')
                snapshot.update(llm_provider='chatgpt' if selected.startswith('chatgpt:') else 'deepseek', llm_model=selected)
                workflow.write_manifest(directory, snapshot)
            else:
                adapter = None

            def progress(message: str):
                stage = json.loads((directory / "job.json").read_text())["state"]
                self.update(stage, message)

            job = workflow.resume_run(directory, adapter, progress=progress, selector=selector)
            if is_saozi:
                self.update("translating", "正在自动生成中日双语字幕")
                bilingual(directory, True, locked=False)
            message = f"处理完成，已导出 {len(job['completed_clips'])} 个切片"
            if is_saozi:
                message += "；双语字幕未完成，可重试" if translation_failed else "及中日双语字幕"
            if not job["completed_clips"]:
                message = "未发现达到阈值的高光；完整视频和字幕已保留"
            self.update("completed", message)
        except Exception as exc:
            error = "外部工具执行超时，请重试；已完成结果会保留" if isinstance(exc, subprocess.TimeoutExpired) else str(exc)
            self.update("failed", "处理失败", error)
        finally:
            if local_source and local_source.parent == self.root and local_source.name.startswith(".saozi-upload-"):
                local_source.unlink(missing_ok=True)
            with self.lock:
                self.last = self.active
                self.active = None

    def detail(self, job_id: str, *, include_segments: bool = True) -> dict:
        return job_detail(self, job_id, include_segments=include_segments)

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
        if translated.get("state") in {"completed", "partial", "translating", "failed"}:
            bilingual_names = {"subtitles.ja-zh.srt"} | {Path(clip["video"]).stem + ".ja-zh.srt" for clip in job.get("completed_clips", [])}
            allowed.update(bilingual_names & set(translated.get("artifacts", {})))
        path = directory / name
        if name not in allowed or Path(name).name != name or path.is_symlink() or not path.is_file():
            raise HTTPException(404, "结果文件不存在")
        if name.endswith(".ja-zh.srt") and media.fingerprint(path) != translated["artifacts"][name]:
            raise HTTPException(409, "双语字幕校验失败，原文件已保留")
        return path
