from __future__ import annotations

import json
import logging
import re
import subprocess
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import TYPE_CHECKING

from fastapi import HTTPException
from pydantic import SecretStr
from app.arctime import companion_llm, media, translation, workflow
from app.arctime.local_asr import LocalASR
from app.arctime.companion_models import JobInput
from app.arctime.subtitle_exports import export_artifact, SubtitleExports
from app.arctime.subtitle_templates import TemplateStore, StyleTemplate
from app.arctime.subtitle_encoding import burn_available
from app.arctime.companion_projection import job_detail
from app.arctime.workstation_projection import TextArtifact, project_artifacts, text_artifact
from app.services.task_artifacts import ArtifactError, ResolvedArtifacts
from app.services.runtime_guard import SlotBusy, engine_slot

if TYPE_CHECKING:
    from app.services.task_documents import Documents
    from app.arctime.unified_host import NativeHost

logger = logging.getLogger(__name__)


class JobManager(companion_llm.LLMConfig):
    def __init__(self, root: Path, model: Path, threads: int, *, artifacts: tuple[ResolvedArtifacts, ...] = (),
                 settings_root: Path | None = None, credential_root: Path | None = None, documents: Documents | None = None):
        self.documents = documents
        self.host: NativeHost | None = None
        self.artifact_contexts = {context.source.task_id: context for context in artifacts}
        if len(self.artifact_contexts) != len(artifacts):
            raise ArtifactError('来源身份重复，请核对来源实例与任务')
        for context in artifacts:
            output_root = root.resolve()
            registered = bool(documents and documents.context_registered(context.source))
            source_roots = [(context.source.root, registered)]
            if context.source.media_root is not None:
                source_roots.append((context.source.media_root, False))
            for source_root, registered_root in source_roots:
                source_root = source_root.resolve()
                if registered_root and source_root == output_root:
                    continue
                if source_root.is_relative_to(output_root) or output_root.is_relative_to(source_root):
                    raise ArtifactError('新编辑根不能与旧来源根重叠')
            context.verify()
        super().__init__(root, settings_root=settings_root, credential_root=credential_root)
        self.model = model
        self.threads = threads
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="local-companion")
        self.lock = threading.Lock()
        self.active: dict | None = None
        self.last: dict | None = None
        self.stop_event = threading.Event()

    def directory(self, job_id: str) -> Path:
        path = self.root / job_id
        owned = self.host is not None and self.documents is not None and self.documents.is_activated(job_id)
        if (not re.fullmatch(r"[0-9a-f]{12}", job_id) and job_id not in self.artifact_contexts and not owned) or path.is_symlink():
            raise HTTPException(404, "任务不存在")
        return path

    def artifacts(self, directory: Path) -> ResolvedArtifacts | None:
        if self.host is not None and directory.parent == self.root:
            return self.host.context(directory.name)
        return self.artifact_contexts.get(directory.name) if directory.parent == self.root else None

    def virtual_artifact(self, job_id: str, name: str) -> TextArtifact | None:
        if re.fullmatch(r'styled-[0-9a-f]{20}\.(ass|mp4|zip)', name):
            return None
        context = self.artifacts(self.directory(job_id))
        if self.host is not None and context is not None:
            from app.arctime.native_document import saved_bilingual
            saved = saved_bilingual(self.host, context, name)
            if saved is not None:
                return saved
        return text_artifact(context, name) if context is not None else None

    def submit(self, request: JobInput | None, job_id: str | None = None, *, deferred: bool = False) -> str:
        if self.host is not None:
            from app.services.task_operations import OperationConflict
            try:
                with self.lock:
                    if deferred and self.active:
                        raise HTTPException(409, '已有录像正在导入，请等待导入完成')
                    return self.host.submit(self, request, job_id, deferred=deferred)
            except OperationConflict as error:
                raise HTTPException(409, str(error)) from None
        if request is not None and request.engine != 'whisper.cpp':
            raise HTTPException(409, 'WhisperX 任务需要统一运行入口')
        if self.documents is not None:
            raise HTTPException(409, '此候选使用统一操作队列，请通过统一处理入口提交')
        if job_id in self.artifact_contexts:
            raise HTTPException(409, '此入口只编辑已载入结果，请使用处理队列启动新操作')
        with self.lock:
            if self.active:
                raise HTTPException(409, "已有任务正在处理，请等待完成后再开始")
            job_id = job_id or uuid.uuid4().hex[:12]
            saved = self.read_json(self.directory(job_id) / "job.json")
            saozi = bool(request.saozi if request else saved.get("saozi"))
            try:
                model = None if self.config_error and not saozi else companion_llm.job_model(self, saved)
                key = companion_llm.require_key(self, model) if saozi else self.api_key
            except ValueError as exc:
                raise HTTPException(409, str(exc)) from None
            template = None
            if request and request.subtitle_template_id:
                template = next((item for item in TemplateStore(self.settings_root).list_styles()
                                 if item.id == request.subtitle_template_id), None)
                if template is None:
                    raise HTTPException(409, '字幕模板不存在，请重新选择')
                if request.live and not burn_available():
                    raise HTTPException(409, '当前 FFmpeg 不支持字幕烧录，请取消模板或安装支持 libass 的版本')
            self.stop_event.clear()
            self.active = {"id": job_id, "state": "uploading" if deferred else "preparing",
                           "message": "正在导入录像" if deferred else "正在检查本地环境", "started_at": time.time(),
                           "error": None, "live": bool(request.live if request else False), "saozi": saozi,
                           'model': model, 'llm_provider': ('chatgpt' if model.startswith('chatgpt:') else 'deepseek') if model else None}
            if template is not None:
                self.active['subtitle_template'] = template.model_dump()
            if not deferred:
                self.executor.submit(self.run, job_id, request, key, model, style_template=template)
        return job_id

    def stop(self, job_id: str) -> None:
        if self.host is not None:
            self.host.stop_live(job_id)
            return
        with self.lock:
            if not self.active or self.active["id"] != job_id or not self.active.get("live"):
                raise HTTPException(409, "没有正在录制的臊子直播任务")
            self.stop_event.set()
            self.active["message"] = "正在停止录制并处理剩余内容"

    def submit_translation(self, job_id: str) -> str:
        if self.host is not None:
            try:
                return self.host.enqueue_translation(job_id, companion_llm.selected_model(self))
            except ValueError as error:
                raise HTTPException(409, str(error)) from None
        if self.documents is not None and self.documents.is_activated(job_id):
            raise HTTPException(409, '请通过统一处理队列翻译此任务')
        if job_id in self.artifact_contexts:
            raise HTTPException(409, '请通过统一处理队列翻译此来源')
        record = self.detail(job_id)
        if record["state"] != "completed":
            raise HTTPException(409, "请等待视频任务完成后再生成双语字幕")
        with self.lock:
            if self.active:
                raise HTTPException(409, "已有任务正在处理，请等待完成")
            saved = self.read_json(self.directory(job_id) / 'job.json')
            try:
                model = (record['translation']['model'] if record['translation']['state'] != 'not_started'
                         else companion_llm.job_model(self, saved))
                key = companion_llm.require_key(self, model)
            except ValueError as exc:
                raise HTTPException(409, str(exc)) from None
            if not (saved.get('saozi_model') or saved.get('llm_model')):
                with workflow.exclusive_lock(self.directory(job_id) / '.lock'):
                    saved.update(llm_model=model, llm_provider='chatgpt' if model.startswith('chatgpt:') else 'deepseek')
                    workflow.write_manifest(self.directory(job_id), saved)
            if self.last and self.last["id"] == job_id:
                self.last = None
            self.active = {"id": job_id, "state": "translating", "message": "准备日译中", "error": None, "model": model}
            self.executor.submit(self.run_translation, job_id, key, model)
        return job_id

    def run_translation(self, job_id: str, key: SecretStr, model: str):
        try:
            with engine_slot():
                return self._run_translation(job_id, key, model)
        except SlotBusy:
            with self.lock:
                self.active["translation_error"] = "其他入口正在处理，请稍后重试翻译；已有结果已保留"
                self.last, self.active = self.active, None

    def _run_translation(self, job_id: str, key: SecretStr, model: str):
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
            with workflow.exclusive_lock(directory / '.lock'):
                saved = self.read_json(directory / 'job.json')
                if saved.get('live') and saved.get('subtitle_template'):
                    SubtitleExports(self).export_live(directory, saved)
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
            model: str | None = None, local_source: Path | None = None, *, style_template: StyleTemplate | None = None,
            owned_upload: workflow.OwnedUpload | None = None):
        try:
            with engine_slot():
                return self._run(job_id, request, key, model, local_source,
                    style_template=style_template, owned_upload=owned_upload)
        except SlotBusy:
            try:
                self.update("failed", "其他入口正在处理，请稍后重试", "执行槽被占用；已有结果已保留")
            finally:
                if owned_upload is not None:
                    owned_upload.cleanup()
                with self.lock:
                    self.last, self.active = self.active, None

    def _run(self, job_id: str, request: JobInput | None, key: SecretStr | None = None,
             model: str | None = None, local_source: Path | None = None, *, style_template: StyleTemplate | None = None,
             owned_upload: workflow.OwnedUpload | None = None):
        reservation = self.active
        try:
            directory = self.directory(job_id)
            saved = self.read_json(directory / "job.json")
            if request is not None and style_template is None and self.active.get('subtitle_template'):
                style_template = StyleTemplate.model_validate(self.active['subtitle_template'])
            is_saozi = bool(request.saozi if request else saved.get("saozi"))
            selected = model or (None if self.config_error and not is_saozi else companion_llm.job_model(self, saved))
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
                changed = set()
                if translation_failed and not final:
                    return changed
                from app.arctime.saozi_translation import translate
                def notify(message: str):
                    with self.lock:
                        self.active["message"] = message
                try:
                    translate(path, key, model=selector.model, final=final, locked=locked, progress=notify,
                              changed_artifact=changed.add, **options)
                    translation_failed = False
                    with self.lock:
                        self.active.pop("translation_error", None)
                except (ValueError, OSError):
                    translation_failed = True
                    with self.lock:
                        self.active["translation_error"] = "双语字幕未完成；原文切片已保留，可继续生成双语字幕"
                return {name.removesuffix('.ja-zh.srt') + '.mp4' for name in changed if name.startswith('clip-')}
            if (request and request.live) or (not request and saved.get("live")):
                from app.arctime.saozi_live import run_live
                adapter = LocalASR(self.model, request.language if request else saved["asr"]["language"], self.threads)
                directory.mkdir(mode=0o700, exist_ok=True)
                job = run_live(directory, selector, adapter, self.stop_event,
                               lambda message: self.update("recording", message), url=request.url if request else None,
                               bilingual=bilingual, style_template=style_template,
                               styled=SubtitleExports(self).export_live)
                self.update("completed", f"臊子已完成，导出 {len(job['completed_clips'])} 个切片" +
                            ("；双语字幕未完成，可重试" if translation_failed else "及中日双语字幕") +
                            ('；自动样式导出未完成，可恢复处理重试' if job.get('subtitle_style_error') else ''))
                return
            if request:
                adapter = LocalASR(self.model, request.language, self.threads)
                ranges = [(media.parse_time(start), media.parse_time(end)) for start, end in request.ranges]
                directory = workflow.create_run(request.url, self.root, ranges, request.highlights, adapter, run_id=job_id,
                                                progress=lambda message: self.update("downloading", message),
                                                saozi=request.saozi, local_source=local_source, llm_model=selected,
                                                recognition_only=request.recognition_only,
                                                owned_upload=owned_upload)
                snapshot = self.read_json(directory / 'job.json')
                if style_template is not None:
                    snapshot['subtitle_template'] = style_template.model_dump()
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
            try:
                self.update("failed", "处理失败", error)
            except OSError as record_error:
                raise exc from record_error
        finally:
            try:
                if owned_upload is not None:
                    owned_upload.cleanup()
            except OSError:
                logger.warning("upload_cleanup_deferred job_id=%s", job_id)
            finally:
                with self.lock:
                    if self.active is reservation:
                        self.last = reservation
                        self.active = None

    def detail(self, job_id: str, *, include_segments: bool = True) -> dict:
        if self.host is not None:
            from app.arctime.native_projection import job_view
            self.directory(job_id)
            return job_view(self.host, job_id, include_segments=include_segments)
        context = self.artifacts(self.directory(job_id))
        if context is not None:
            return project_artifacts(context, include_segments=include_segments).model_dump()
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
        if self.host is not None:
            from app.arctime.native_live import file
            partial = file(self.host, job_id, name)
            if partial is not None:
                return partial
        if re.fullmatch(r"styled-[0-9a-f]{20}\.(ass|mp4|zip)", name):
            if self.host is not None:
                from app.arctime.native_exports import export_file
                return export_file(self.host, job_id, name)
            return export_artifact(directory, name)
        context = self.artifacts(directory)
        if context is not None:
            if name == 'source.mp4':
                return context.source.checked(context.source.video)
            if re.fullmatch(r'clip-\d{3,}\.mp4', name):
                index = int(name.removeprefix('clip-').removesuffix('.mp4')) - 1
                if 0 <= index < len(context.source.clips):
                    return context.source.checked(context.source.clips[index].video)
            raise HTTPException(404, '结果文件不存在')
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
