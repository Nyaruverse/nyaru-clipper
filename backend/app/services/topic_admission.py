from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import JsonValue

from app.api.schemas.operations import AnalyzeTopicsOperation, ExportTopicsOperation
from app.arctime import companion_llm
from app.arctime.topic_models import DanmakuStore, ScoringConfig
from app.services.task_operations import OperationConflict, digest
from app.services.task_requests import freeze_request
from app.services.topic_results import topic_snapshot

if TYPE_CHECKING:
    from app.arctime.unified_host import NativeHost


def danmaku_store(host: NativeHost, task_id: str) -> DanmakuStore:
    body = host.globals.read(f"topics/{task_id}/danmaku.json")
    return DanmakuStore.model_validate_json(body) if body else DanmakuStore()


def topic_configuration(
    host: NativeHost, payload: AnalyzeTopicsOperation | ExportTopicsOperation
) -> dict[str, JsonValue]:
    context = host.context(payload.task_id)
    if context is None:
        raise OperationConflict("视频与字幕尚未就绪")
    document = host.documents.load(
        payload.task_id, context.document(host.templates.load_defaults())
    )
    if not document.cues:
        raise OperationConflict("没有可分析的字幕")
    config = {
        "topic_document": freeze_request(
            host.root,
            payload.task_id,
            {"request": {"document": document.model_dump(mode="json")}},
        ),
        "topic_document_revision": document.revision,
        "topic_document_sha256": digest(document.model_dump_json()),
    }
    match payload:
        case AnalyzeTopicsOperation(request=request):
            if (request.start_seconds or 0) >= document.duration or (
                request.end_seconds or 0
            ) > document.duration:
                raise OperationConflict("分析范围超过视频时长")
            if not any(
                cue.end_seconds > (request.start_seconds or 0)
                and (
                    request.end_seconds is None
                    or cue.start_seconds < request.end_seconds
                )
                for cue in document.cues
            ):
                raise OperationConflict("分析范围内没有字幕")
            credentials = companion_llm.LLMConfig(
                host.root,
                settings_root=host.settings_root,
                credential_root=host.credential_root,
                preferences=host.globals,
            )
            try:
                model = companion_llm.selected_model(credentials)
                companion_llm.require_key(credentials, model)
            except ValueError as error:
                raise OperationConflict(str(error)) from None
            finally:
                credentials.chatgpt.close()
            config["llm_model"] = model
            from app.services.topic_profiles import profile_identity, load_profile

            danmaku = danmaku_store(host, payload.task_id)
            profile_key, label = profile_identity(host, payload.task_id, danmaku)
            profile = load_profile(host, profile_key)
            config["topic_profile_key"] = profile_key
            config["topic_danmaku"] = danmaku.model_dump(mode="json")
            config["topic_scoring"] = ScoringConfig(
                streamer=label, profile_terms=profile.terms
            ).model_dump(mode="json")
        case ExportTopicsOperation(request=request):
            result = topic_snapshot(host, payload.task_id)
            if (
                result.state != "completed"
                or result.document_sha256 != config["topic_document_sha256"]
            ):
                raise OperationConflict("话题分析尚未完成或字幕已改变，请重新分析")
            if any(
                index >= len(result.segments) or not result.segments[index].analyzed
                for index in request.indices
            ):
                raise OperationConflict("切片索引越界或未分析")
            if any(item.end_seconds > document.duration for item in request.ranges):
                raise OperationConflict("切片范围超过视频时长")
            if request.ranges:
                ranges = {item.index: item for item in request.ranges}
                result = result.model_copy(
                    update={
                        "segments": [
                            segment.model_copy(
                                update={
                                    "start_seconds": ranges[index].start_seconds,
                                    "end_seconds": ranges[index].end_seconds,
                                }
                            )
                            if index in ranges
                            else segment
                            for index, segment in enumerate(result.segments)
                        ]
                    }
                )
            if request.variant in {"zh", "bilingual"}:
                if request.variant == "zh" and context.source.source_language == "zh":
                    pass
                elif not all(
                    cue.translation.strip()
                    for index in request.indices
                    for cue in document.cues
                    if cue.end_seconds > result.segments[index].start_seconds
                    and cue.start_seconds < result.segments[index].end_seconds
                ):
                    raise OperationConflict("所选片段缺少翻译字幕")
                elif request.variant == "zh" and context.source.target_language not in {
                    None,
                    "zh",
                }:
                    raise OperationConflict("当前译文不是中文")
            config["topic_result"] = result.model_dump(mode="json")
            config["topic_source_language"] = context.source.source_language
        case unreachable:
            from typing import assert_never

            assert_never(unreachable)
    return config
