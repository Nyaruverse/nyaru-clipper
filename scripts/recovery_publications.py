from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

from recovery_storage import JsonValue, RecoveryError, checked, object_value, sha, string


def canonical(value: JsonValue) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False)


def checksum(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def publication(connection: sqlite3.Connection, tasks: Path, row: sqlite3.Row) -> dict[str, JsonValue]:
    from frozen_recovery_formats import PreparedReceipt
    receipt_file = checked(tasks, f".unified/receipts/{row['id']}.json")
    content = receipt_file.read_text()
    if checksum(content) != row['receipt_sha256'] or content != row['receipt_json']:
        raise RecoveryError('registered publication receipt mismatch')
    receipt = object_value(json.loads(PreparedReceipt.model_validate_json(content).model_dump_json()))
    outputs = receipt.get('outputs')
    if receipt.get('version') != 1 or not isinstance(outputs, list) or not outputs:
        raise RecoveryError('unsupported publication format')
    members = [object_value(member) for member in outputs]
    if len({string(member.get('role')) for member in members}) != len(members):
        raise RecoveryError('duplicate required publication member')
    step = connection.execute('SELECT * FROM operationstep WHERE id=?', (row['step_id'],)).fetchone()
    attempt = connection.execute('SELECT * FROM operationattempt WHERE execution_token=?', (row['execution_token'],)).fetchone()
    if step is None or attempt is None or step['state'] != 'succeeded':
        raise RecoveryError('publication execution proof missing')
    for key in ('operation_id', 'attempt', 'execution_token', 'step_id'):
        if receipt.get(key) != row[key]:
            raise RecoveryError('publication execution identity mismatch')
    if (receipt.get('publication_id') != row['id'] or attempt['operation_id'] != row['operation_id']
            or attempt['attempt'] != row['attempt'] or attempt['snapshot_sha256'] != receipt.get('snapshot_sha256')
            or step['operation_id'] != row['operation_id'] or step['execution_token'] != row['execution_token']
            or step['attempt'] != row['attempt'] or checksum(step['metadata_json']) != receipt.get('child_snapshot_sha256')
            or set(json.loads(step['required_roles_json'])) != {member['role'] for member in members}
            or checksum(canonical([{key: value for key, value in member.items() if key != 'target'} for member in members])) != receipt.get('set_sha256')):
        raise RecoveryError('publication required set proof mismatch')
    operation = connection.execute('SELECT snapshot_json,snapshot_sha256 FROM unifiedoperation WHERE id=?', (row['operation_id'],)).fetchone()
    if operation is None or checksum(operation['snapshot_json']) != receipt.get('snapshot_sha256'):
        raise RecoveryError('publication operation snapshot proof missing')
    frozen = object_value(json.loads(operation['snapshot_json']))
    if (checksum(canonical(frozen.get('input', {}))) != receipt.get('input_sha256')
            or checksum(canonical(frozen.get('config', {}))) != receipt.get('configuration_sha256')
            or checksum(canonical([row['operation_id'], row['attempt'], row['step_id'], receipt['snapshot_sha256'],
                receipt['document_sha256'], receipt['set_sha256']])) != row['id']):
        raise RecoveryError('publication input/configuration/identity mismatch')
    for member in members:
        staging = string(member.get('staging'))
        if (not staging.startswith(f".unified/staging/{row['operation_id']}/{row['attempt']}/")
                or member.get('target') != f".unified/results/{row['id']}/{member['role']}{Path(staging).suffix}"):
            raise RecoveryError('publication member is outside its immutable execution namespace')
        path = checked(tasks, string(member.get('target')))
        if not path.is_file() or path.stat().st_size != member.get('size') or sha(path) != member.get('sha256'):
            raise RecoveryError('publication set unavailable')
    return receipt
