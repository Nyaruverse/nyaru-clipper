from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Body, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import Field
from sqlmodel import Session

from app.api.schemas.operations import AnalyzeTopicsOperation, ExportTopicsOperation
from app.arctime.companion_manager import JobManager
from app.arctime.topic_models import (
    TopicAnalyzeOptions,
    TopicClipOptions,
    TopicModel,
    TopicSegmentStore,
)
from app.arctime.topic_danmaku import MAX_DANMAKU_BYTES, parse_danmaku
from app.arctime.unified_host import NativeHost
from app.services.task_operations import OperationConflict, enqueue_operation
from app.services.topic_admission import danmaku_store
from app.services.topic_results import (
    TopicClipsView,
    clips_snapshot,
    topic_download,
    topic_snapshot,
)


class Admission(TopicModel):
    operation_id: str
    state: Literal["queued"] = "queued"


class DanmakuUpload(TopicModel):
    content: str = Field(max_length=MAX_DANMAKU_BYTES)
    streamer: str | None = Field(default=None, min_length=1, max_length=128)


class DanmakuSummary(TopicModel):
    count: int
    source: str | None


def topic_router(manager: JobManager) -> APIRouter:
    router = APIRouter(prefix="/companion-api/jobs/{job_id}", tags=["topics"])

    def host_for(job_id: str) -> NativeHost:
        if manager.host is None:
            raise HTTPException(
                409, "unified-entry-required: 请从统一宿主入口使用内容切片"
            )
        manager.host.context(job_id)
        return manager.host

    def admit(
        host: NativeHost, payload: AnalyzeTopicsOperation | ExportTopicsOperation
    ) -> Admission:
        try:
            configuration = host.configuration(payload)
            with Session(host.engine) as session:
                operation = enqueue_operation(
                    session,
                    payload.task_id,
                    payload.kind,
                    {
                        "input": payload.model_dump(
                            mode="json", exclude={"kind", "task_id"}
                        ),
                        "config": configuration,
                    },
                )
                result = Admission(operation_id=operation.id)
                session.commit()
                return result
        except OSError:
            raise HTTPException(409, "切片输入无法读取；请检查已登记文件") from None
        except ValueError as error:
            raise HTTPException(409, str(error)) from None

    @router.get("/topic-segments", response_model=TopicSegmentStore)
    def topics(job_id: str) -> TopicSegmentStore:
        try:
            return topic_snapshot(host_for(job_id), job_id)
        except (ValueError, OSError):
            raise HTTPException(
                409, "已登记分析无法读取；请保留原文件并检查记录"
            ) from None

    @router.post("/topic-segments", status_code=202, response_model=Admission)
    def analyze(
        job_id: str, payload: TopicAnalyzeOptions = Body(default=TopicAnalyzeOptions())
    ) -> Admission:
        host = host_for(job_id)
        return admit(
            host,
            AnalyzeTopicsOperation(
                kind="analyze_topics", task_id=job_id, request=payload
            ),
        )

    @router.get("/danmaku", response_model=DanmakuSummary)
    def danmaku(job_id: str) -> DanmakuSummary:
        stored = danmaku_store(host_for(job_id), job_id)
        return DanmakuSummary(count=len(stored.entries), source=stored.source)

    @router.post("/danmaku", response_model=DanmakuSummary)
    async def upload(job_id: str, request: Request) -> DanmakuSummary:
        host = host_for(job_id)
        data = bytearray()
        async for chunk in request.stream():
            data.extend(chunk)
            if len(data) > MAX_DANMAKU_BYTES:
                raise HTTPException(413, "弹幕上传超过 8 MiB 上限")
        try:
            payload = DanmakuUpload.model_validate_json(bytes(data))
            stored = parse_danmaku(payload.content).model_copy(
                update={"streamer": payload.streamer}
            )
            with host.globals.mutation():
                host.globals.write(
                    f"topics/{job_id}/danmaku.json", stored.model_dump_json().encode()
                )
        except ValueError:
            raise HTTPException(
                422, "无效 ASS/XML 弹幕；请检查时间、条数与文本长度"
            ) from None
        return DanmakuSummary(count=len(stored.entries), source=stored.source)

    @router.post("/topic-clips", status_code=202, response_model=Admission)
    def export(job_id: str, payload: TopicClipOptions) -> Admission:
        host = host_for(job_id)
        return admit(
            host,
            ExportTopicsOperation(
                kind="export_topics", task_id=job_id, request=payload
            ),
        )

    @router.get("/topic-clips", response_model=TopicClipsView)
    def clips(job_id: str) -> TopicClipsView:
        try:
            return clips_snapshot(host_for(job_id), job_id)
        except (ValueError, OSError):
            raise HTTPException(
                409, "已登记导出无法读取；请保留原文件并检查记录"
            ) from None

    @router.get("/topic-clips/files/{publication_id}/{role}")
    def download(job_id: str, publication_id: str, role: str) -> FileResponse:
        try:
            path = topic_download(host_for(job_id), job_id, publication_id, role)
        except (OperationConflict, OSError, ValueError):
            raise HTTPException(404, "切片文件不存在或校验失败") from None
        return FileResponse(path, filename=role + ".mp4", media_type="video/mp4")

    return router
