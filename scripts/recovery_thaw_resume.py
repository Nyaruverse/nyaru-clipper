from __future__ import annotations

import json
from pathlib import Path

from recovery_storage import JsonValue, RecoveryError, checked, inventory, object_value, sha, string


def verify_resume(recipe: dict[str, JsonValue], roots: dict[str, Path], journal: Path) -> bool:
    reference = recipe.get('interrupted_thaw')
    if reference is None:
        return False
    reference = object_value(reference)
    path = Path(string(reference.get('path')))
    if sha(path) != reference.get('sha256'):
        raise RecoveryError('interrupted thaw intent pin differs')
    intent = object_value(json.loads(path.read_bytes()))
    original = {key: value for key, value in recipe.items() if key != 'interrupted_thaw'}
    if intent != {'version': 1, 'recipe': original, 'journal': str(journal), 'journal_sha256': sha(journal)}:
        raise RecoveryError('interrupted thaw intent identity differs')
    entries = object_value(json.loads(journal.read_bytes())).get('entries')
    if not isinstance(entries, list):
        raise RecoveryError('interrupted thaw inode journal missing')
    for raw in entries:
        entry = object_value(raw)
        member = Path(string(entry.get('path')))
        root = next((root for root in roots.values() if member.is_relative_to(root)), None)
        if root is None:
            raise RecoveryError('interrupted thaw journal domain differs')
        checked(root, member.relative_to(root).as_posix())
        info = member.stat()
        if (info.st_dev, info.st_ino) != (entry.get('device'), entry.get('inode')):
            raise RecoveryError('interrupted thaw original inode differs')
    return True


def verify_control_changes(recipe: dict[str, JsonValue], root: Path, original: dict[str, JsonValue]) -> None:
    database = Path(string(recipe.get('database')))
    guard = Path(string(object_value(recipe.get('guard')).get('guard_root')))
    allowed = set()
    if database.is_relative_to(root):
        allowed.update(database.relative_to(root).as_posix() + suffix for suffix in ('', '-journal', '-wal', '-shm'))
    if guard.is_relative_to(root):
        allowed.update((guard / name).relative_to(root).as_posix() for name in ('thaw-allowed.json', 'thawed.json'))
    current = inventory(root)
    if set(current) - set(original) - allowed or any(current.get(name) != digest for name, digest in original.items() if name not in allowed):
        raise RecoveryError('interrupted thaw control bytes or membership differ')
