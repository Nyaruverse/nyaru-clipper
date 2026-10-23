from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Literal, assert_never

sys.path.insert(0, str(Path(__file__).resolve().parent))
from recovery_manifest import formats, verify
from recovery_publications import checksum, publication
from recovery_launcher import legacy_browser
from recovery_storage import JsonValue, RecoveryError, checked, copy_file, independent, inventory, json_write, object_value, sha, snapshot, string, write

sys.dont_write_bytecode = True


def timestamp(seconds: JsonValue) -> str:
    if type(seconds) not in {int, float}:
        raise RecoveryError('invalid cue time')
    ticks = int((Decimal(str(seconds)) * 1000).quantize(Decimal('1'), rounding=ROUND_HALF_UP))
    hours, rest = divmod(ticks, 3600000)
    minutes, rest = divmod(rest, 60000)
    whole, millis = divmod(rest, 1000)
    return f'{hours:02}:{minutes:02}:{whole:02},{millis:03}'


def srt(document: dict[str, JsonValue]) -> str:
    cues = document.get('cues')
    if not isinstance(cues, list):
        raise RecoveryError('invalid document cues')
    result = []
    for index, raw in enumerate(cues, 1):
        cue = object_value(raw)
        original = string(cue.get('text')) if cue.get('text') else ''
        translated = string(cue.get('translation')) if cue.get('translation') else ''
        result.append(f"{index}\n{timestamp(cue.get('start_seconds'))} --> {timestamp(cue.get('end_seconds'))}\n"
            + original + ('\n' + translated if translated else '') + '\n')
    return '\n'.join(result)


def context_files(context: dict[str, JsonValue], value: dict[str, JsonValue], roles: dict[str, Path], output: Path) -> None:
    reference_roots = {string(object_value(record).get('source')): roles[role]
        for role, record in object_value(value['roots']).items()}
    if string(context.get('root')) not in reference_roots:
        raise RecoveryError('task context references an unsnapshotted root')
    files = [context.get('video'), context.get('transcript'), context.get('subtitles')]
    if context.get('translation') is not None:
        files.append(context['translation'])
    clips, supporting = context.get('clips', []), context.get('supporting', [])
    if not isinstance(clips, list) or not isinstance(supporting, list):
        raise RecoveryError('invalid context members')
    files.extend(object_value(clip).get('video') for clip in clips)
    files.extend(supporting)
    for index, raw in enumerate(files):
        member = object_value(raw)
        storage = member.get('storage', 'task')
        if storage not in {'task', 'media'}:
            raise RecoveryError('unknown reference storage')
        root_key = string(context.get('root') if storage == 'task' else context.get('media_root'))
        if root_key not in reference_roots:
            raise RecoveryError('referenced medium absent from recovery epoch')
        relative = string(member.get('path'))
        source = checked(reference_roots[root_key], relative)
        if sha(source) != member.get('sha256'):
            raise RecoveryError('registered context file hash mismatch')
        copy_file(source, output / f'{index:04d}{source.suffix}')


