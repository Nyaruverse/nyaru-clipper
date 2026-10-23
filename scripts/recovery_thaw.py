from __future__ import annotations

import json
import sqlite3
from contextlib import nullcontext
from pathlib import Path

from recovery_manifest import formats
from recovery_storage import JsonValue, RecoveryError, barrier, checked, independent, json_write, object_value, sha, string


def canonical(value: JsonValue) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def quiescent(connection: sqlite3.Connection) -> None:
    if connection.execute('SELECT paused,recovering FROM unifiedruntime WHERE id=1').fetchone() != (1, 0):
        raise RecoveryError('queue must be paused and recovery complete')
    queries = ("SELECT 1 FROM unifiedoperation WHERE state='running'",
        'SELECT 1 FROM operationprocess WHERE released=0',
        "SELECT 1 FROM taskjob WHERE status IN ('pending','running')",
        'SELECT 1 FROM taskexecutioncontrol WHERE active_process_group_id IS NOT NULL',
        "SELECT 1 FROM unifiedpublication WHERE state='ready'")
    if any(connection.execute(query + ' LIMIT 1').fetchone() for query in queries):
        raise RecoveryError('execution or publication ownership is not released')


def withdraw(connection: sqlite3.Connection, group_id: str, profile: str, seal_sha: str) -> dict[str, JsonValue]:
    quiescent(connection)
    group = connection.execute('SELECT state,ever_activated,new_writes,thaw_receipt_json FROM migrationgroup WHERE id=?', (group_id,)).fetchone()
    if group is None or group[0] not in {'open', 'withdrawing', 'thawed'} or group[2]:
        raise RecoveryError('R2, closed or unknown migration group cannot thaw originals')
    if group[3] is not None:
        receipt = object_value(json.loads(group[3]))
        if receipt.get('seal_sha256') != seal_sha or receipt.get('permission_profile') != profile:
            raise RecoveryError('committed permission receipt differs')
        if not committed(connection, group_id, receipt):
            raise RecoveryError('committed withdrawal references differ')
        return receipt
    if group[0] == 'thawed':
        raise RecoveryError('thawed group lacks committed permission receipt')
    batches = [row[0] for row in connection.execute('SELECT id FROM migrationbatch WHERE group_id=? ORDER BY id', (group_id,))]
    members = [{'task_id': row[0], 'generation': row[1]} for row in connection.execute(
        'SELECT m.task_id,m.generation FROM migrationmember m JOIN migrationbatch b ON m.batch_id=b.id WHERE b.group_id=? ORDER BY m.id', (group_id,))]
    bindings = {row[0] for row in connection.execute('SELECT task_id FROM taskbinding WHERE root_group_id=?', (group_id,))}
    if bindings - {member['task_id'] for member in members}:
        raise RecoveryError('unregistered outside dependency prevents thaw')
    edges = list(connection.execute('SELECT id,kind FROM migrationdependency WHERE group_id=? ORDER BY id', (group_id,)))
    if any(row[1] != 'source-and-global-package' for row in edges):
        raise RecoveryError('unknown external migration dependency')
    sources = [{'id': row[0], 'roots': json.loads(row[1])} for row in connection.execute(
        'SELECT id,roots_json FROM migrationsource WHERE group_id=? ORDER BY id', (group_id,))]
    receipt = {'version': 1, 'group_id': group_id, 'category': 'R1' if group[1] else 'R0', 'batches': batches,
        'members': members, 'sources': sources, 'withdrawn_references': [row[0] for row in edges],
        'permission_profile': profile, 'seal_sha256': seal_sha}
    connection.execute("UPDATE taskbinding SET state='withdrawn' WHERE root_group_id=?", (group_id,))
    connection.execute("UPDATE migrationmember SET state='withdrawn' WHERE batch_id IN (SELECT id FROM migrationbatch WHERE group_id=?)", (group_id,))
    connection.execute("UPDATE migrationbatch SET state='withdrawn' WHERE group_id=?", (group_id,))
    connection.execute('UPDATE migrationdependency SET active=0 WHERE group_id=?', (group_id,))
    connection.execute("UPDATE migrationgroup SET state='withdrawing',thaw_receipt_json=? WHERE id=?", (canonical(receipt), group_id))
    return receipt


