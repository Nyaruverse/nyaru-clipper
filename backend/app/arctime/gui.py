from __future__ import annotations

import re
import threading
from contextlib import asynccontextmanager
from pathlib import Path
from typing import TYPE_CHECKING

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.arctime import companion_llm, media, translation, workflow
from app.arctime.chatgpt_api import chatgpt_router
from app.arctime.companion_models import JobInput, TranslationConfig, validated_api_key
from app.arctime.companion_manager import JobManager
from app.arctime.local_asr import DEFAULT_MODEL, LocalASR
from app.arctime.subtitle_api import subtitle_router
from app.arctime.subtitle_exports import SubtitleExports
from app.arctime.saozi_api import saozi_router
from app.services.task_artifacts import ResolvedArtifacts
from app.services.task_documents import Documents
from app.services.unified_database import DatabaseSafetyError

if TYPE_CHECKING:
    from app.arctime.unified_host import NativeHost

WEB_DIST = Path(__file__).resolve().parents[3] / "web" / "dist"


def create_app(root: Path, model: Path = DEFAULT_MODEL, threads: int = 4, web_dist: Path = WEB_DIST,
               *, artifacts: tuple[ResolvedArtifacts, ...] = (), settings_root: Path | None = None,
               credential_root: Path | None = None, documents: Documents | None = None, host: NativeHost | None = None,
               bind_host: str = '127.0.0.1') -> FastAPI:
    from app.services.host_binding import private_host
    bind_host = private_host(bind_host)
    if host is not None:
        if root.absolute() != host.root:
            raise ValueError('统一宿主与任务根不一致')
        documents, settings_root, credential_root = host.documents, host.settings_root, host.credential_root
    manager = JobManager(root, model, threads, artifacts=artifacts, settings_root=settings_root, credential_root=credential_root, documents=documents)
    if documents is not None and documents.root != manager.root:
        raise ValueError('文档索引与任务根不一致')
    manager.host = host
    if host is not None:
        manager.preferences = host.globals
        manager.load_preferences()
    exports = SubtitleExports(manager)

    @asynccontextmanager
    async def lifespan(app):
        manager.root.mkdir(parents=True, exist_ok=True)
        for task_id in manager.artifact_contexts:
            manager.directory(task_id).mkdir(mode=0o700, exist_ok=True)
        with workflow.exclusive_lock(manager.root / ".gui.lock"):
            started = False
            try:
                if host is not None:
                    host.start()
                    started = True
                yield
            finally:
                if host is not None and started:
                    host.stop()
                manager.stop_event.set()
                manager.executor.shutdown(wait=True)
                manager.chatgpt.close()

    app = FastAPI(title="Nyaru Local Companion", lifespan=lifespan)
    app.state.stream_stopping = threading.Event()
    @app.middleware('http')
    async def executor_readiness(request: Request, call_next):
        if host is not None and host.failure_code and request.method not in {'GET', 'HEAD', 'OPTIONS'} and not request.url.path.startswith('/companion-api/chatgpt/'):
            return JSONResponse(status_code=503, content={'detail': '统一执行器需要恢复；新写入已暂停，请保留数据并重开服务'})
        return await call_next(request)
    from app.api.body_limit import OperationsBodyLimit
    app.add_middleware(OperationsBodyLimit)

    @app.exception_handler(DatabaseSafetyError)
    def database_safety_error(_request: Request, error: DatabaseSafetyError) -> JSONResponse:
        return JSONResponse(status_code=503, content={'detail': str(error)})

    app.include_router(subtitle_router(manager, exports))
    app.include_router(saozi_router(manager))
    from app.arctime.topic_api import topic_router
    app.include_router(topic_router(manager))
    app.include_router(chatgpt_router(manager))
    if host is not None:
        from app.api.routes.operations import operations_router
        from app.api.routes.unified_library import library_router
        from app.api.routes.workstation_events import events_router
        app.include_router(operations_router(host.sessions, configuration=host.configuration, input_root=host.root), prefix='/api')
        app.include_router(library_router(host.sessions), prefix='/api')
        app.include_router(events_router(host.engine, stopped=app.state.stream_stopping), prefix='/api')
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "[::1]", "testserver", bind_host])

    @app.middleware("http")
    async def same_origin(request: Request, call_next):
        origin = request.headers.get("origin")
        if origin and origin != str(request.base_url).rstrip("/"):
            return Response("此接口只接受本地界面的请求", status_code=403)
        return await call_next(request)

    @app.get("/companion-api/config")
    def config():
        missing = []
        for name in ("yt-dlp", "ffmpeg", "ffprobe", "whisper-cli"):
            try:
                media.tool_path(name)
            except FileNotFoundError:
                missing.append(name)
        if not model.expanduser().is_file():
            missing.append("本地 Whisper 模型")
        if host is not None and host.failure_code:
            missing.append('统一执行器需要恢复，请保留数据并重新启动')
        from app.arctime.engine_readiness import whisperx_missing
        if host is not None:
            from app.services.public_runtime_settings import effective_settings
            engines = {'whisper.cpp': missing, 'whisperx': whisperx_missing(missing, effective_settings(host.globals.read('runtime/settings.json')))}
        else:
            engines = {'whisper.cpp': missing}
        return {"ready": not missing, "missing": missing, "translation_configured": manager.api_key is not None,
                'unified_operations': host is not None,
                'runtime_id': host.instance_id if host is not None else None,
                'engine_missing': engines,
                "subtitle_export_busy": bool(manager.active and manager.active.get("state") == "subtitle_export"),
                "translation_model": manager.translation_model, "translation_models": translation.MODELS,
                "translation_config_error": manager.config_error,
                'llm_provider': manager.llm_provider,
                'llm_model': manager.chatgpt_model if manager.llm_provider == 'chatgpt' else manager.translation_model,
                'llm_configured': companion_llm.configured(manager), 'chatgpt': manager.chatgpt.status()}

    @app.post("/companion-api/translation-config")
    def translation_config(payload: TranslationConfig):
        if payload.api_key is None and payload.model is None:
            raise HTTPException(422, "请输入 API Key 或选择翻译模型")
        if payload.model is not None and payload.model not in translation.MODELS:
            raise HTTPException(422, "请选择支持的 DeepSeek 翻译模型")
        try:
            new_key = validated_api_key(payload.api_key.get_secret_value()) if payload.api_key is not None else None
        except ValueError:
            raise HTTPException(422, "请输入有效 API Key") from None
        with manager.lock:
            if manager.config_path.is_symlink():
                raise HTTPException(409, "配置文件不能是符号链接，请检查 runs/config.json")
            try:
                key = new_key if new_key is not None else manager.api_key
                selected_model = payload.model if payload.model is not None else manager.translation_model
                manager.api_key, manager.translation_model = key, selected_model
                companion_llm.persist(manager)
            except (OSError, ValueError):
                refreshed = companion_llm.LLMConfig(manager.root, settings_root=manager.settings_root,
                    credential_root=manager.credential_root, preferences=manager.preferences)
                manager.api_key, manager.translation_model = refreshed.api_key, refreshed.translation_model
                refreshed.chatgpt.close()
                raise HTTPException(500, "Key 配置保存失败，请检查数据目录权限后重试") from None
            manager.api_key = key
            manager.translation_model = selected_model
            manager.config_error = None
        return {"translation_configured": manager.api_key is not None, "translation_model": manager.translation_model}

    @app.post("/companion-api/jobs/{job_id}/translate", status_code=202)
    def translate(job_id: str):
        return {"id": manager.submit_translation(job_id)}

    @app.post("/companion-api/jobs", status_code=202)
    def create_job(payload: JobInput):
        return {"id": manager.submit(payload)}

    @app.get("/companion-api/jobs")
    def list_jobs():
        ids = {p.name for p in manager.root.iterdir() if p.is_dir() and not p.is_symlink() and re.fullmatch(r"[0-9a-f]{12}", p.name)}
        ids.update(manager.artifact_contexts)
        if host is not None:
            ids.update(host.ids())
        with manager.lock:
            if manager.active:
                ids.add(manager.active["id"])
            if manager.last:
                ids.add(manager.last["id"])
        jobs = []
        for job_id in ids:
            try:
                if manager.read_json(manager.directory(job_id) / "job.json").get("version", 2) == 2:
                    jobs.append(manager.detail(job_id, include_segments=False))
            except (HTTPException, OSError, ValueError, KeyError, IndexError, TypeError):
                continue
        return sorted(jobs, key=lambda job: job["started_at"], reverse=True)

    @app.get("/companion-api/jobs/{job_id}")
    def job_detail(job_id: str):
        return manager.detail(job_id)

    @app.post("/companion-api/jobs/{job_id}/resume", status_code=202)
    def resume(job_id: str):
        if not manager.detail(job_id)["can_resume"]:
            raise HTTPException(409, "此任务不能恢复；下载失败请重新输入链接")
        return {"id": manager.submit(None, job_id)}

    @app.get("/companion-api/jobs/{job_id}/files/{name}")
    def file(job_id: str, name: str, download: bool = False):
        virtual = manager.virtual_artifact(job_id, name)
        if virtual is not None:
            return Response(virtual.content, media_type=virtual.media_type,
                headers={'Content-Disposition': f'attachment; filename="{name}"'} if download else None)
        if name.endswith(".vtt"):
            path = manager.artifact(job_id, name.removesuffix(".vtt") + ".srt")
            cues = media.read_subtitles(path) if path.read_text().strip() else []
            content = "WEBVTT\n\n" + re.sub(r"(?<=\d{2}:\d{2}:\d{2}),", ".", media.render_srt(cues))
            return Response(content, media_type="text/vtt")
        path = manager.artifact(job_id, name)
        return FileResponse(path, filename=name if download else None, content_disposition_type="attachment" if download else "inline")

    if (web_dist / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=web_dist / "assets"), name="assets")

    @app.get("/")
    def index():
        if not (web_dist / "companion.html").is_file():
            raise HTTPException(503, "请先在 web 目录执行 corepack pnpm build 构建界面")
        return FileResponse(web_dist / "companion.html")

    return app
