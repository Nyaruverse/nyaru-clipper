from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
import subprocess
import sys
from typing import TYPE_CHECKING, TypeVar

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field, ValidationError

from app.arctime.subtitle_encoding import burn_available
from app.arctime.subtitle_exports import ExportSnapshot, SubtitleExports
from app.arctime.subtitle_inputs import ExportRequest
from app.arctime.subtitle_style import SubtitleStyle
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
    except OSError:
        raise HTTPException(500, "字幕文件操作失败，请检查目录权限；原文件已保留") from None


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
    def submit(job_id: str, payload: ExportRequest) -> dict[str, str]:
        return {"id": _operation(lambda: exports.submit(job_id, payload))}

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