def committed(connection: sqlite3.Connection, identifier: str, receipt: dict[str, JsonValue]) -> bool:
    quiescent(connection)
    group = connection.execute('SELECT state,new_writes,thaw_receipt_json FROM migrationgroup WHERE id=?', (identifier,)).fetchone()
    edges = connection.execute('SELECT 1 FROM migrationdependency WHERE group_id=? AND active=1 LIMIT 1', (identifier,)).fetchone()
    bindings = connection.execute("SELECT 1 FROM taskbinding WHERE root_group_id=? AND state='activated' LIMIT 1", (identifier,)).fetchone()
    batches = connection.execute('SELECT id,state FROM migrationbatch WHERE group_id=? ORDER BY id', (identifier,)).fetchall()
    members = connection.execute('SELECT m.task_id,m.generation,m.state FROM migrationmember m JOIN migrationbatch b ON m.batch_id=b.id WHERE b.group_id=? ORDER BY m.id', (identifier,)).fetchall()
    references = connection.execute('SELECT id FROM migrationdependency WHERE group_id=? ORDER BY id', (identifier,)).fetchall()
    binding_rows = connection.execute('SELECT task_id,state FROM taskbinding WHERE root_group_id=?', (identifier,)).fetchall()
    registered = {row[0] for row in members}
    complete = (all(row[1] == 'withdrawn' for row in batches)
        and all(row[2] == 'withdrawn' for row in members)
        and all(row[0] in registered and row[1] == 'withdrawn' for row in binding_rows)
        and [row[0] for row in batches] == receipt.get('batches')
        and [{'task_id': row[0], 'generation': row[1]} for row in members] == receipt.get('members')
        and [row[0] for row in references] == receipt.get('withdrawn_references')
        and receipt.get('group_id') == identifier)
    return bool(complete and group is not None and group[0] in {'withdrawing', 'thawed'}
        and group[1:] == (0, canonical(receipt)) and not edges and not bindings)


def thaw(recipe: dict[str, JsonValue], output: Path, bundle: Path) -> Path:
    try:
        if 'sealed_snapshot' in recipe:
            from recovery_thaw_snapshot import thaw_snapshot
            return thaw_snapshot(recipe, output, bundle)
        return thaw_database(recipe, output, bundle)
    except ValueError as error:
        raise RecoveryError(str(error)) from error