def read_only(manifest: Path, output: Path, bundle_manifest: Path) -> Path:
    value, roles, database = verify(manifest)
    pinned_reader = object_value(value.get('reader_bundle'))
    if str(bundle_manifest.absolute()) != pinned_reader.get('path') or sha(bundle_manifest) != pinned_reader.get('sha256'):
        raise RecoveryError('reader bundle does not match this recovery epoch')
    originals = [Path(string(object_value(member).get('source'))) for member in object_value(value['roots']).values()]
    output = output.absolute()
    independent([*sorted(set(originals)), manifest.absolute().parent, output, bundle_manifest.absolute().parent])
    renderer = formats(bundle_manifest)
    output.mkdir(parents=True, exist_ok=False, mode=0o700)
    registered, errors, task_index, publications = set(), [], [], []
    with sqlite3.connect(database.as_uri() + '?mode=ro&immutable=1', uri=True) as connection:
        connection.row_factory = sqlite3.Row
        if connection.execute('SELECT version_num FROM alembic_version').fetchone()[0] != '20261022_01':
            raise RecoveryError('reader schema mismatch')
        for row in connection.execute('SELECT * FROM documenthead ORDER BY task_id'):
            identifier = row['task_id']
            try:
                if re.fullmatch('[0-9a-f]{32}', identifier) is None:
                    raise RecoveryError('invalid task identity')
                path = checked(roles['task_root'], row['body_path'])
                registered.add(row['body_path'])
                if sha(path) != row['body_sha256']:
                    raise RecoveryError('registered document hash mismatch')
                document = renderer.SubtitleDocument.model_validate_json(path.read_bytes())
                if document.revision != row['revision']:
                    raise RecoveryError('registered document revision mismatch')
                write(output / 'tasks' / identifier / 'document.json', path.read_bytes())
                write(output / 'tasks' / identifier / 'subtitles.srt', srt(json.loads(path.read_bytes())).encode())
                write(output / 'tasks' / identifier / 'subtitles.ass', renderer.render_document_ass(document, True).encode())
                task_index.append({'task_id': identifier, 'revision': row['revision'], 'sha256': row['body_sha256']})
            except (ValueError, OSError, KeyError, TypeError):
                errors.append({'kind': 'document', 'id': identifier})
        for row in connection.execute('SELECT task_id,revision,body_path,body_sha256 FROM documentversion'):
            registered.add(row['body_path'])
            try:
                path = checked(roles['task_root'], row['body_path'])
                if sha(path) != row['body_sha256'] or renderer.SubtitleDocument.model_validate_json(path.read_bytes()).revision != row['revision']:
                    raise RecoveryError('historical document body mismatch')
            except (ValueError, OSError, KeyError, TypeError):
                errors.append({'kind': 'document-version', 'id': row['task_id'], 'revision': row['revision']})
        for row in connection.execute("SELECT task_id,context_json FROM taskbinding WHERE state='activated' AND context_json!='{}'"):
            try:
                if re.fullmatch('[0-9a-f]{32}', row['task_id']) is None:
                    raise RecoveryError('invalid context task identity')
                context_files(object_value(json.loads(row['context_json'])), value, roles, output / 'contexts' / row['task_id'])
            except (ValueError, OSError, KeyError, TypeError):
                errors.append({'kind': 'context', 'id': row['task_id']})
        for row in connection.execute('SELECT * FROM globalhead WHERE deleted=0 ORDER BY key'):
            try:
                path = checked(roles['settings_root'], row['body_path'])
                if sha(path) != row['body_sha256']:
                    raise RecoveryError('registered global document hash mismatch')
                write(checked(output / 'settings', row['key']), path.read_bytes())
            except (ValueError, OSError):
                errors.append({'kind': 'settings', 'id': checksum(row['key'])})
        global_history = [dict(row) for row in connection.execute('SELECT * FROM globalversion ORDER BY key,revision')]
        for row in global_history:
            try:
                path = checked(roles['settings_root'], row['body_path'])
                if sha(path) != row['body_sha256']:
                    raise RecoveryError('historical global document hash mismatch')
                copy_file(path, checked(output / 'settings-history', row['body_path']))
            except (ValueError, OSError):
                errors.append({'kind': 'settings-version', 'id': checksum(row['key']), 'revision': row['revision']})
        for row in connection.execute("SELECT * FROM unifiedpublication WHERE state='committed' ORDER BY id"):
            try:
                receipt = publication(connection, roles['task_root'], row)
                for raw in receipt['outputs']:
                    member = object_value(raw)
                    relative = string(member['target'])
                    registered.add(relative)
                    if member['role'] == 'response':
                        continue
                    copy_file(checked(roles['task_root'], relative), checked(output / 'registered', relative))
                step = connection.execute('SELECT step_key FROM operationstep WHERE id=?', (row['step_id'],)).fetchone()
                task = connection.execute('SELECT task_id FROM unifiedoperation WHERE id=?', (row['operation_id'],)).fetchone()
                publications.append({'id': row['id'], 'task_id': task[0], 'operation_id': row['operation_id'],
                    'step_key': step[0], 'outputs': [member for member in receipt['outputs'] if member['role'] != 'response']})
            except (ValueError, OSError, KeyError, TypeError):
                errors.append({'kind': 'publication', 'id': row['id']})
        registrations = [dict(row) for row in connection.execute('SELECT task_id, source_instance_id, legacy_id, source_generation, origin, state, root_group_id FROM taskbinding ORDER BY task_id')]
        operations = [dict(row) for row in connection.execute('SELECT id,task_id,kind,state,attempt,failure_code FROM unifiedoperation ORDER BY created_at')]
        metadata = [dict(row) for row in connection.execute('SELECT t.* FROM task t JOIN taskbinding b ON t.id=b.task_id ORDER BY t.id')]
        tags = [dict(row) for row in connection.execute('SELECT * FROM tasktaglink ORDER BY task_id,tag_name')]
        migrations = {table: [dict(row) for row in connection.execute('SELECT * FROM ' + table)]
            for table in ('migrationgroup', 'migrationsource', 'migrationbatch', 'migrationmember', 'migrationdependency')}
    for operation in operations:
        if operation['state'] == 'running':
            operation['state'] = 'interrupted'
    orphans = [relative for relative in inventory(roles['task_root'])
        if '/.unified/documents/' in relative and relative not in registered]
    json_write(output / 'task-index.json', task_index)
    json_write(output / 'source-registrations.json', registrations)
    json_write(output / 'operations.json', operations)
    json_write(output / 'publication-index.json', publications)
    json_write(output / 'task-metadata.json', {'tasks': metadata, 'tags': tags})
    json_write(output / 'migration-registry.json', migrations)
    json_write(output / 'global-package-index.json', inventory(roles['global_package_root']))
    json_write(output / 'global-history.json', global_history)
    json_write(output / 'isolated-bodies.json', {'paths': orphans, 'adopted': False})
    report = {'version': 1, 'recovery_epoch': value['recovery_epoch'], 'complete': not errors,
        'documents': len(task_index), 'errors': errors, 'files': inventory(output)}
    json_write(output / 'verification.json', report)
    if errors:
        raise RecoveryError('some registered recovery items failed; partial exports and source bytes retained')
    return output / 'verification.json'


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--mode', choices=('snapshot', 'read-only', 'legacy-browser', 'thaw'), required=True)
    parser.add_argument('--output-root', type=Path, required=True)
    parser.add_argument('--bundle', type=Path)
    parser.add_argument('--install-seal', action='store_true')
    options = parser.parse_args()
    try:
        mode: Literal['snapshot', 'read-only', 'legacy-browser', 'thaw'] = options.mode
        match mode:
            case 'snapshot':
                result = snapshot(object_value(json.loads(options.manifest.read_bytes())), options.output_root, install_seal=options.install_seal)
            case 'read-only':
                if options.bundle is None:
                    raise RecoveryError('a pinned independent reader bundle is required')
                result = read_only(options.manifest, options.output_root, options.bundle)
            case 'legacy-browser':
                return legacy_browser(options.manifest, options.output_root)
            case 'thaw':
                from recovery_thaw import thaw
                if options.bundle is None:
                    raise RecoveryError('a pinned independent thaw bundle is required')
                result = thaw(object_value(json.loads(options.manifest.read_bytes())), options.output_root, options.bundle)
            case unreachable:
                assert_never(unreachable)
        print(json.dumps({'receipt': str(result)}))
        return 0
    except KeyboardInterrupt:
        return 130
    except RecoveryError as error:
        print(f'Recovery blocked: {error}. Originals and partial evidence retained.', file=sys.stderr)
        return 2
    except (OSError, sqlite3.DatabaseError, KeyError, TypeError):
        print('Recovery blocked; originals and partial evidence retained.', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
