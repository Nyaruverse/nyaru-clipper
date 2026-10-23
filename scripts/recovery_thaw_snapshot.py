from __future__ import annotations

import json
import os
import sqlite3
import stat
from pathlib import Path

from recovery_manifest import formats, verify
from recovery_protection import seal
from recovery_storage import JsonValue, RecoveryError, barrier, checked, independent, inventory, json_write, object_value, sha, string


def journal_entries(path: Path) -> list[dict[str, JsonValue]]:
    entries = object_value(json.loads(path.read_bytes())).get('entries')
    if not isinstance(entries, list):
        raise RecoveryError('original recovery permission journal missing')
    return [object_value(entry) for entry in entries]


def restore_controls(roots: list[Path], journal: Path) -> None:
    for entry in sorted(journal_entries(journal), key=lambda entry: len(Path(string(entry['path'])).parts)):
        path = Path(string(entry['path']))
        root = next((root for root in roots if path.is_relative_to(root)), None)
        if root is None:
            continue
        checked(root, path.relative_to(root).as_posix())
        info = path.stat()
        if (info.st_dev, info.st_ino) != (entry.get('device'), entry.get('inode')):
            raise RecoveryError('sealed recovery control inode changed')
        if type(entry.get('mode')) is not int or type(entry.get('flags')) is not int:
            raise RecoveryError('invalid original control permissions')
        os.chflags(path, entry['flags'])
        path.chmod(entry['mode'])


def reseal_controls(roots: list[Path], journal: Path, output: Path) -> None:
    original = {string(entry['path']): entry for entry in journal_entries(journal)}
    entries = []
    for root in roots:
        for path in [root, *root.rglob('*')]:
            info = path.stat()
            old = original.get(str(path))
            if old is not None and (info.st_dev, info.st_ino) == (old.get('device'), old.get('inode')):
                entries.append(old)
            else:
                entries.append({'path': str(path), 'mode': stat.S_IMODE(info.st_mode), 'flags': info.st_flags,
                    'device': info.st_dev, 'inode': info.st_ino})
    resumed = output / 'control-permissions.json'
    json_write(resumed, {'version': 1, 'entries': entries})
    seal(roots, output / 'controls-resealed.json', install=True, resume=resumed)


def thaw_snapshot(recipe: dict[str, JsonValue], output: Path, bundle: Path) -> Path:
    from recovery_thaw import quiescent, thaw_database
    reference = object_value(recipe['sealed_snapshot'])
    manifest = Path(string(reference.get('path')))
    if sha(manifest) != reference.get('sha256'):
        raise RecoveryError('sealed snapshot manifest pin differs')
    value, _, snapshot_db = verify(manifest)
    bundle_ref = object_value(value['reader_bundle'])
    if (bundle_ref.get('path') != str(bundle.absolute()) or bundle_ref.get('sha256') != sha(bundle)
            or recipe.get('bundle_sha256') != sha(bundle)):
        raise RecoveryError('snapshot and thaw reader bundle differ')
    formats(bundle)
    if string(object_value(value.get('credentials'))['reference']) != recipe.get('credential_root'):
        raise RecoveryError('snapshot and thaw credential references differ')
    if value.get('root_group_id') != object_value(recipe.get('guard')).get('group_id'):
        raise RecoveryError('snapshot and thaw group identities differ')
    roles = {name: Path(string(object_value(raw)['source'])) for name, raw in object_value(value['roots']).items()}
    database = Path(string(recipe.get('database')))
    if database.parent != roles['unified_db']:
        raise RecoveryError('thaw database is outside the sealed epoch')
    locks_raw = value.get('locks')
    if not isinstance(locks_raw, list):
        raise RecoveryError('sealed epoch writer locks missing')
    locks = [Path(string(item)) for item in locks_raw]
    if roles['guard_root'] / '.heavy.lock' not in locks:
        raise RecoveryError('sealed epoch lacks its heavy-work barrier')
    control = Path(string(object_value(recipe['guard'])['guard_root'])) / '.guard.lock'
    locks = [path for path in locks if path != control]
    independent([*sorted(set(roles.values())), manifest.absolute().parent, output.absolute(), bundle.absolute().parent])
    protection = object_value(recipe.get('controls_protection') or value.get('source_protection'))
    journal = Path(string(protection.get('path'))) if 'controls_protection' in recipe else checked(manifest.parent, string(protection.get('path')))
    if sha(journal) != protection.get('sha256'):
        raise RecoveryError('original new-root permission journal pin differs')
    from recovery_thaw_resume import verify_control_changes, verify_resume
    output.mkdir(parents=True, exist_ok=False, mode=0o700)
    controls = [roles['unified_db'], roles['guard_root']]
    with barrier(locks):
        resumed = verify_resume(recipe, roles, journal)
        for role, raw in object_value(value['roots']).items():
            if resumed and roles[role] in controls:
                verify_control_changes(recipe, roles[role], object_value(object_value(raw)['files']))
            elif inventory(roles[role]) != object_value(object_value(raw)['files']):
                raise RecoveryError('sealed originals changed after snapshot')
        with sqlite3.connect(snapshot_db.as_uri() + '?mode=ro&immutable=1', uri=True) as connection:
            quiescent(connection)
            group = connection.execute('SELECT state,new_writes FROM migrationgroup WHERE id=?',
                (string(object_value(recipe['guard'])['group_id']),)).fetchone()
            if group is None or group[0] not in {'open', 'withdrawing'} or group[1]:
                raise RecoveryError('R2 or closed group cannot release sealed controls')
        json_write(output / 'thaw-intent.json', {'version': 1,
            'recipe': {key: member for key, member in recipe.items() if key != 'interrupted_thaw'},
            'journal': str(journal), 'journal_sha256': sha(journal)})
        try:
            restore_controls(controls, journal)
            return thaw_database(recipe, output / 'result', bundle, already_barred=True)
        finally:
            reseal_controls(controls, journal, output)