def thaw_database(recipe: dict[str, JsonValue], output: Path, bundle: Path, *, already_barred: bool = False) -> Path:
    if recipe.get('version') != 1 or sha(bundle) != recipe.get('bundle_sha256'):
        raise RecoveryError('independent thaw recipe or bundle pin mismatch')
    formats(bundle)
    from frozen_recovery_guard import Supervisor
    guard = object_value(recipe.get('guard'))
    group_id = string(guard.get('group_id'))
    domains, locks = guard.get('domains'), guard.get('locks')
    if not isinstance(domains, list) or not isinstance(locks, list):
        raise RecoveryError('explicit old protection domains and locks required')
    sources = tuple(Path(string(item)) for item in domains)
    guard_root = Path(string(guard.get('guard_root')))
    credentials = Path(string(recipe.get('credential_root')))
    database = Path(string(recipe.get('database')))
    independent([*sources, guard_root, credentials, database.parent, output.absolute(), bundle.absolute().parent])
    if output.exists():
        raise RecoveryError('thaw receipt output already exists; use a new directory')
    if not database.is_file():
        raise RecoveryError('registered database is missing; automatic creation prohibited')
    with sqlite3.connect(database.as_uri() + '?mode=rw', uri=True, isolation_level=None) as connection:
        if connection.execute('SELECT version_num FROM alembic_version').fetchall() != [('20261022_01',)]:
            raise RecoveryError('unsupported thaw schema')
        if connection.execute('PRAGMA integrity_check').fetchone() != ('ok',):
            raise RecoveryError('corrupt migration database')
        roles = object_value(json.loads(connection.execute('SELECT root_roles_json FROM unifiedruntime WHERE id=1').fetchone()[0]))
        host_guard = Path(string(roles.get('guard')))
        if not guard_root.is_relative_to(host_guard) or str(credentials) != roles.get('credential'):
            raise RecoveryError('thaw guard or credential reference differs from runtime registration')
        checked(host_guard, '.heavy.lock')
        with (nullcontext() if already_barred else barrier([host_guard / '.heavy.lock'])), Supervisor(sources, guard_root, credentials, group_id,
                tuple(Path(string(item)) for item in locks)) as supervisor:
            sealed = guard_root / 'sealed.json'
            record = supervisor._record('sealed.json')
            ownership_row = connection.execute('SELECT ownership_json FROM migrationgroup WHERE id=?', (group_id,)).fetchone()
            if ownership_row is None:
                raise RecoveryError('migration ownership group missing')
            ownership = object_value(json.loads(ownership_row[0]))
            if ownership and (ownership.get('sealed_record') != str(sealed) or ownership.get('sealed_sha256') != sha(sealed)
                    or ownership.get('recovery_bundle') != str(bundle.absolute()) or ownership.get('recovery_bundle_sha256') != sha(bundle)):
                raise RecoveryError('thaw guard or reader differs from committed migration ownership')
            for (raw,) in connection.execute('SELECT roots_json FROM migrationsource WHERE group_id=?', (group_id,)):
                for role, value in object_value(json.loads(raw)).items():
                    if role in {'tasks', 'settings', 'database', 'media'} and value is not None:
                        if not any(Path(string(value)).is_relative_to(source) for source in sources):
                            raise RecoveryError('registered source is outside this Supervisor')
            connection.execute('PRAGMA synchronous=FULL')
            connection.execute('BEGIN IMMEDIATE')
            receipt = withdraw(connection, group_id, record.profile, sha(sealed))
            if receipt['category'] == 'R1' and not ownership:
                raise RecoveryError('activated group lacks pinned ownership')
            connection.commit()
            observed = supervisor._inventory()
            if len(observed) != len(record.entries) or any(
                    item.model_copy(update={'mode': expected.mode, 'flags': expected.flags}) != expected
                    for item, expected in zip(observed, record.entries, strict=True)):
                raise RecoveryError('original source bytes or inode changed during interrupted thaw')
            allowed = guard_root / 'thaw-allowed.json'
            if allowed.exists() and object_value(json.loads(allowed.read_bytes())) != receipt:
                raise RecoveryError('guard permission receipt differs from committed withdrawal')
            finished = connection.execute('SELECT state FROM migrationgroup WHERE id=?', (group_id,)).fetchone() == ('thawed',)
            if finished:
                proof = object_value(json.loads((guard_root / 'thawed.json').read_bytes()))
                if (not allowed.exists() or observed != record.entries or proof != {'version': 1,
                        'root_group_id': group_id, 'seal_sha256': sha(sealed), 'restored_entries': len(observed)}
                        or not committed(connection, group_id, receipt)):
                    raise RecoveryError('completed thaw proof or original permissions differ')
            else:
                supervisor.thaw(dependencies_released=lambda identifier: committed(connection, identifier, receipt), receipt=receipt)
            if not finished:
                connection.execute('BEGIN IMMEDIATE')
                if not committed(connection, group_id, receipt):
                    raise RecoveryError('committed group proof changed during thaw')
                connection.execute("UPDATE migrationgroup SET state='thawed' WHERE id=?", (group_id,))
                connection.commit()
    output.mkdir(parents=True, exist_ok=False, mode=0o700)
    json_write(output / 'thaw-receipt.json', receipt)
    return output / 'thaw-receipt.json'
