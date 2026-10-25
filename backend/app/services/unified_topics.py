from __future__ import annotations

from typing import TYPE_CHECKING, assert_never

from pydantic import JsonValue, TypeAdapter

from app.api.schemas.operations import AnalyzeTopicsOperation, ExportTopicsOperation
from app.arctime import companion_llm
from app.arctime.subtitle_document import SubtitleDocument, clip_document
from app.arctime.subtitle_encoding import subtitle_ffmpeg
from app.arctime.subtitle_render import render_document_ass
from app.arctime.topic_models import DanmakuStore, ScoringConfig, TopicSegmentStore
from app.arctime.topic_scoring import score_topics
from app.arctime.topic_segments import analyze_document
from app.services.publication_reuse import reuse_publication
from app.services.task_execution import Execution, WorkflowFailure
from app.services.task_operations import canonical, digest
from app.services.task_requests import restore_request

if TYPE_CHECKING:
    from app.arctime.unified_host import NativeHost


def execute_topics(
    host: NativeHost,
    execution: Execution,
    payload: AnalyzeTopicsOperation | ExportTopicsOperation,
    configuration: dict[str, JsonValue],
) -> None:
    frozen = restore_request(host.root, configuration["topic_document"])
    document = SubtitleDocument.model_validate(frozen["request"]["document"])
    key = "topics:" + digest(
        canonical({"input": payload.model_dump(mode="json"), "config": configuration})
    )
    reused = reuse_publication(execution, key)
    if reused is not None:
        if isinstance(payload, AnalyzeTopicsOperation):
            from app.services.unified_files import checked_path
            from app.services.topic_profiles import accumulate_profile

            member = next(
                member for member in reused.outputs if member.role == "topics"
            )
            result = TopicSegmentStore.model_validate_json(
                checked_path(host.root, member.target).read_bytes()
            )
            accumulate_profile(
                host,
                execution,
                TypeAdapter(str).validate_python(configuration["topic_profile_key"]),
                result,
            )
        return
    match payload:
        case AnalyzeTopicsOperation(request=request):
            credentials = companion_llm.LLMConfig(
                host.root,
                settings_root=host.settings_root,
                credential_root=host.credential_root,
                preferences=host.globals,
            )
            try:
                model = TypeAdapter(str).validate_python(configuration["llm_model"])
                result = analyze_document(
                    execution,
                    document,
                    request,
                    model,
                    companion_llm.require_key(credentials, model),
                    companion_llm.requester(credentials, model),
                )
            finally:
                credentials.chatgpt.close()
            from app.arctime.topic_audio import audio_features, apply_audio

            context = host.context(execution.task_id)
            if context is None:
                raise WorkflowFailure("missing_input")
            audio = audio_features(
                execution,
                context.source.checked(context.source.video),
                document.duration,
            )
            result = apply_audio(result, audio)
            result = score_topics(
                result,
                document.cues,
                DanmakuStore.model_validate(configuration["topic_danmaku"]).entries,
                ScoringConfig.model_validate(configuration["topic_scoring"]),
            )
            path = execution.staging(key) / "topics.json"
            path.write_text(result.model_dump_json(), encoding="utf-8")
            execution.check()
            execution.publish(
                key,
                {"topics": path},
                document_sha256=digest(document.model_dump_json()),
            )
            from app.services.topic_profiles import accumulate_profile

            accumulate_profile(
                host,
                execution,
                TypeAdapter(str).validate_python(configuration["topic_profile_key"]),
                result,
            )
        case ExportTopicsOperation():
            export_topics(host, execution, payload, configuration, document, key)
        case unreachable:
            assert_never(unreachable)


def export_topics(
    host: NativeHost,
    execution: Execution,
    payload: ExportTopicsOperation,
    configuration: dict[str, JsonValue],
    document: SubtitleDocument,
    key: str,
) -> None:
    context = host.context(execution.task_id)
    if context is None:
        raise WorkflowFailure("missing_input")
    context.verify()
    source = context.source.checked(context.source.video)
    topics = TopicSegmentStore.model_validate(configuration["topic_result"])
    workspace = execution.staging(key)
    products = {}
    ordered = []
    for index in payload.request.indices:
        execution.check()
        segment = topics.segments[index]
        clipped = clip_document(document, segment.start_seconds, segment.end_seconds)
        if (
            payload.request.variant == "zh"
            and configuration.get("topic_source_language") != "zh"
        ):
            clipped = clipped.model_copy(
                update={
                    "cues": [
                        cue.model_copy(
                            update={
                                "text": cue.translation,
                                "original_style": cue.translation_style,
                                "original_emphasis": cue.translation_emphasis,
                            }
                        )
                        for cue in clipped.cues
                    ]
                }
            )
        filename = f"clip-{index:03d}"
        subtitle = workspace / f"{filename}.ass"
        subtitle.write_text(
            render_document_ass(clipped, payload.request.variant == "bilingual"),
            encoding="utf-8",
        )
        output = workspace / f"{filename}.mp4"
        result = execution.run_command(
            [
                subtitle_ffmpeg(),
                "-v",
                "error",
                "-nostdin",
                "-y",
                "-ss",
                str(segment.start_seconds),
                "-i",
                str(source),
                "-t",
                str(segment.end_seconds - segment.start_seconds),
                "-map",
                "0:v:0",
                "-map",
                "0:a:0?",
                "-vf",
                f"ass={subtitle.name}",
                "-c:v",
                "libx264",
                "-preset",
                "fast",
                "-crf",
                "20",
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "aac",
                "-movflags",
                "+faststart",
                output.name,
            ],
            cwd=workspace,
        )
        if result.returncode != 0 or not output.is_file() or output.stat().st_size == 0:
            raise WorkflowFailure("topic_export_ffmpeg_failed")
        products[filename] = output
        products[f"subtitle-{index:03d}"] = subtitle
        ordered.append(output.name)
    if payload.request.mode == "combined":
        concat = workspace / "concat.txt"
        concat.write_text(
            "".join(f"file '{name}'\n" for name in ordered), encoding="utf-8"
        )
        output = workspace / "combined.mp4"
        result = execution.run_command(
            [
                subtitle_ffmpeg(),
                "-v",
                "error",
                "-nostdin",
                "-y",
                "-f",
                "concat",
                "-safe",
                "1",
                "-i",
                concat.name,
                "-c",
                "copy",
                "-movflags",
                "+faststart",
                output.name,
            ],
            cwd=workspace,
        )
        if result.returncode != 0 or not output.is_file() or output.stat().st_size == 0:
            raise WorkflowFailure("topic_concat_ffmpeg_failed")
        products["combined"] = output
    snapshot = workspace / "document.json"
    snapshot.write_text(document.model_dump_json(), encoding="utf-8")
    products["document"] = snapshot
    execution.check()
    execution.publish(
        key,
        products,
        document_sha256=digest(snapshot.read_bytes()),
        metadata={
            "topic_export": True,
            "indices": payload.request.indices,
            "mode": payload.request.mode,
            "variant": payload.request.variant,
        },
    )
