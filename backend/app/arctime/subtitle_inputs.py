from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.arctime import media, workflow
from app.arctime.subtitle_style import SubtitleStyle
from app.services.subtitles import SubtitleSegment


class ExportError(ValueError):
    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


class ExportRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    kind: Literal["ass", "burn", "arctime"]
    video: str = Field(pattern=r"^(source|clip-\d{3})\.mp4$")
    bilingual: bool = False
    style: SubtitleStyle
    arctime_template_id: str | None = None


class CompletedClip(BaseModel):
    video: str
    subtitles: str
    video_sha256: str
    subtitles_sha256: str


class ManagedRun(BaseModel):
    state: str
    duration: float
    video: str
    video_sha256: str
    subtitles: str
    artifacts: dict[str, str]
    completed_clips: list[CompletedClip]


class TranslationRun(BaseModel):
    state: str
    artifacts: dict[str, str] = Field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ExportInputs:
    source: Path
    original: list[SubtitleSegment]
    translated: list[SubtitleSegment] | None
    time_origin: float
    digests: dict[str, str]


def checked_artifact(directory: Path, name: str, digest: str) -> Path:
    path = workflow._path(directory, name)
    if not path.is_file() or media.fingerprint(path) != digest:
        raise ExportError("原任务文件缺失或已改变；已保留文件，请检查任务")
    return path


def load_inputs(directory: Path, request: ExportRequest) -> ExportInputs:
    job_path = workflow._path(directory, "job.json")
    run = ManagedRun.model_validate_json(job_path.read_bytes())
    if run.state != "completed":
        raise ExportError("请等待视频任务完成后再导出字幕")
    if request.kind == "burn" and request.video == "source.mp4":
        raise ExportError("字幕烧录请选择已完成切片")
    digests = {run.video: run.video_sha256, **run.artifacts}
    for name, digest in digests.items():
        checked_artifact(directory, name, digest)
    subtitle_name = run.subtitles
    time_origin = 0.0
    if request.video != run.video:
        clip = next((clip for clip in run.completed_clips if clip.video == request.video), None)
        if clip is None:
            raise ExportError("请选择当前任务的完整视频或已完成切片")
        digests.update({clip.video: clip.video_sha256, clip.subtitles: clip.subtitles_sha256})
        subtitle_name = clip.subtitles
        checked_artifact(directory, clip.subtitles, clip.subtitles_sha256)
    source = checked_artifact(directory, request.video, digests[request.video])
    subtitle = checked_artifact(directory, subtitle_name, digests[subtitle_name])
    original = media.read_subtitles(subtitle) if subtitle.read_text(encoding="utf-8").strip() else []
    translated = None
    if request.bilingual:
        translation_path = workflow._path(directory, "translation.json")
        if not translation_path.is_file():
            raise ExportError("请先完成中日双语字幕")
        result = TranslationRun.model_validate_json(translation_path.read_bytes())
        if result.state != "completed":
            raise ExportError("请先完成中日双语字幕")
        bilingual_name = Path(subtitle_name).stem + ".ja-zh.srt"
        bilingual_path = checked_artifact(directory, bilingual_name, result.artifacts.get(bilingual_name, ""))
        digests[bilingual_name] = result.artifacts[bilingual_name]
        bilingual = media.read_subtitles(bilingual_path) if bilingual_path.read_text(encoding="utf-8").strip() else []
        if len(original) != len(bilingual):
            raise ExportError("双语字幕与原文数量不一致")
        translated = []
        for cue, paired in zip(original, bilingual, strict=True):
            prefix = cue.text + "\n"
            if (cue.start_seconds != paired.start_seconds or cue.end_seconds != paired.end_seconds
                    or not paired.text.startswith(prefix) or not paired.text[len(prefix):].strip()):
                raise ExportError("双语字幕的文字或时间轴与原文不一致")
            translated.append(SubtitleSegment(cue.id, cue.start_seconds, cue.end_seconds, paired.text[len(prefix):]))
    return ExportInputs(source, original, translated, time_origin, digests)
