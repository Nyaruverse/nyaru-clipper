from __future__ import annotations

import fcntl
import os
import stat
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, JsonValue

from app.services.task_operations import canonical
from app.services.unified_files import checked_path, file_sha256, immutable_bytes, make_parents


class GuardError(ValueError):
    pass


class SealEntry(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    root_index: int
    relative: str
    device: int
    inode: int
    mode: int
    flags: int
    sha256: str | None


class SealRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    version: Literal[1] = 1
    root_group_id: str
    profile: Literal["darwin-immutable", "readonly-mount"]
    roots: tuple[str, ...]
    locks: tuple[str, ...]
    entries: tuple[SealEntry, ...]


class Supervisor:
    def __init__(self, sources: tuple[Path, ...], guard_root: Path, credential_root: Path,
                 root_group_id: str, locks: tuple[Path, ...]) -> None:
        self.sources = tuple(path.absolute() for path in sources)
        self.guard_root, self.credential_root = guard_root.absolute(), credential_root.absolute()
        self.root_group_id = root_group_id
        self.locks = tuple(sorted(path.absolute() for path in locks))
        self.descriptors: list[int] = []
        if not self.sources or not self.locks:
            raise GuardError("source roots and existing old-entry locks are required")
        for root in self.sources:
            checked_path(root, ".probe")
            if not root.is_dir():
                raise GuardError("source protection root missing")
            if self.credential_root.is_relative_to(root) or root.is_relative_to(self.credential_root):
                raise GuardError("credential root overlaps the source protection domain")
            if self.guard_root.is_relative_to(root) or root.is_relative_to(self.guard_root):
                raise GuardError("guard records must be outside protected roots")
        if any(first != second and (first.is_relative_to(second) or second.is_relative_to(first)) for first in self.sources for second in self.sources):
            raise GuardError("protection roots overlap")
        if any(not any(lock.is_relative_to(root) for root in self.sources) for lock in self.locks):
            raise GuardError("old lock is outside the source protection domains")

    def __enter__(self) -> Supervisor:
        control = checked_path(self.guard_root, ".guard.lock")
        make_parents(control)
        try:
            self._hold(control, create=True)
            for path in self.locks:
                self._hold(path, create=False)
            if (self.guard_root / "sealed.json").exists() and not (self.guard_root / "thaw-allowed.json").exists():
                self.verify()
            return self
        except (OSError, ValueError):
            self.close()
            raise

    def _hold(self, path: Path, *, create: bool) -> None:
        descriptor = os.open(path, (os.O_CREAT | os.O_RDWR if create else os.O_RDONLY) | os.O_NOFOLLOW, 0o600)
        self.descriptors.append(descriptor)
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise GuardError("old writer or another Supervisor still owns a lock") from error

    def close(self) -> None:
        for descriptor in reversed(self.descriptors):
            os.close(descriptor)
        self.descriptors.clear()

    def __exit__(self, *_: BaseException | type[BaseException] | None) -> None:
        self.close()

    def _inventory(self) -> tuple[SealEntry, ...]:
        entries = []
        for index, root in enumerate(self.sources):
            for path in sorted([root, *root.rglob("*")]):
                if path.is_symlink() or not (path.is_file() or path.is_dir()):
                    raise GuardError("source contains unsupported links or special files")
                info = path.stat()
                if path.is_file() and info.st_nlink != 1:
                    raise GuardError("source hard links require a separate verified protection profile")
                entries.append(SealEntry(root_index=index, relative=path.relative_to(root).as_posix(),
                    device=info.st_dev, inode=info.st_ino, mode=stat.S_IMODE(info.st_mode), flags=getattr(info, "st_flags", 0),
                    sha256=file_sha256(path) if path.is_file() else None))
        return tuple(entries)

    def _record(self, name: str) -> SealRecord:
        record = SealRecord.model_validate_json(checked_path(self.guard_root, name).read_bytes())
        if (record.root_group_id != self.root_group_id or record.roots != tuple(map(str, self.sources))
                or record.locks != tuple(map(str, self.locks))):
            raise GuardError("guard identity or protection domains changed")
        return record

    def seal(self) -> SealRecord:
        if len(self.descriptors) != len(self.locks) + 1:
            raise GuardError("Supervisor must own all old locks before sealing")
        if (self.guard_root / "thaw-allowed.json").exists():
            raise GuardError("guard epoch was released; create a new guarded migration epoch")
        if (self.guard_root / "sealed.json").exists():
            return self.verify()
        if (self.guard_root / "preparing.json").exists():
            record = self._record("preparing.json")
        else:
            if sys.platform == "darwin":
                profile = "darwin-immutable"
            elif all(os.statvfs(root).f_flag & os.ST_RDONLY for root in self.sources):
                profile = "readonly-mount"
            else:
                raise GuardError("a verified persistent read-only mount profile is required on this platform")
            record = SealRecord(root_group_id=self.root_group_id, profile=profile, roots=tuple(map(str, self.sources)),
                locks=tuple(map(str, self.locks)), entries=self._inventory())
            immutable_bytes(checked_path(self.guard_root, "preparing.json"), canonical(record.model_dump(mode="json")).encode())
        for entry in sorted(record.entries, key=lambda entry: len(Path(entry.relative).parts), reverse=True):
            path = self.sources[entry.root_index] / entry.relative
            info = path.stat()
            if (info.st_dev, info.st_ino) != (entry.device, entry.inode):
                raise GuardError("source inode changed during sealing")
            if record.profile == "darwin-immutable" and not (info.st_flags & stat.UF_IMMUTABLE):
                path.chmod(entry.mode & ~0o222)
                os.chflags(path, entry.flags | stat.UF_IMMUTABLE)
        self._verify(record)
        immutable_bytes(checked_path(self.guard_root, "sealed.json"), canonical(record.model_dump(mode="json")).encode())
        return record

    def _verify(self, record: SealRecord) -> None:
        observed = {(index, path.relative_to(root).as_posix()) for index, root in enumerate(self.sources) for path in [root, *root.rglob("*")]}
        if observed != {(entry.root_index, entry.relative) for entry in record.entries}:
            raise GuardError("source membership changed after freeze")
        for entry in record.entries:
            path = checked_path(self.sources[entry.root_index], entry.relative)
            info = path.stat()
            if (info.st_dev, info.st_ino) != (entry.device, entry.inode):
                raise GuardError("source inode changed after freeze")
            if record.profile == "darwin-immutable":
                if (info.st_flags & stat.UF_IMMUTABLE) == 0 or stat.S_IMODE(info.st_mode) != entry.mode & ~0o222:
                    raise GuardError("persistent immutable protection missing")
            elif not os.statvfs(path).f_flag & os.ST_RDONLY:
                raise GuardError("persistent read-only mount protection missing")
            if entry.sha256 is not None and file_sha256(path) != entry.sha256:
                raise GuardError("source generation changed after freeze")
        for descriptor, path in zip(self.descriptors[1:], self.locks, strict=True):
            held, current = os.fstat(descriptor), path.stat()
            if (held.st_dev, held.st_ino) != (current.st_dev, current.st_ino):
                raise GuardError("held old lock inode was replaced")

    def verify(self) -> SealRecord:
        if len(self.descriptors) != len(self.locks) + 1:
            raise GuardError("Supervisor does not hold all original lock inodes")
        if (self.guard_root / "thaw-allowed.json").exists():
            raise GuardError("guard epoch has a thaw receipt; new execution is prohibited")
        record = self._record("sealed.json")
        self._verify(record)
        return record

    def thaw(self, *, dependencies_released: Callable[[str], bool], receipt: dict[str, JsonValue] | None = None) -> None:
        record = self._record("sealed.json") if (self.guard_root / "thaw-allowed.json").exists() else self.verify()
        if not dependencies_released(self.root_group_id):
            raise GuardError("cross-batch dependencies still require protection")
        if record.profile != "darwin-immutable":
            raise GuardError("mount restoration requires its separately verified operator profile")
        if receipt is not None and (receipt.get('group_id') != self.root_group_id or receipt.get('category') not in {'R0', 'R1'}
                or receipt.get('permission_profile') != record.profile):
            raise GuardError('committed thaw receipt identity or permission profile mismatch')
        immutable_bytes(checked_path(self.guard_root, "thaw-allowed.json"), canonical(receipt or {"version": 1, "root_group_id": self.root_group_id}).encode())
        for entry in sorted(record.entries, key=lambda entry: len(Path(entry.relative).parts)):
            path = self.sources[entry.root_index] / entry.relative
            info = path.stat()
            if (info.st_dev, info.st_ino) != (entry.device, entry.inode):
                raise GuardError("source inode changed while restoring protection permissions")
            os.chflags(path, entry.flags)
            path.chmod(entry.mode)
        observed = self._inventory()
        if observed != record.entries:
            raise GuardError('restored source membership, bytes or permissions differ from the original journal')
        immutable_bytes(checked_path(self.guard_root, "thawed.json"), canonical({"version": 1, "root_group_id": self.root_group_id,
            'seal_sha256': file_sha256(self.guard_root / 'sealed.json'), 'restored_entries': len(observed)}).encode())
