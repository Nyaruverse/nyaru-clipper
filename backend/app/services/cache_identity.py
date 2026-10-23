from __future__ import annotations

import hashlib
from pathlib import Path


def content_sha256(path: Path) -> str:
    """Hash bytes, including local model trees, without trusting size or mtime."""
    digest = hashlib.sha256()
    if path.is_dir():
        for child in sorted(candidate for candidate in path.rglob("*") if candidate.is_file()):
            digest.update(str(child.relative_to(path)).encode())
            digest.update(b"\0")
            digest.update(content_sha256(child).encode())
    else:
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
    return digest.hexdigest()
