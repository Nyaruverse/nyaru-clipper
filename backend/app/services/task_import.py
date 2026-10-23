"""Read-only migration discovery. No locks, mapping writes, activation, or execution.

The caller supplies an externally registered instance UUID. A task generation is
only a discovery snapshot; P5 must also bind global state and verify under guards.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from pathlib import Path
from typing import Annotated, Literal, NoReturn
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, ValidationError

Digest = Annotated[str, Field(pattern=r'^[0-9a-f]{64}$')]
Eligibility = Literal['terminal', 'requires_withdrawal', 'active', 'rejected']
Issue = Literal['invalid_manifest', 'missing_artifact', 'artifact_mismatch',
                'unsafe_path', 'source_changed', 'unreadable_source']


class ImportIdentity(BaseModel):
    model_config = ConfigDict(frozen=True, extra='forbid')
    source_instance_id: UUID
    legacy_id: str = Field(pattern=r'^[0-9a-f]{12}$')


class DiscoveryItem(BaseModel):
    model_config = ConfigDict(frozen=True, extra='forbid')
    identity: ImportIdentity
    eligibility: Eligibility
    task_generation: Digest | None = None
    issue: Issue | None = None


class _Clip(BaseModel):
    model_config = ConfigDict(frozen=True)
    video: str
    subtitles: str
    video_sha256: Digest
    subtitles_sha256: Digest


class _Manifest(BaseModel):
    model_config = ConfigDict(frozen=True, allow_inf_nan=False)
    version: Literal[2]
    state: str
    duration: float = Field(gt=0)
    video: str | None = None
    video_sha256: Digest | None = None
    subtitles: str
    artifacts: dict[str, Digest] = Field(default_factory=dict)
    completed_clips: tuple[_Clip, ...] = ()


class _Activity(BaseModel):
    model_config = ConfigDict(frozen=True)
    state: str | None = None
    active: _Activity | None = None


class _Output(BaseModel):
    model_config = ConfigDict(frozen=True)
    filename: str
    sha256: Digest


class _Index(_Activity):
    artifacts: dict[str, Digest] = Field(default_factory=dict)
    outputs: tuple[_Output, ...] = ()


class _Rejected(ValueError):
    def __init__(self, issue: Issue) -> None:
        self.issue = issue
        super().__init__(issue)


def _walk_error(error: OSError) -> NoReturn:
    raise error


def _paths(directory: Path) -> list[Path]:
    paths = []
    for parent, directories, files in os.walk(directory, followlinks=False, onerror=_walk_error):
        if any((Path(parent) / name).is_symlink() for name in directories):
            raise _Rejected('unsafe_path')
        paths.extend(Path(parent) / name for name in files if name != '.lock')
    return sorted(paths)


def _signature(path: Path) -> tuple[int, int, int, int, int]:
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode):
        raise _Rejected('unsafe_path')
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns


def _hash(path: Path) -> str:
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(descriptor, 'rb') as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise _Rejected('unsafe_path')
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def _artifact(name: str, digests: dict[str, str], expected: str) -> None:
    if Path(name).name != name or name in {'.', '..'}:
        raise _Rejected('unsafe_path')
    if name not in digests:
        raise _Rejected('missing_artifact')
    if digests[name] != expected:
        raise _Rejected('artifact_mismatch')


def _discover(directory: Path, identity: ImportIdentity) -> DiscoveryItem:
    if directory.is_symlink() or not directory.is_dir():
        raise _Rejected('unsafe_path')
    root_identity = directory.stat().st_dev, directory.stat().st_ino
    paths = _paths(directory)
    signatures = {path: _signature(path) for path in paths}
    digests = {str(path.relative_to(directory)): _hash(path) for path in paths}
    manifest = _Manifest.model_validate_json((directory / 'job.json').read_bytes())
    if manifest.video is None or manifest.video_sha256 is None:
        raise _Rejected('missing_artifact')
    for name, expected in [(manifest.video, manifest.video_sha256), *manifest.artifacts.items()]:
        _artifact(name, digests, expected)
    if manifest.subtitles not in manifest.artifacts:
        raise _Rejected('missing_artifact')
    for clip in manifest.completed_clips:
        _artifact(clip.video, digests, clip.video_sha256)
        _artifact(clip.subtitles, digests, clip.subtitles_sha256)
    for path in paths:
        if path.suffix == '.json':
            json.loads(path.read_bytes())
    generation = hashlib.sha256(json.dumps(digests, sort_keys=True).encode()).hexdigest()
    state_eligibilities: dict[str, Eligibility] = {
        'completed': 'terminal', 'failed': 'terminal', 'interrupted': 'terminal',
        'cancelled': 'terminal', 'queued': 'requires_withdrawal',
    }
    eligibility = state_eligibilities.get(manifest.state, 'active')
    for name in ['gui.json', 'translation.json', 'subtitle-exports.json', 'subtitle-export-activity.json']:
        if name in digests:
            activity = _Index.model_validate_json((directory / name).read_bytes())
            for artifact, expected in activity.artifacts.items():
                _artifact(artifact, digests, expected)
            for output in activity.outputs:
                _artifact(output.filename, digests, output.sha256)
            states = [activity.state, activity.active.state if activity.active else None]
            if any(state not in {None, 'completed', 'failed', 'interrupted', 'cancelled', 'partial', 'not_started'}
                   for state in states):
                eligibility = 'active'
    if (paths != _paths(directory) or signatures != {path: _signature(path) for path in paths}
            or root_identity != (directory.stat().st_dev, directory.stat().st_ino)):
        raise _Rejected('source_changed')
    return DiscoveryItem(identity=identity, eligibility=eligibility, task_generation=generation)


def discover_companion(root: Path, source_instance_id: UUID) -> tuple[DiscoveryItem, ...]:
    """Inspect plain legacy task directories without creating even a lock file.

    Untrusted exception text, metadata, URLs, and paths never enter the report.
    A terminal manifest is not proof that all old writers have stopped.
    """
    if root.is_symlink() or not root.is_dir():
        if not root.exists():
            raise FileNotFoundError(root)
        message = 'Discovery requires an existing plain root directory'
        raise ValueError(message)
    result = []
    for directory in sorted(root.iterdir()):
        if re.fullmatch(r'[0-9a-f]{12}', directory.name) is None:
            continue
        identity = ImportIdentity(source_instance_id=source_instance_id, legacy_id=directory.name)
        try:
            result.append(_discover(directory, identity))
        except _Rejected as error:
            result.append(DiscoveryItem(identity=identity, eligibility='rejected', issue=error.issue))
        except (ValidationError, json.JSONDecodeError, UnicodeError):
            result.append(DiscoveryItem(identity=identity, eligibility='rejected', issue='invalid_manifest'))
        except FileNotFoundError:
            result.append(DiscoveryItem(identity=identity, eligibility='rejected', issue='missing_artifact'))
        except OSError:
            result.append(DiscoveryItem(identity=identity, eligibility='rejected', issue='unreadable_source'))
    return tuple(result)
