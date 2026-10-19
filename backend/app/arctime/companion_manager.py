from __future__ import annotations

import json
import os
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
from app.arctime.subtitle_exports import export_artifact, SubtitleExports
from app.arctime.subtitle_templates import TemplateStore, StyleTemplate
from app.arctime.subtitle_encoding import burn_available
from app.arctime.companion_projection import job_detail


class JobManager:
    def __init__(self, root: Path, model: Path, threads: int):
        self.root = root.expanduser().resolve()
        self.model = model
        self.threads = threads
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="local-companion")
        self.lock = threading.RLock() if os.name == "nt" else threading.Lock()
        self.active: dict | None = None
        self.last: dict | None = None
        self.stop_event = threading.Event()
        self.cancel_event = threading.Event()
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
            template = None
            if request and request.subtitle_template_id:
                template = next((item for item in TemplateStore(self.root).list_styles()
                                 if item.id == request.subtitle_template_id), None)
                if template is None:
                    raise HTTPException(409, '字幕模板不存在，请重新选择')
                if not burn_available():
                    raise HTTPException(409, '当前 FFmpeg 不支持字幕烧录，请取消模板或安装支持 libass 的版本')
            self.stop_event.clear()
            self.cancel_event.clear()
            self.active = {"id": job_id, "state": "uploading" if deferred else "preparing",
                           "message": "正在导入录像" if deferred else "正在检查本地环境", "started_at": time.time(),
                           "error": None, "live": bool(request.live if request else False), "saozi": saozi,
                           'model': model, 'llm_provider': 'chatgpt' if model.startswith('chatgpt:') else 'deepseek'}
            if not deferred:
                self.executor.submit(self.run, job_id, request, key, model, style_template=template)
        return job_id

    def stop(self, job_id: str) -> None:
        with self.lock:
            if not self.active or self.active["id"] != job_id or not self.active.get("live"):
                raise HTTPException(409, "没有正在录制的臊子直播任务")
            self.stop_event.set()
            self.active["message"] = "正在停止录制并处理剩余内容"

    def cancel(self, job_id: str) -> None:
        """手动终止正在运行的任务（下载/转录/导出/翻译）。"""
        with self.lock:
            if not self.active or self.active["id"] != job_id:
                raise HTTPException(409, "该任务未在运行，无法终止")
            if self.active.get("state") in {"cancelling", "cancelled"}:
                return
            self.active["state"] = "cancelling"
            self.active["message"] = "正在终止任务"
            self.cancel_event.set()
            self.stop_event.set()
        killed = media.terminate_active_processes()
        with self.lock:
            if self.active and self.active["id"] == job_id:
                self.active["message"] = f"正在终止任务（已结束 {killed} 个子进程）"

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
            self.cancel_event.clear()
            self.active = {"id": job_id, "state": "translating", "message": "准备日译中", "error": None, "model": model}
            self.executor.submit(self.run_translation, job_id, key, model)
        return job_id

    def run_translation(self, job_id: str, key: SecretStr, model: str):
        def progress(message: str):
            if self.cancel_event.is_set():
                raise media.RunCancelled()
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
                # 术语表只走 DeepSeek 经典路径（ChatGPT 订阅路径不注入）
                store = None if request_json is not None else self._load_glossary()
                terms = store.terms if store is not None else None
                translation.translate_run(directory, key, progress=progress, model=model, terms=terms, **options)
                if request_json is None and store is not None:
                    self._collect_glossary_candidates(directory, key, model, store, progress)
            with workflow.exclusive_lock(directory / '.lock'):
                saved = self.read_json(directory / 'job.json')
                if saved.get('live') and saved.get('subtitle_template'):
                    SubtitleExports(self).export_live(directory, saved)
        except media.RunCancelled:
            with self.lock:
                self.active["state"] = "cancelled"
                self.active["message"] = "翻译已手动终止，可继续翻译"
                self.active["error"] = None
        except Exception:
            with self.lock:
                self.active["translation_error"] = "翻译未完成；检查字幕、API Key 或网络后重试，原结果已保留"
        finally:
            with self.lock:
                self.last = self.active
                self.active = None

    def _load_glossary(self):
        from app.arctime.local_features_api import load_glossary_store
        return load_glossary_store(self)

    def _save_glossary(self, store) -> None:
        from app.arctime.local_features_api import save_glossary_store
        save_glossary_store(self, store)

    def _collect_glossary_candidates(self, directory: Path, key: SecretStr, model: str,
                                     store, progress) -> None:
        """翻译完成后提取未收录术语候选；任何失败都不影响翻译结果。"""
        from app.arctime import glossary
        try:
            job = json.loads(workflow._path(directory, "job.json").read_text())
            cues = media.read_subtitles(workflow._path(directory, job["subtitles"]))
            zh_path = directory / "subtitles.zh.srt"
            translated = [cue.text for cue in media.read_subtitles(zh_path)] if zh_path.is_file() else []
            if not cues or not translated:
                return
            progress("正在整理术语候选")
            import httpx
            with httpx.Client(timeout=120, follow_redirects=False) as client:
                found = translation.extract_candidates(client, key, model, cues, translated, store.terms)
            if found and glossary.add_candidates(store, found):
                self._save_glossary(store)
        except Exception:
            pass

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
            model: str | None = None, local_source: Path | None = None, *, style_template: StyleTemplate | None = None):
        if os.name == "nt":
            terminal_update = None
        should_cancel = lambda: self.cancel_event.is_set()
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
                               bilingual=bilingual, style_template=style_template,
                               styled=SubtitleExports(self).export_live)
                if os.name == "nt":
                    terminal_update = ("completed", f"臊子已完成，导出 {len(job['completed_clips'])} 个切片" +
                                ("；双语字幕未完成，可重试" if translation_failed else "及中日双语字幕") +
                                ('；自动样式导出未完成，可恢复处理重试' if job.get('subtitle_style_error') else ''))
                else:
                    self.update("completed", f"臊子已完成，导出 {len(job['completed_clips'])} 个切片" +
                                ("；双语字幕未完成，可重试" if translation_failed else "及中日双语字幕") +
                                ('；自动样式导出未完成，可恢复处理重试' if job.get('subtitle_style_error') else ''))
                return
            if request:
                adapter = LocalASR(self.model, request.language, self.threads)
                ranges = [(media.parse_time(start), media.parse_time(end)) for start, end in request.ranges]
                directory = workflow.create_run(request.url, self.root, ranges, request.highlights, adapter, run_id=job_id,
                                                progress=lambda message: self.update("downloading", message),
                                                saozi=request.saozi, local_source=local_source,
                                                should_cancel=should_cancel)
                snapshot = self.read_json(directory / 'job.json')
                snapshot.update(llm_provider='chatgpt' if selected.startswith('chatgpt:') else 'deepseek', llm_model=selected)
                workflow.write_manifest(directory, snapshot)
            else:
                adapter = None

            def progress(message: str):
                stage = json.loads((directory / "job.json").read_text())["state"]
                self.update(stage, message)

            job = workflow.resume_run(directory, adapter, progress=progress, selector=selector,
                                      should_cancel=should_cancel)
            if is_saozi:
                self.update("translating", "正在自动生成中日双语字幕")
                bilingual(directory, True, locked=False)
            message = f"处理完成，已导出 {len(job['completed_clips'])} 个切片"
            if is_saozi:
                message += "；双语字幕未完成，可重试" if translation_failed else "及中日双语字幕"
            if not job["completed_clips"]:
                message = "未发现达到阈值的高光；完整视频和字幕已保留"
            if os.name == "nt":
                terminal_update = ("completed", message)
            else:
                self.update("completed", message)
        except media.RunCancelled:
            if os.name == "nt":
                terminal_update = ("cancelled", "任务已手动终止，可恢复继续", None)
            else:
                self.update("cancelled", "任务已手动终止，可恢复继续")
        except Exception as exc:
            error = "外部工具执行超时，请重试；已完成结果会保留" if isinstance(exc, subprocess.TimeoutExpired) else str(exc)
            if os.name == "nt":
                terminal_update = ("failed", "处理失败", error)
            else:
                self.update("failed", "处理失败", error)
        finally:
            if os.name == "nt":
                # Windows file cleanup must finish before publishing the terminal
                # state. Always release the active slot, even if status I/O fails.
                try:
                    if local_source and local_source.parent == self.root and local_source.name.startswith(".saozi-upload-"):
                        local_source.unlink(missing_ok=True)
                except OSError as exc:
                    terminal_update = ("failed", "处理失败", str(exc))
                with self.lock:
                    try:
                        if terminal_update:
                            self.update(*terminal_update)
                    except Exception as exc:
                        self.update("failed", "处理失败", str(exc))
                    finally:
                        self.last = self.active
                        self.active = None
            else:
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
            if os.name == "nt":
                with media.json_io_lock:
                    value = json.loads(path.read_text(encoding="utf-8"))
            else:
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
            bilingual_names = ({"subtitles.ja-zh.srt", "subtitles.zh.srt"}
                               | {Path(clip["video"]).stem + suffix for clip in job.get("completed_clips", [])
                                  for suffix in (".ja-zh.srt", ".zh.srt")})
            allowed.update(bilingual_names & set(translated.get("artifacts", {})))
        # 切片视频产物（topic-NN.mp4 / topic-combined.mp4）
        topic_clips = self.read_json(directory / "topic_clips.json")
        for item in topic_clips.get("items", []):
            if isinstance(item, dict) and item.get("state") == "completed" and isinstance(item.get("file"), str):
                allowed.add(item["file"])
        combined = topic_clips.get("combined")
        if isinstance(combined, dict) and isinstance(combined.get("file"), str):
            allowed.add(combined["file"])
        # 烧录合成产物（*.burn.{variant}.mp4）
        for clip_burns in self.read_json(directory / "burn.json").get("clips", {}).values():
            if isinstance(clip_burns, dict):
                for entry in clip_burns.values():
                    if isinstance(entry, dict) and entry.get("state") == "completed" and isinstance(entry.get("file"), str):
                        allowed.add(entry["file"])
        path = directory / name
        if name not in allowed or Path(name).name != name or path.is_symlink() or not path.is_file():
            raise HTTPException(404, "结果文件不存在")
        if name.endswith(".ja-zh.srt") and media.fingerprint(path) != translated["artifacts"][name]:
            raise HTTPException(409, "双语字幕校验失败，原文件已保留")
        return path
