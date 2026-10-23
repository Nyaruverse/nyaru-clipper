from __future__ import annotations

import fcntl
import hashlib
import json
import os
import shutil
import sqlite3
import stat
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import TypeAlias
from uuid import UUID, uuid4


class RecoveryError(ValueError):
    pass


JsonValue: TypeAlias = str | int | float | bool | None | list['JsonValue'] | dict[str, 'JsonValue']


def object_value(value: JsonValue) -> dict[str, JsonValue]:
    if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
        raise RecoveryError('expected a JSON object')
    return {key: member for key, member in value.items()}


def string(value: JsonValue) -> str:
    if not isinstance(value, str) or not value:
        raise RecoveryError('expected a nonempty string')
    return value


def checked(root: Path, relative: str) -> Path:
    part = Path(relative)
    if part.is_absolute() or '..' in part.parts or '\\' in relative:
        raise RecoveryError('unsafe relative path')
    path = root / part
    if any(item.is_symlink() for item in (path, *path.parents)):
        raise RecoveryError('symlink in recovery path')
    return path


def sha(path: Path) -> str:
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def write(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with path.open('xb') as stream:
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())
    descriptor = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def json_write(path: Path, value: JsonValue) -> None:
    write(path, json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode())


def copy_file(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with source.open('rb') as incoming, target.open('xb') as outgoing:
        shutil.copyfileobj(incoming, outgoing, length=8 * 1024 * 1024)
        outgoing.flush()
        os.fsync(outgoing.fileno())
    descriptor = os.open(target.parent, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def inventory(root: Path) -> dict[str, str]:
    checked(root, '.probe')
    if not root.is_dir():
        raise RecoveryError('required recovery root missing')
    result = {}
    for path in sorted(root.rglob('*')):
        checked(root, path.relative_to(root).as_posix())
        if path.is_dir():
            continue
        if not path.is_file() or path.stat().st_nlink != 1:
            raise RecoveryError('unsupported recovery file or hard link')
        result[path.relative_to(root).as_posix()] = sha(path)
    return result


def independent(paths: list[Path]) -> None:
    for index, path in enumerate(paths):
        checked(path, '.probe')
        if any(path.is_relative_to(other) or other.is_relative_to(path) for other in paths[index + 1:]):
            raise RecoveryError('recovery domains overlap')


@contextmanager
def barrier(locks: list[Path]) -> Iterator[None]:
    if not locks or len(set(locks)) != len(locks):
        raise RecoveryError('unique existing writer locks are required')
    descriptors = []
    try:
        for path in sorted(locks):
            checked(path.parent, path.name)
            descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
            descriptors.append(descriptor)
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield
        for path, descriptor in zip(sorted(locks), descriptors, strict=True):
            if (path.stat().st_dev, path.stat().st_ino) != (os.fstat(descriptor).st_dev, os.fstat(descriptor).st_ino):
                raise RecoveryError('writer lock inode changed')
    finally:
        for descriptor in reversed(descriptors):
            os.close(descriptor)


def snapshot(recipe: dict[str, JsonValue], output: Path, *, install_seal: bool = False) -> Path:
    from recovery_protection import seal
    if recipe.get('version') != 1:
        raise RecoveryError('unsupported recovery recipe')
    group = str(UUID(string(recipe.get('root_group_id'))))
    roles = {name: Path(string(value)).absolute() for name, value in object_value(recipe.get('roots')).items()}
    required = {'unified_db', 'task_root', 'settings_root', 'global_package_root', 'migration_registry', 'guard_root'}
    if not required.issubset(roles):
        raise RecoveryError('incomplete recovery root roles')
    roots = sorted(set(roles.values()))
    credentials = Path(string(recipe.get('credential_root'))).absolute()
    output = output.absolute()
    independent([*roots, credentials, output])
    locks_value = recipe.get('locks')
    if not isinstance(locks_value, list):
        raise RecoveryError('missing writer locks')
    locks = [Path(string(value)).absolute() for value in locks_value]
    if not all(any(path.is_relative_to(root) for root in roots) for path in locks):
        raise RecoveryError('writer lock outside recovery set')
    database = checked(roles['unified_db'], string(recipe.get('database')))
    reader = object_value(recipe.get('reader_bundle'))
    reader_manifest = Path(string(reader.get('path'))).absolute()
    if sha(reader_manifest) != reader.get('sha256'):
        raise RecoveryError('frozen reader manifest mismatch')
    reader_contract = object_value(json.loads(reader_manifest.read_bytes()))
    if reader_contract.get('version') != 1 or reader_contract.get('schema') != ['20261022_01']:
        raise RecoveryError('unsupported frozen reader contract')
    for relative, expected in object_value(reader_contract.get('files')).items():
        if sha(checked(reader_manifest.parent, relative)) != expected:
            raise RecoveryError('frozen reader resource mismatch')
    independent([*roots, credentials, output, reader_manifest.parent])
    output.mkdir(parents=True, exist_ok=False, mode=0o700)
    with barrier(locks):
        previous = Path(string(recipe['protection_record'])) if 'protection_record' in recipe else None
        if previous is not None and sha(previous) != recipe.get('protection_sha256'):
            raise RecoveryError('original protection journal pin differs')
        seal(roots, output / 'source-protection.json', install=install_seal, resume=previous)
        before = {str(root): inventory(root) for root in roots}
        copied = {}
        for index, root in enumerate(roots):
            relative = f'roots/{index}'
            shutil.copytree(root, output / relative, copy_function=shutil.copyfile)
            if inventory(output / relative) != before[str(root)]:
                raise RecoveryError('recovery root copy differs')
            for path in (output / relative).rglob('*'):
                if path.is_file():
                    with path.open('rb') as stream:
                        os.fsync(stream.fileno())
            copied[str(root)] = relative
        raw_database = output / copied[str(roles['unified_db'])] / database.relative_to(roles['unified_db'])
        normalized = output / 'database.sqlite3'
        with tempfile.TemporaryDirectory(prefix='.database-normalization-', dir=output) as temporary:
            working = Path(temporary) / 'database.sqlite3'
            for suffix in ('', '-wal', '-shm'):
                source_file = Path(str(raw_database) + suffix)
                if source_file.exists():
                    shutil.copyfile(source_file, Path(str(working) + suffix))
            with sqlite3.connect(working) as source, sqlite3.connect(normalized) as target:
                source.backup(target)
        with sqlite3.connect(normalized) as connection:
            version = connection.execute('SELECT version_num FROM alembic_version').fetchone()
            if version != ('20261022_01',) or connection.execute('PRAGMA integrity_check').fetchone() != ('ok',):
                raise RecoveryError('unsupported or corrupt recovery database')
            paused = connection.execute('SELECT paused FROM unifiedruntime WHERE id=1').fetchone()
            if paused is None:
                raise RecoveryError('runtime registration missing')
            registered_roots = object_value(json.loads(connection.execute('SELECT root_roles_json FROM unifiedruntime WHERE id=1').fetchone()[0]))
            expected_roots = {'task': str(roles['task_root']), 'settings': str(roles['settings_root']),
                'guard': str(roles['guard_root']), 'credential': str(credentials)}
            if registered_roots != expected_roots:
                raise RecoveryError('registered runtime protection domains differ from recovery recipe')
            for (pid,) in connection.execute("SELECT a.owner_pid FROM operationattempt a JOIN unifiedoperation o ON a.execution_token=o.execution_token WHERE o.state='running'"):
                try:
                    os.kill(pid, 0)
                except ProcessLookupError:
                    continue
                raise RecoveryError('original operation owner is still alive')
            for (pgid,) in connection.execute('SELECT process_group_id FROM operationprocess WHERE released=0'):
                try:
                    os.killpg(pgid, 0)
                except ProcessLookupError:
                    continue
                raise RecoveryError('original process group is still alive')
            if connection.execute("SELECT 1 FROM taskjob WHERE status IN ('pending','running') LIMIT 1").fetchone():
                raise RecoveryError('legacy execution eligibility remains')
            if connection.execute('SELECT 1 FROM taskexecutioncontrol WHERE active_process_group_id IS NOT NULL LIMIT 1').fetchone():
                raise RecoveryError('legacy process ownership remains')
            watermark = connection.execute('SELECT COALESCE(MAX(id),0) FROM workstationevent').fetchone()[0]
        if any(inventory(root) != before[str(root)] for root in roots):
            raise RecoveryError('source changed across recovery barrier')
        credential_info = credentials.stat()
        result = {'version': 1, 'root_group_id': group, 'recovery_epoch': uuid4().hex, 'schema': version[0],
            'watermark': watermark, 'queue_was_paused': bool(paused[0]), 'execution_disabled_by_seal': True,
            'reader_bundle': {'path': str(reader_manifest), 'sha256': sha(reader_manifest)},
            'wal_handling': 'stopped sealed DB/WAL set copied; SQLite backup on independent copy',
            'locks': [str(path) for path in locks],
            'database': {'path': 'database.sqlite3', 'sha256': sha(normalized)},
            'roots': {name: {'source': str(root), 'snapshot': copied[str(root)], 'files': before[str(root)]} for name, root in roles.items()},
            'credentials': {'reference': str(credentials), 'mode': stat.S_IMODE(credential_info.st_mode), 'copied': False}}
        if 'legacy' in recipe:
            result['legacy'] = recipe['legacy']
        protection = output / 'source-protection.json'
        if protection.is_file():
            result['source_protection'] = {'path': protection.name, 'sha256': sha(protection)}
        for directory in sorted([output, *(path for path in output.rglob('*') if path.is_dir())], reverse=True):
            descriptor = os.open(directory, os.O_RDONLY)
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
        with normalized.open('rb') as stream:
            os.fsync(stream.fileno())
        json_write(output / 'complete.json', result)
    return output / 'complete.json'
