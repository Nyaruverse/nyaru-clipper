from __future__ import annotations

from pathlib import Path
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from sqlmodel import Session

from app.arctime import media
from app.models_unified import DocumentHead, TaskBinding
from app.services.task_artifacts import (
    ArtifactClip, ArtifactCue, ArtifactError, ArtifactFile, ResolvedArtifacts, WorkstationArtifacts, artifact_path, resolve_workstation,
)
from app.services.task_execution import Execution
from app.services.task_operations import canonical, require_token
from app.services.task_publication import Publisher
from app.services.unified_database import begin_unified_mutation


class _Range(BaseModel):
    model_config = ConfigDict(frozen=True, allow_inf_nan=False)
    start: float = Field(ge=0)
    end: float = Field(gt=0)


class _Clip(BaseModel):
    model_config = ConfigDict(frozen=True)
    video: str
    subtitles: str
    video_sha256: str
    subtitles_sha256: str


class _ASR(BaseModel):
    model_config = ConfigDict(frozen=True)
    language: str


class _Checkpoint(BaseModel):
    model_config = ConfigDict(frozen=True, allow_inf_nan=False)
    duration: float = Field(gt=0)
    video: str
    video_sha256: str
    subtitles: str
    artifacts: dict[str, str]
    completed_clips: tuple[_Clip, ...] = ()
    selection: tuple[_Range, ...] = ()
    asr: _ASR


class _Transcript(BaseModel):
    model_config = ConfigDict(frozen=True)
    segments: tuple[ArtifactCue, ...]


class _Translation(BaseModel):
    model_config = ConfigDict(frozen=True)
    state: str
    artifacts: dict[str, str]
    target_language: str | None = None


def _checked(directory: Path, name: str, checksum: str) -> Path:
    path = artifact_path(directory, name)
    if media.fingerprint(path) != checksum:
        raise ArtifactError('引擎检查点的产物摘要不匹配')
    return path


def _members(execution: Execution, publication_id: str) -> dict[str, ArtifactFile]:
    receipt = Publisher(execution.engine, execution.root).registered(publication_id)
    return {member.role: ArtifactFile(path=member.target, sha256=member.sha256) for member in receipt.outputs}


def publish_companion_result(execution: Execution, directory: Path) -> ResolvedArtifacts:
    job = _Checkpoint.model_validate_json(artifact_path(directory, 'job.json').read_bytes())
    source_id = execution.publish('recognition', {
        'source_video': _checked(directory, job.video, job.video_sha256),
        'transcript_json': _checked(directory, 'transcript.json', job.artifacts['transcript.json']),
        'subtitle_srt': _checked(directory, job.subtitles, job.artifacts[job.subtitles]),
    })
    source = _members(execution, source_id)
    clips = []
    if len(job.completed_clips) > len(job.selection):
        raise ArtifactError('切片选择与完成索引不一致')
    for index, (clip, bounds) in enumerate(zip(job.completed_clips, job.selection), start=1):
        publication_id = execution.publish(f'clip-{index:03d}', {
            'video': _checked(directory, clip.video, clip.video_sha256),
            'subtitles': _checked(directory, clip.subtitles, clip.subtitles_sha256),
        }, metadata={'clip_index': index, 'start': bounds.start, 'end': bounds.end})
        members = _members(execution, publication_id)
        clips.append(ArtifactClip(video=members['video'], start=bounds.start, end=bounds.end))
    with Session(execution.engine) as session:
        binding = session.get(TaskBinding, execution.task_id)
        if binding is None:
            raise ArtifactError('统一任务来源绑定缺失')
        instance, legacy_id = UUID(binding.source_instance_id), binding.legacy_id
    provenance = sorted((directory / 'whisperx').rglob('*.json')) if (directory / 'whisperx').is_dir() else []
    supporting = ()
    if provenance:
        provenance_id = execution.publish('recognition-provenance', {f'provenance_{index:04d}': path for index, path in enumerate(provenance)})
        supporting = tuple(_members(execution, provenance_id).values())
    context = WorkstationArtifacts(source_instance_id=instance, legacy_id=legacy_id, root=execution.root,
        duration=job.duration, video=source['source_video'], transcript=source['transcript_json'],
        subtitles=source['subtitle_srt'], source_language=job.asr.language, clips=tuple(clips), supporting=supporting)
    context = _save_context(execution, context)
    path = directory / 'translation.json'
    if path.is_file():
        translation = _Translation.model_validate_json(path.read_bytes())
        if translation.state == 'completed':
            context = _translated(execution, directory, context, translation)
            context = _save_context(execution, context)
    return resolve_workstation(context)


def _translated(execution: Execution, directory: Path, context: WorkstationArtifacts, state: _Translation) -> WorkstationArtifacts:
    bilingual = _checked(directory, 'subtitles.ja-zh.srt', state.artifacts['subtitles.ja-zh.srt'])
    source = _Transcript.model_validate_json(context.checked(context.transcript).read_bytes()).segments
    paired = media.read_subtitles(bilingual)
    if len(source) != len(paired):
        raise ArtifactError('译文与原始字幕数量不一致')
    rows = []
    for cue, pair in zip(source, paired, strict=True):
        prefix = cue.text + '\n'
        if (not pair.text.startswith(prefix) or abs(pair.start_seconds - cue.start_seconds) > .001001
                or abs(pair.end_seconds - cue.end_seconds) > .001001):
            raise ArtifactError('译文与原始时间轴不一致')
        rows.append(cue.model_copy(update={'translated_text': pair.text.removeprefix(prefix)}).model_dump(mode='json'))
    normalized = execution.staging('translation') / 'transcript.json'
    normalized.write_text(canonical({'segments': rows}), encoding='utf-8')
    publication_id = execution.publish('translation', {'transcript_json': normalized, 'bilingual_srt': bilingual})
    translated = _members(execution, publication_id)['transcript_json']
    target = state.target_language or {'ja': 'zh', 'zh': 'ja'}.get(context.source_language, 'mixed')
    return context.model_copy(update={'translation': translated, 'target_language': target})


def _source_content(context: WorkstationArtifacts) -> tuple:
    return (context.source_instance_id, context.legacy_id, context.duration, context.source_language,
        context.video.sha256, context.transcript.sha256, context.subtitles.sha256,
        tuple((clip.video.sha256, clip.start, clip.end) for clip in context.clips))


def _save_context(execution: Execution, context: WorkstationArtifacts) -> WorkstationArtifacts:
    resolve_workstation(context)
    with Session(execution.engine) as session:
        begin_unified_mutation(session)
        require_token(session, execution.operation_id, execution.token)
        binding = session.get(TaskBinding, execution.task_id)
        if binding is None or binding.state != 'activated':
            raise ArtifactError('统一任务尚未激活')
        if binding.context_json != '{}':
            prior = WorkstationArtifacts.model_validate_json(binding.context_json)
            if (_source_content(prior) == _source_content(context)
                    and (context.translation is None or (prior.translation is not None and
                        prior.translation.sha256 == context.translation.sha256 and prior.target_language == context.target_language))):
                resolve_workstation(prior)
                return prior
            if prior.fingerprint != context.fingerprint and session.get(DocumentHead, execution.task_id) is not None:
                raise ArtifactError('已有编辑稿的来源发生变化，保留原稿及新产物，请检查后合并')
        binding.context_json = context.model_dump_json()
        session.add(binding)
        session.commit()
        return context
