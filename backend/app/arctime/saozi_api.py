from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from pydantic import ValidationError

from app.arctime.companion_manager import JobManager
from app.arctime.companion_models import JobInput


def saozi_router(manager: JobManager) -> APIRouter:
    router = APIRouter(prefix="/companion-api")

    @router.post("/saozi/upload", status_code=202)
    @router.post("/jobs/upload", status_code=202)
    async def upload(request: Request, language: str = "auto", saozi: bool = True,
                     ranges: str = "[]", highlights: int | None = None):
        try:
            payload = JobInput(url="https://local.invalid", saozi=saozi, language=language,
                               ranges=json.loads(ranges), highlights=highlights)
        except (ValidationError, json.JSONDecodeError):
            raise HTTPException(422, "请检查视频语种及切片选项：选择有效时间段、高光数量或臊子其中一种") from None
        declared = request.headers.get("content-length")
        if declared and (not declared.isdigit() or int(declared) > shutil.disk_usage(manager.root).free - 64 * 1024 ** 2):
            raise HTTPException(413, "录像过大或磁盘空间不足")
        job_id = manager.submit(payload, deferred=True)
        from app.arctime import companion_llm
        model = manager.active['model']
        temporary = None
        try:
            key = companion_llm.require_key(manager, model) if payload.saozi else manager.api_key
            descriptor, name = tempfile.mkstemp(prefix=".saozi-upload-", dir=manager.root)
            temporary = Path(name)
            count = 0
            with os.fdopen(descriptor, "wb") as handle:
                async for block in request.stream():
                    if shutil.disk_usage(manager.root).free < len(block) + 64 * 1024 ** 2:
                        raise HTTPException(413, "磁盘空间不足，导入已停止")
                    handle.write(block)
                    count += len(block)
                handle.flush()
                os.fsync(handle.fileno())
            if not count:
                raise HTTPException(422, "请选择非空录像文件")
            manager.executor.submit(manager.run, job_id, payload, key, model, temporary)
            return {"id": job_id}
        except BaseException:
            if temporary:
                temporary.unlink(missing_ok=True)
            manager.update("failed", "录像导入未完成，请重新选择文件", "导入失败，原录像未改变")
            with manager.lock:
                manager.last = manager.active
                manager.active = None
            raise

    @router.post("/jobs/{job_id}/stop", status_code=202)
    def stop(job_id: str):
        manager.stop(job_id)
        return {"id": job_id, "stopping": True}

    return router
