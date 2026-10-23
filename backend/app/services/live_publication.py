from __future__ import annotations

from pathlib import Path
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, JsonValue
from sqlmodel import Session

from app.arctime import media
from app.arctime.subtitle_inputs import ExportRequest
from app.arctime.subtitle_templates import ProjectTemplates, StyleTemplate
from app.models_unified import TaskBinding
from app.services.publication_reuse import reuse_publication
from app.services.task_artifacts import ArtifactClip, ArtifactCue, ArtifactError, ArtifactFile, ResolvedArtifacts, WorkstationArtifacts, artifact_path, resolve_workstation
from app.services.task_execution import Execution
from app.services.task_operations import canonical
from app.services.task_publication import Publisher
from app.services.unified_exports import export_result


class LiveClip(BaseModel):
    model_config = ConfigDict(frozen=True)
    video: str
    subtitles: str
    video_sha256: str
    subtitles_sha256: str


class _Bounds(BaseModel):
    model_config = ConfigDict(frozen=True, allow_inf_nan=False)
    start: float = Field(ge=0)
    end: float = Field(gt=0)


class _ASR(BaseModel):
    language: str


class _Job(BaseModel):
    completed_clips: tuple[LiveClip, ...]
    selection: tuple[_Bounds, ...]
    asr: _ASR
    discontinuities: tuple[float, ...] = ()


def _references(execution: Execution, identifier: str) -> dict[str, ArtifactFile]:
    receipt = Publisher(execution.engine, execution.root).registered(identifier)
    return {member.role: ArtifactFile(path=member.target, sha256=member.sha256) for member in receipt.outputs}


def clip_context(execution: Execution, directory: Path, job: _Job, index: int) -> ResolvedArtifacts:
    clip, bounds = job.completed_clips[index], job.selection[index]
    key = f'live-clip-{index + 1:03d}'
    metadata: dict[str, JsonValue] = {'clip_index': index + 1, 'start': bounds.start, 'end': bounds.end,
        'discontinuities': [gap for gap in job.discontinuities if bounds.start <= gap <= bounds.end]}
    prior = reuse_publication(execution, key, metadata=metadata)
    if prior is None:
        video, subtitles = artifact_path(directory, clip.video), artifact_path(directory, clip.subtitles)
        if media.fingerprint(video) != clip.video_sha256 or media.fingerprint(subtitles) != clip.subtitles_sha256:
            raise ArtifactError('直播切片摘要发生变化')
        original = media.read_subtitles(subtitles)
        duration = bounds.end - bounds.start
        if any(cue.end_seconds > duration + .001001 for cue in original):
            raise ArtifactError('直播切片字幕超出选定时间范围')
        rows = [ArtifactCue(id=cue.id, start_seconds=cue.start_seconds, end_seconds=min(duration, cue.end_seconds),
            text=cue.text).model_dump(mode='json') for cue in original]
        transcript = execution.staging(key) / 'transcript.json'
        transcript.write_text(canonical({'segments': rows}), encoding='utf-8')
        identifier = execution.publish(key, {'video': video, 'subtitles': subtitles, 'transcript_json': transcript}, metadata=metadata)
    else:
        identifier = prior.publication_id
    members = _references(execution, identifier)
    with Session(execution.engine) as session:
        binding = session.get(TaskBinding, execution.task_id)
        if binding is None:
            raise ArtifactError('直播任务来源绑定缺失')
        instance, legacy_id = UUID(binding.source_instance_id), binding.legacy_id
    context = WorkstationArtifacts(source_instance_id=instance, legacy_id=legacy_id, root=execution.root,
        duration=bounds.end - bounds.start, video=members['video'], transcript=members['transcript_json'],
        subtitles=members['subtitles'], source_language=job.asr.language,
        clips=(ArtifactClip(video=members['video'], start=0., end=bounds.end - bounds.start),))
    translated = directory / 'translation.json'
    if translated.is_file():
        import json
        state = json.loads(translated.read_bytes())
        name = Path(clip.subtitles).stem + '.ja-zh.srt'
        expected = state.get('artifacts', {}).get(name)
        if expected is not None:
            bilingual = artifact_path(directory, name)
            if media.fingerprint(bilingual) != expected:
                raise ArtifactError('直播双语切片摘要不匹配')
            original = resolve_workstation(context).cues
            paired = media.read_subtitles(bilingual)
            if len(original) != len(paired):
                raise ArtifactError('直播双语切片数量不匹配')
            rows = []
            for cue, pair in zip(original, paired, strict=True):
                if (not pair.text.startswith(cue.text + '\n') or abs(cue.start_seconds - pair.start_seconds) > .001001
                        or abs(cue.end_seconds - pair.end_seconds) > .001001):
                    raise ArtifactError('直播双语切片时间或原文不匹配')
                rows.append(cue.model_copy(update={'translated_text': pair.text[len(cue.text) + 1:]}).model_dump(mode='json'))
            key = f'live-bilingual-{index + 1:03d}:' + expected
            bilingual_metadata = {**metadata, 'source_language': job.asr.language}
            prior = reuse_publication(execution, key, metadata=bilingual_metadata)
            if prior is None:
                normalized = execution.staging(key) / 'translated.json'
                normalized.write_text(canonical({'segments': rows}), encoding='utf-8')
                identifier = execution.publish(key, {'transcript_json': normalized, 'bilingual_srt': bilingual}, metadata=bilingual_metadata)
            else:
                identifier = prior.publication_id
            context = context.model_copy(update={'translation': _references(execution, identifier)['transcript_json'],
                'target_language': {'ja': 'zh', 'zh': 'ja'}.get(job.asr.language, 'mixed')})
    return resolve_workstation(context)


def publish_live_clips(execution: Execution, directory: Path, body: dict[str, JsonValue],
                       template: StyleTemplate | None, templates: ProjectTemplates) -> None:
    job = _Job.model_validate(body)
    if len(job.selection) < len(job.completed_clips):
        raise ArtifactError('直播切片选择缺失')
    for index in range(len(job.completed_clips)):
        execution.check()
        context = clip_context(execution, directory, job, index)
        if template is not None:
            document = context.document(template.style)
            for kind in ('ass', 'burn'):
                export_result(execution, context, ExportRequest(kind=kind, video='clip-001.mp4', style=template.style,
                    bilingual=context.source.translation is not None, document=document), templates,
                    video_label=f'clip-{index + 1:03d}.mp4')
