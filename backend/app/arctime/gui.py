from __future__ import annotations

import json
import re
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.arctime import companion_llm, media, translation, workflow
from app.arctime.chatgpt_api import chatgpt_router
from app.arctime.companion_models import GlossarySettings, JobInput, TranslationConfig, validated_api_key
from app.arctime.companion_manager import JobManager
from app.arctime.local_asr import DEFAULT_MODEL, LocalASR
from app.arctime.local_features_api import local_features_router
from app.arctime.subtitle_api import subtitle_router
from app.arctime.subtitle_exports import SubtitleExports
from app.arctime.saozi_api import saozi_router

WEB_DIST = Path(__file__).resolve().parents[3] / "web" / "dist"


def create_app(root: Path, model: Path = DEFAULT_MODEL, threads: int = 4, web_dist: Path = WEB_DIST) -> FastAPI:
    manager = JobManager(root, model, threads)
    exports = SubtitleExports(manager)

    @asynccontextmanager
    async def lifespan(app):
        manager.root.mkdir(parents=True, exist_ok=True)
        with workflow.exclusive_lock(manager.root / ".gui.lock"):
            yield
            manager.stop_event.set()
            manager.executor.shutdown(wait=True)
            manager.chatgpt.close()

    app = FastAPI(title="Nyaru Local Companion", lifespan=lifespan)
    app.include_router(subtitle_router(manager, exports))
    app.include_router(saozi_router(manager))
    app.include_router(chatgpt_router(manager))
    app.include_router(local_features_router(manager))
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "[::1]", "testserver"])

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
        return {"ready": not missing, "missing": missing, "translation_configured": manager.api_key is not None,
                "subtitle_export_busy": bool(manager.active and manager.active.get("state") == "subtitle_export"),
                "translation_model": manager.translation_model, "translation_models": translation.MODELS,
                "translation_config_error": manager.config_error,
                'llm_provider': manager.llm_provider,
                'llm_model': manager.chatgpt_model if manager.llm_provider == 'chatgpt' else manager.translation_model,
                'llm_configured': companion_llm.configured(manager), 'chatgpt': manager.chatgpt.status(),
                'glossary_collect_candidates': manager.glossary_collect_candidates}

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
                media.write_json(manager.config_path, {"deepseek_api_key": key.get_secret_value() if key else "",
                                                       "deepseek_model": selected_model,
                                                       'llm_provider': manager.llm_provider,
                                                       'chatgpt_model': manager.chatgpt_model})
            except OSError:
                raise HTTPException(500, "Key 配置保存失败，请检查数据目录权限后重试") from None
            manager.api_key = key
            manager.translation_model = selected_model
            manager.config_error = None
        return {"translation_configured": manager.api_key is not None, "translation_model": manager.translation_model}

    @app.post("/companion-api/glossary-settings")
    def glossary_settings(payload: GlossarySettings):
        with manager.lock:
            if manager.config_path.is_symlink():
                raise HTTPException(409, "配置文件不能是符号链接，请检查 runs/config.json")
            try:
                config = {}
                if manager.config_path.exists():
                    loaded = json.loads(manager.config_path.read_text(encoding="utf-8"))
                    if isinstance(loaded, dict):
                        config = loaded
                config["glossary_collect_candidates"] = payload.collect_candidates
                media.write_json(manager.config_path, config)
            except (OSError, UnicodeError):
                raise HTTPException(500, "配置保存失败，请检查数据目录权限后重试") from None
            manager.glossary_collect_candidates = payload.collect_candidates
        return {"glossary_collect_candidates": manager.glossary_collect_candidates}

    @app.post("/companion-api/jobs/{job_id}/translate", status_code=202)
    def translate(job_id: str, payload: dict | None = None):
        clip_index = payload.get("clip_index") if payload else None
        return {"id": manager.submit_translation(job_id, clip_index=clip_index)}

    @app.post("/companion-api/jobs/{job_id}/asr", status_code=202)
    def reasr(job_id: str):
        return {"id": manager.submit_asr(job_id)}

    @app.post("/companion-api/jobs", status_code=202)
    def create_job(payload: JobInput):
        return {"id": manager.submit(payload)}

    @app.get("/companion-api/jobs")
    def list_jobs():
        ids = {p.name for p in manager.root.iterdir() if p.is_dir() and not p.is_symlink() and re.fullmatch(r"[0-9a-f]{12}", p.name)}
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
    def file(job_id: str, name: str, download: bool = False, alias: str = ""):
        if name.endswith(".vtt"):
            path = manager.artifact(job_id, name.removesuffix(".vtt") + ".srt")
            cues = media.read_subtitles(path) if path.read_text(encoding="utf-8-sig", errors="replace").strip() else []
            content = "WEBVTT\n\n" + re.sub(r"(?<=\d{2}:\d{2}:\d{2}),", ".", media.render_srt(cues))
            return Response(content, media_type="text/vtt")
        path = manager.artifact(job_id, name)
        # alias 用于下载时的展示文件名（如投稿标题），净化路径分隔符防注入；缺扩展名时补上
        display = re.sub(r'[\\/:*?"<>|\x00-\x1f]', "_", alias).strip(" .")[:80] or path.name
        if alias and not display.lower().endswith(path.suffix.lower()):
            display += path.suffix
        # no-cache：同名产物（封面/切片视频/字幕）重新生成后强制浏览器重验证，避免展示旧内容
        return FileResponse(path, filename=display if download else None,
                            content_disposition_type="attachment" if download else "inline",
                            headers={"Cache-Control": "no-cache"})

    if (web_dist / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=web_dist / "assets"), name="assets")

    @app.get("/")
    def index():
        if not (web_dist / "companion.html").is_file():
            raise HTTPException(503, "请先在 web 目录执行 corepack pnpm build 构建界面")
        return FileResponse(web_dist / "companion.html")

    return app
