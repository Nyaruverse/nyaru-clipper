from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

from recovery_storage import JsonValue, RecoveryError, checked, inventory, object_value, sha, string


def verify(manifest: Path) -> tuple[dict[str, JsonValue], dict[str, Path], Path]:
    root = manifest.absolute().parent
    value = object_value(json.loads(checked(root, manifest.name).read_bytes()))
    if value.get('version') != 1 or value.get('schema') != '20261022_01' or value.get('execution_disabled_by_seal') is not True:
        raise RecoveryError('unsupported or incomplete recovery epoch')
    roles = {}
    for role, raw in object_value(value.get('roots')).items():
        member = object_value(raw)
        copied = checked(root, string(member.get('snapshot')))
        if inventory(copied) != object_value(member.get('files')):
            raise RecoveryError('recovery root hash or membership mismatch')
        roles[role] = copied
    required = {'unified_db', 'task_root', 'settings_root', 'global_package_root', 'migration_registry', 'guard_root'}
    if not required.issubset(roles):
        raise RecoveryError('incomplete recovery roots')
    record = object_value(value.get('database'))
    database = checked(root, string(record.get('path')))
    if sha(database) != record.get('sha256'):
        raise RecoveryError('normalized database hash mismatch')
    if 'source_protection' in value:
        protection = object_value(value['source_protection'])
        if sha(checked(root, string(protection.get('path')))) != protection.get('sha256'):
            raise RecoveryError('original protection journal hash mismatch')
    return value, roles, database


def formats(bundle_manifest: Path):
    root = bundle_manifest.absolute().parent
    bundle = object_value(json.loads(bundle_manifest.read_bytes()))
    if bundle.get('version') != 1 or bundle.get('schema') != ['20261022_01']:
        raise RecoveryError('unsupported frozen reader bundle')
    for relative, expected in object_value(bundle.get('files')).items():
        if sha(checked(root, relative)) != expected:
            raise RecoveryError('frozen reader dependency hash mismatch')
    sys.path.insert(0, str(checked(root, 'dependencies')))
    spec = importlib.util.spec_from_file_location('frozen_recovery_formats', checked(root, 'formats.py'))
    if spec is None or spec.loader is None:
        raise RecoveryError('frozen format reader missing')
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module
