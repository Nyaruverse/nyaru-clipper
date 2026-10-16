from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
import subprocess
import sys
from typing import TYPE_CHECKING, TypeVar

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response
from starlette.concurrency import run_in_threadpool
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.arctime.subtitle_encoding import burn_available
from app.arctime.subtitle_fonts import FontCatalog, font_catalog
from app.arctime.subtitle_exports import ExportSnapshot, SubtitleExports
from app.arctime.subtitle_inputs import ExportRequest
from app.arctime.subtitle_style import SubtitleStyle
from app.arctime.subtitle_document import DocumentStore, SubtitleDocument, validate_source
from app.arctime.subtitle_render import preview_png
from app.arctime.subtitle_templates import ProjectTemplate, StyleTemplate

if TYPE_CHECKING:
    from app.arctime.gui import JobManager

Result = TypeVar("Result")


def _operation(action: Callable[[], Result]) -> Result:
    try:
        return action()
    except ValidationError:
        raise HTTPException(422, "字幕样式或模板格式无效；请检查版本、颜色、数值及字体") from None
    except FileNotFoundError:
        raise HTTPException(404, "模板或任务文件不存在") from None
    except ValueError as error:
        raise HTTPException(409, str(error)) from None
    except subprocess.SubprocessError:
        raise HTTPException(409, "字幕工具执行失败或超时；原文件已保留") from None
    except OSError:
        raise HTTPException(500, "字幕文件操作失败，请检查目录权限；原文件已保留") from None


class PreviewInput(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)
    document: SubtitleDocument
    time: float = Field(ge=0)
    bilingual: bool = False


class DefaultInput(BaseModel):
    style: SubtitleStyle


class TemplateInput(DefaultInput):
    id: str | None = None
    name: str = Field(min_length=1, max_length=100)
    arctime_template_id: str | None = None


class SubtitleSettings(BaseModel):
    style: SubtitleStyle
    templates: list[StyleTemplate]
    arctime_templates: list[ProjectTemplate]
    burn_available: bool
    native_handoff_available: bool


async def _bounded_body(request: Request, limit: int) -> bytes:
    content = bytearray()
    async for part in request.stream():
        if len(content) + len(part) > limit:
            raise HTTPException(413, "模板文件超出允许大小")
        content.extend(part)
    return bytes(content)


