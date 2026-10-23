from __future__ import annotations

import hashlib
import os
import shutil
from pathlib import Path
from uuid import uuid4


class FileIntegrityError(ValueError):
    pass


def checked_path(root: Path, relative: str) -> Path:
    name = Path(relative)
    if not relative or name.is_absolute() or ".." in name.parts:
        raise FileIntegrityError("invalid relative artifact path")
    root = root.absolute()
    if any(part.is_symlink() for part in (root, *root.parents)):
        raise FileIntegrityError("artifact root contains a symlink")
    path = root / name
    if any(part.is_symlink() for part in (path, *path.parents) if part.is_relative_to(root)):
        raise FileIntegrityError("artifact path contains a symlink")
    return path


def file_sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def sync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def make_parents(path: Path) -> None:
    missing = []
    parent = path.parent
    while not parent.exists():
        missing.append(parent)
        parent = parent.parent
    for directory in reversed(missing):
        directory.mkdir(mode=0o700, exist_ok=True)
        sync_directory(directory.parent)


def immutable_bytes(path: Path, content: bytes) -> None:
    make_parents(path)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.link(temporary, path, follow_symlinks=False)
        except FileExistsError:
            if path.is_symlink() or path.read_bytes() != content:
                raise FileIntegrityError("immutable artifact already exists with different content")
        sync_directory(path.parent)
    finally:
        temporary.unlink(missing_ok=True)


def publish_file(source: Path, target: Path, sha256: str, size: int) -> None:
    make_parents(target)
    if not target.exists():
        temporary = target.with_name(f".{target.name}.{uuid4().hex}.tmp")
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        try:
            with os.fdopen(descriptor, "wb") as destination, source.open("rb") as original:
                shutil.copyfileobj(original, destination)
                destination.flush()
                os.fsync(destination.fileno())
            if temporary.stat().st_size != size or file_sha256(temporary) != sha256:
                raise FileIntegrityError("staged artifact changed during publication")
            try:
                os.link(temporary, target, follow_symlinks=False)
            except FileExistsError:
                if target.is_symlink():
                    raise FileIntegrityError("published target is a symlink")
        finally:
            temporary.unlink(missing_ok=True)
    if target.is_symlink() or target.stat().st_size != size or file_sha256(target) != sha256:
        raise FileIntegrityError("published artifact does not match its immutable receipt")
    sync_directory(target.parent)
