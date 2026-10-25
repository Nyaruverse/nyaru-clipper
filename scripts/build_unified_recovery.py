from __future__ import annotations

import argparse
import ast
import hashlib
import importlib.metadata
import json
import shutil
import sys
from pathlib import Path
from packaging.requirements import Requirement


DEFINITIONS = {
    'subtitle_style.py': {'OutlineLayer', 'TextStyle', 'SubtitleStyle', '_color', 'centiseconds', '_timestamp', '_text', 'alignment_for', 'automatic_layout'},
    'subtitle_document.py': {'Emphasis', 'Cue', 'SubtitleDocument'},
    'subtitle_render.py': {'_lines', 'render_document_ass'},
    '../services/publication_receipts.py': {'ReceiptError', 'OutputMember', 'PreparedReceipt'},
}
PACKAGES = ('pydantic', 'pydantic_core', 'annotated_types', 'typing_extensions', 'typing_inspection', 'regex')


class RecoveryBuildError(ValueError):
    pass


def freeze(output: Path, *, legacy_helper: bool = False, tools_root: Path | None = None) -> Path:
    repository = Path(__file__).resolve().parents[1]
    output.mkdir(parents=True, exist_ok=False, mode=0o700)
    header = '''from __future__ import annotations
import math, re, unicodedata
from collections.abc import Sequence
from decimal import Decimal, ROUND_HALF_UP
from typing import Literal
import regex
from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, model_validator, field_validator
'''
    definitions = []
    for filename, names in DEFINITIONS.items():
        source = repository / 'backend/app/arctime' / filename
        tree = ast.parse(source.read_text())
        selected = [node for node in tree.body if isinstance(node, (ast.ClassDef, ast.FunctionDef)) and node.name in names]
        if {node.name for node in selected} != names:
            raise RecoveryBuildError('frozen format contract changed')
        definitions.extend(ast.unparse(node) for node in selected)
    (output / 'formats.py').write_text(header + '\n\n'.join(definitions) + '\n')
    guard_sources = {
        repository / 'backend/app/services/unified_files.py': {'FileIntegrityError', 'checked_path', 'file_sha256', 'sync_directory', 'make_parents', 'immutable_bytes'},
        repository / 'backend/app/services/source_seal.py': {'GuardError', 'SealEntry', 'SealRecord', 'Supervisor'},
    }
    guard_definitions = []
    for path, names in guard_sources.items():
        tree = ast.parse(path.read_text())
        selected = [node for node in tree.body if isinstance(node, (ast.ClassDef, ast.FunctionDef)) and node.name in names]
        if {node.name for node in selected} != names:
            raise RecoveryBuildError('frozen guard contract changed')
        guard_definitions.extend(ast.unparse(node) for node in selected)
    guard_header = '\n'.join(('from __future__ import annotations', 'import fcntl, hashlib, json, os, stat, sys',
        'from collections.abc import Callable', 'from pathlib import Path', 'from typing import Literal',
        'from uuid import uuid4', 'from pydantic import BaseModel, ConfigDict, JsonValue', 'def canonical(value):',
        '    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)', ''))
    (output / 'frozen_recovery_guard.py').write_text(guard_header + '\n\n'.join(guard_definitions) + '\n')
    shutil.copyfile(repository / 'scripts/unified_recovery.py', output / 'reader.py')
    shutil.copyfile(repository / 'scripts/recovery_storage.py', output / 'recovery_storage.py')
    for module in ('recovery_manifest.py', 'recovery_launcher.py', 'recovery_protection.py', 'recovery_thaw.py', 'recovery_thaw_snapshot.py', 'recovery_thaw_resume.py', 'recovery_publications.py'):
        shutil.copyfile(repository / 'scripts' / module, output / module)
    dependencies = output / 'dependencies'
    packages = set(PACKAGES)
    if legacy_helper:
        packages.update({'fastapi', 'uvicorn', 'httpx', 'sqlmodel', 'alembic', 'pydantic-settings', 'PyJWT', 'cryptography'})
    pending = list(packages)
    while pending:
        name = pending.pop()
        for expression in importlib.metadata.requires(name) or ():
            requirement = Requirement(expression)
            if (requirement.marker is None or requirement.marker.evaluate()) and requirement.name not in packages:
                packages.add(requirement.name)
                pending.append(requirement.name)
    for name in sorted(packages):
        distribution = importlib.metadata.distribution(name)
        for item in distribution.files or ():
            if '..' in item.parts or '__pycache__' in item.parts or item.suffix == '.pyc':
                continue
            source = Path(distribution.locate_file(item))
            if source.is_file():
                target = dependencies / item
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target)
    if legacy_helper:
        shutil.copytree(repository / 'backend/app', output / 'legacy/app', ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        if not (repository / 'web/dist/index.html').is_file():
            raise RecoveryBuildError('build the actual interface before freezing the legacy helper')
        shutil.copytree(repository / 'web/dist', output / 'web')
        shutil.copyfile(repository / 'scripts/recovery_legacy_helper.py', output / 'legacy_helper.py')
        launcher = output / 'legacy-helper'
        launcher.write_text('#!/bin/sh\nset -eu\nroot=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)\n'
            'exec "$root/runtime/bin/python3.11" -I -S -B "$root/legacy_helper.py" "$@"\n')
        launcher.chmod(0o700)
        if tools_root is not None:
            for name in ('ffmpeg', 'ffprobe'):
                if not (tools_root / name).is_file():
                    raise RecoveryBuildError('independent recovery tools missing')
            tools = output / 'tools'
            tools.mkdir(mode=0o700)
            for source in tools_root.iterdir():
                if source.is_file() and (source.name in {'ffmpeg', 'ffprobe'} or source.suffix == '.dylib' or '.so' in source.suffixes):
                    shutil.copyfile(source, tools / source.name)
                    (tools / source.name).chmod(0o700 if source.name in {'ffmpeg', 'ffprobe'} else 0o600)
    runtime = Path(sys.base_prefix).resolve()
    if not (runtime / 'bin/python3.11').is_file():
        raise RecoveryBuildError('freeze requires an independent CPython 3.11 runtime')
    shutil.copytree(runtime, output / 'runtime', symlinks=False, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    files = {path.relative_to(output).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(output.rglob('*')) if path.is_file()}
    manifest = {'version': 1, 'schema': ['20261022_01'], 'runtime': 'runtime/bin/python3.11',
        'reader': 'reader.py', 'files': files, 'packages': {name: importlib.metadata.version(name) for name in sorted(packages)}}
    if legacy_helper:
        manifest['legacy_helper'] = {'path': 'legacy-helper', 'sha256': files['legacy-helper'], 'offline_abi': 'nyaru-local-recovery-v1'}
    (output / 'bundle.json').write_text(json.dumps(manifest, sort_keys=True, ensure_ascii=False, indent=2))
    return output / 'bundle.json'


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--legacy-helper', action='store_true')
    parser.add_argument('--tools-root', type=Path)
    options = parser.parse_args()
    print(freeze(options.output, legacy_helper=options.legacy_helper, tools_root=options.tools_root))


if __name__ == '__main__':
    main()
