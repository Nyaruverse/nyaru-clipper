from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from app.services.task_operations import OperationConflict
from app.services.unified_files import checked_path, file_sha256


class _Helper(BaseModel):
    offline_abi: str
    path: str


class _Bundle(BaseModel):
    model_config = ConfigDict(extra='allow', frozen=True)
    version: int
    schemas: list[str] = Field(alias='schema')
    runtime: str
    reader: str
    files: dict[str, str]
    legacy_helper: _Helper


def verify_bundle(path: Path, expected_sha256: str) -> None:
    if file_sha256(path) != expected_sha256:
        raise OperationConflict('independent recovery bundle pin mismatch')
    bundle = _Bundle.model_validate_json(path.read_bytes())
    if bundle.version != 1 or bundle.schemas != ['20261022_01'] or bundle.legacy_helper.offline_abi != 'nyaru-local-recovery-v1':
        raise OperationConflict('independent recovery ABI/schema mismatch')
    for name in (bundle.runtime, bundle.reader, bundle.legacy_helper.path, 'recovery_launcher.py',
                 'recovery_thaw.py', 'recovery_protection.py', 'recovery_thaw_snapshot.py', 'recovery_publications.py', 'frozen_recovery_guard.py'):
        if name not in bundle.files:
            raise OperationConflict('independent recovery runtime/reader/helper incomplete')
    for name, checksum in bundle.files.items():
        if file_sha256(checked_path(path.parent, name)) != checksum:
            raise OperationConflict('independent recovery dependency hash mismatch')
