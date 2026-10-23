from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, ConfigDict, Field
from sqlmodel import Session, select

from app.models_migration import MigrationBatch, MigrationMember
from app.models_unified import TaskBinding
from app.services.migration_snapshot import Candidate
from app.services.task_artifacts import ArtifactError, ResolvedArtifacts
from app.services.unified_files import checked_path, file_sha256

if TYPE_CHECKING:
    from app.arctime.unified_host import NativeHost


class SelectionBounds(BaseModel):
    model_config = ConfigDict(frozen=True, allow_inf_nan=False)
    start: float = Field(ge=0)
    end: float = Field(gt=0)
    score: float | None = None
    reasons: tuple[str, ...] = ()


class MigratedSelection(BaseModel):
    model_config = ConfigDict(frozen=True)
    mode: Literal['ranges', 'highlights', 'saozi'] | None = None
    highlight_count: int | None = Field(default=None, ge=1)
    saozi: bool = False
    live: bool = False
    selection: tuple[SelectionBounds, ...] = ()

    @property
    def processing_mode(self) -> Literal['ranges', 'highlights', 'saozi']:
        return self.mode or ('saozi' if self.saozi else 'highlights' if self.highlight_count else 'ranges')


def migrated_selection(host: NativeHost, context: ResolvedArtifacts) -> MigratedSelection | None:
    """Read only the registered manifest; keep historical artifact fingerprints unchanged."""
    source = context.source
    with Session(host.engine) as session:
        binding = session.get(TaskBinding, source.task_id)
        if binding is None or binding.origin != 'companion':
            return None
        member = session.exec(select(MigrationMember).join(MigrationBatch).where(
            MigrationMember.task_id == source.task_id, MigrationMember.state == 'activated',
            MigrationBatch.group_id == binding.root_group_id,
            MigrationMember.generation == binding.source_generation).order_by(MigrationMember.id)).first()
        if member is None:
            return None
        path = checked_path(host.root, member.candidate_path)
        if file_sha256(path) != member.candidate_sha256:
            raise ArtifactError('迁移选择记录摘要不符；原文件与记录已保留')
        candidate = Candidate.model_validate_json(path.read_bytes())
        if (candidate.context.task_id != source.task_id or candidate.generation != member.generation
                or candidate.generation != binding.source_generation):
            raise ArtifactError('迁移选择记录身份不符')
    entry = next((item for item in candidate.files if item.role == 'tasks' and item.path == f'{source.legacy_id}/job.json'), None)
    if entry is None:
        return None
    archive = checked_path(host.root,
        f'.unified/imports/{candidate.source_id}/{candidate.generation}/archive/tasks/{entry.path}')
    if archive.stat().st_size != entry.size or file_sha256(archive) != entry.sha256:
        raise ArtifactError('迁移选择源摘要不符；原文件与记录已保留')
    result = MigratedSelection.model_validate_json(archive.read_bytes())
    if len(result.selection) < len(source.clips) or any(
        (clip.start, clip.end) != (bounds.start, bounds.end)
        for clip, bounds in zip(source.clips, result.selection)
    ):
        raise ArtifactError('迁移选择范围与登记切片不一致')
    return result
