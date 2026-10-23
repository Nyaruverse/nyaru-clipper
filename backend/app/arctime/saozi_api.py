from __future__ import annotations

import json
import logging
import os
import shutil
import tempfile
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import ValidationError

from app.arctime.companion_manager import JobManager
from app.arctime.companion_models import JobInput
from app.arctime.workflow import OwnedUpload

logger = logging.getLogger(__name__)


def saozi_router(manager: JobManager) -> APIRouter:
    router = APIRouter(prefix="/companion-api")

    @router.post("/saozi/upload", status_code=202)
    @router.post("/jobs/upload", status_code=202)
    async def upload(request: Request, language: str = "auto", saozi: bool = True,
                     ranges: str = "[]", highlights: int | None = None, subtitle_template_id: str | None = None,
                     engine: Literal['whisper.cpp', 'whisperx'] = 'whisper.cpp'):
        try:
            payload = JobInput(url="https://local.invalid", saozi=saozi, language=language, engine=engine,
                               ranges=json.loads(ranges), highlights=highlights, subtitle_template_id=subtitle_template_id)
        except (ValidationError, json.JSONDecodeError):
            raise HTTPException(422, "请检查视频语种及切片选项：选择有效时间段、高光数量或臊子其中一种") from None
        declared = request.headers.get("content-length")
        if declared and (not declared.isdigit() or int(declared) > shutil.disk_usage(manager.root).free - 64 * 1024 ** 2):
            raise HTTPException(413, "录像过大或磁盘空间不足")
        job_id = manager.submit(payload, deferred=True)
        from app.arctime import companion_llm
        reservation = manager.active
        model = reservation['model']
        temporary = None
        owned_upload = None
        try:
            key = companion_llm.require_key(manager, model) if payload.saozi and manager.host is None else manager.api_key
            descriptor, name = tempfile.mkstemp(prefix=".saozi-upload-", dir=manager.root)
            temporary = Path(name)
            count = 0
            with os.fdopen(descriptor, "wb") as handle:
                owned_upload = OwnedUpload.from_descriptor(temporary, manager.root, descriptor)
                async for block in request.stream():
                    if shutil.disk_usage(manager.root).free < len(block) + 64 * 1024 ** 2:
                        raise HTTPException(413, "磁盘空间不足，导入已停止")
                    handle.write(block)
                    count += len(block)
                handle.flush()
                os.fsync(handle.fileno())
            if not count:
                raise HTTPException(422, "请选择非空录像文件")
            if manager.host is not None:
                manager.host.finish_upload(job_id, owned_upload)
                with manager.lock:
                    if manager.active is reservation:
                        manager.active = None
            else:
                manager.executor.submit(manager.run, job_id, payload, key, model, owned_upload=owned_upload)
            return {"id": job_id}
        except BaseException:
            try:
                try:
                    if manager.host is not None:
                        manager.host.fail_upload(job_id)
                    else:
                        manager.update("failed", "录像导入未完成，请重新选择文件", "导入失败，原录像未改变")
                except OSError:
                    logger.warning("upload_failure_record_deferred job_id=%s", job_id)
            finally:
                try:
                    if owned_upload is not None:
                        owned_upload.cleanup()
                    elif temporary:
                        logger.warning("upload_cleanup_deferred job_id=%s", job_id)
                except OSError:
                    logger.warning("upload_cleanup_deferred job_id=%s", job_id)
                finally:
                    with manager.lock:
                        if manager.active is reservation:
                            manager.last = reservation
                            manager.active = None
            raise

    @router.post("/jobs/{job_id}/stop", status_code=202)
    def stop(job_id: str):
        manager.stop(job_id)
        return {"id": job_id, "stopping": True}

    return router
