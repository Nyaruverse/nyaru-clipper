from __future__ import annotations

import json
import os
import stat
import sys
from pathlib import Path

from recovery_storage import JsonValue, RecoveryError, checked, json_write, object_value, string


def seal(roots: list[Path], record: Path, *, install: bool, resume: Path | None = None) -> None:
    paths = {str(path): path for root in roots for path in [root, *sorted(root.rglob('*'))]}
    for root in roots:
        for path in [root, *root.rglob('*')]:
            checked(root, path.relative_to(root).as_posix())
            if not (path.is_dir() or path.is_file()) or (path.is_file() and path.stat().st_nlink != 1):
                raise RecoveryError('unsupported protection profile')
    entries: list[dict[str, JsonValue]] = []
    if resume is not None:
        value = object_value(json.loads(resume.read_bytes()))
        if value.get('version') != 1 or not isinstance(value.get('entries'), list):
            raise RecoveryError('unsupported original protection journal')
        entries = [object_value(item) for item in value['entries']]
        if {string(entry.get('path')) for entry in entries} != set(paths) or len(entries) != len(paths):
            raise RecoveryError('protection journal membership differs')
    else:
        for name, path in paths.items():
            info = path.stat()
            if install and sys.platform == 'darwin' and info.st_flags & stat.UF_IMMUTABLE:
                raise RecoveryError('existing protection requires its original pinned journal')
            entries.append({'path': name, 'mode': stat.S_IMODE(info.st_mode), 'flags': getattr(info, 'st_flags', 0),
                'device': info.st_dev, 'inode': info.st_ino})
    for entry in entries:
        info = paths[string(entry['path'])].stat()
        if (info.st_dev, info.st_ino) != (entry.get('device'), entry.get('inode')):
            raise RecoveryError('protection journal inode differs')
        if any(type(entry.get(key)) is not int for key in ('mode', 'flags', 'device', 'inode')):
            raise RecoveryError('invalid original protection attributes')
    if install:
        if sys.platform != 'darwin':
            raise RecoveryError('seal installation requires a separately qualified platform profile')
        json_write(record, {'version': 1, 'entries': entries})
        for entry in sorted(entries, key=lambda item: len(Path(string(item['path'])).parts), reverse=True):
            path = paths[string(entry['path'])]
            if not path.stat().st_flags & stat.UF_IMMUTABLE:
                path.chmod(int(entry['mode']) & ~0o222)
                os.chflags(path, int(entry['flags']) | stat.UF_IMMUTABLE)
    for entry in entries:
        path = paths[string(entry['path'])]
        info = path.stat()
        if sys.platform == 'darwin':
            if not info.st_flags & stat.UF_IMMUTABLE or stat.S_IMODE(info.st_mode) != int(entry['mode']) & ~0o222:
                raise RecoveryError('persistent protection missing or changed')
        elif not os.statvfs(path).f_flag & os.ST_RDONLY:
            raise RecoveryError('persistent read-only mount missing')