def subtitle_router(manager: JobManager, exports: SubtitleExports) -> APIRouter:
    router = APIRouter(prefix="/companion-api")
    store = exports.templates
    documents = DocumentStore()

    @router.get('/jobs/{job_id}/subtitle-document')
    def document(job_id: str, source: bool = False) -> SubtitleDocument:
        return _operation(lambda: documents.load(manager.directory(job_id), store.load_defaults(), source=source))

    @router.post('/jobs/{job_id}/subtitle-document')
    async def save(job_id: str, request: Request) -> SubtitleDocument:
        content = await _bounded_body(request, 20 * 1024 * 1024)
        payload = _operation(lambda: SubtitleDocument.model_validate_json(content))
        def persist() -> SubtitleDocument:
            with manager.lock:
                if manager.active:
                    raise HTTPException(409, '已有任务正在处理，请等待完成')
                return _operation(lambda: documents.save(manager.directory(job_id), payload))
        return await run_in_threadpool(persist)

    @router.post('/jobs/{job_id}/subtitle-preview')
    async def preview(job_id: str, request: Request) -> Response:
        content = await _bounded_body(request, 20 * 1024 * 1024)
        payload = _operation(lambda: PreviewInput.model_validate_json(content))
        def render() -> bytes:
            validate_source(payload.document, documents.base(manager.directory(job_id), payload.document.style))
            if payload.time > payload.document.duration:
                raise ValueError('预览时间超过视频时长')
            return preview_png(payload.document, payload.time, payload.bilingual)
        return Response(await run_in_threadpool(lambda: _operation(render)), media_type='image/png', headers={'Cache-Control': 'no-store'})

    @router.get('/subtitle-fonts')
    def fonts() -> FontCatalog:
        return font_catalog()

    @router.get("/subtitle-settings")
    def settings() -> SubtitleSettings:
        return _operation(lambda: SubtitleSettings(style=store.load_defaults(), templates=store.list_styles(),
            arctime_templates=store.list_projects(), burn_available=burn_available(), native_handoff_available=sys.platform == "darwin"))

    @router.post("/subtitle-settings")
    def save_settings(payload: DefaultInput) -> DefaultInput:
        return DefaultInput(style=_operation(lambda: store.save_defaults(payload.style)))

    @router.post("/style-templates")
    def save_template(payload: TemplateInput) -> StyleTemplate:
        if "arctime_template_id" in payload.model_fields_set:
            return _operation(lambda: store.save_style(payload.name, payload.style, payload.arctime_template_id, payload.id))
        return _operation(lambda: store.save_style(payload.name, payload.style, template_id=payload.id))

    @router.post("/style-templates/import")
    async def import_template(request: Request) -> StyleTemplate:
        content = await _bounded_body(request, 64 * 1024)
        return _operation(lambda: store.import_style(content))

    @router.post("/style-templates/{identity}/delete")
    def delete_template(identity: str) -> dict[str, bool]:
        _operation(lambda: store.delete_style(identity))
        return {"deleted": True}

    @router.get("/style-templates/{identity}/download")
    def download_template(identity: str) -> Response:
        return Response(_operation(lambda: store.download_style(identity)), media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="style-{identity}.json"'})

    @router.post("/arctime-templates")
    async def upload_project(request: Request, name: str, filename: str) -> ProjectTemplate:
        content = await _bounded_body(request, 16 * 1024 * 1024)
        return _operation(lambda: store.save_project(name, filename, content))

    @router.post("/arctime-templates/{identity}/delete")
    def delete_project(identity: str) -> dict[str, bool]:
        _operation(lambda: store.delete_project(identity))
        return {"deleted": True}

    @router.get("/arctime-templates/{identity}/download")
    def download_project(identity: str) -> Response:
        return Response(_operation(lambda: store.download_project(identity)), media_type="application/octet-stream",
            headers={"Content-Disposition": f'attachment; filename="template-{identity}.atpj"'})

    @router.post("/jobs/{job_id}/subtitle-export", status_code=202)
    async def submit(job_id: str, request: Request) -> dict[str, str]:
        content = await _bounded_body(request, 20 * 1024 * 1024)
        payload = _operation(lambda: ExportRequest.model_validate_json(content))
        return {'id': await run_in_threadpool(lambda: _operation(lambda: exports.submit(job_id, payload)))}

    @router.get("/jobs/{job_id}/subtitle-exports")
    def snapshot(job_id: str) -> ExportSnapshot:
        return _operation(lambda: exports.snapshot(job_id))

    @router.post("/arctime/open")
    def open_arctime() -> dict[str, bool]:
        application = Path("/Applications/ArcTime Pro.app")
        if sys.platform != "darwin" or not application.is_dir():
            raise HTTPException(409, "请安装 macOS 版 ArcTime Pro，或手动导入精修包")
        result = subprocess.run(["/usr/bin/open", "-a", str(application)], capture_output=True, timeout=15, check=False)
        if result.returncode:
            raise HTTPException(409, "ArcTime 启动失败，请手动打开")
        return {"opened": True}

    @router.post("/jobs/{job_id}/subtitle-exports/open-folder")
    def open_folder(job_id: str) -> dict[str, bool]:
        if sys.platform != "darwin":
            raise HTTPException(409, "请使用下载入口保存精修包")
        manager.detail(job_id, include_segments=False)
        result = subprocess.run(["/usr/bin/open", str(manager.directory(job_id))], capture_output=True, timeout=15, check=False)
        if result.returncode:
            raise HTTPException(409, "无法打开导出目录，请使用下载入口")
        return {"opened": True}

    return router
