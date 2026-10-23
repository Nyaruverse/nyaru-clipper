from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, JsonValue

from app.services.task_operations import canonical, digest
from app.services.unified_files import checked_path, immutable_bytes


class RequestDocument(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    path: str
    sha256: str = Field(pattern=r'^[0-9a-f]{64}$')


def freeze_request(root: Path, task_id: str, body: dict[str, JsonValue]) -> dict[str, JsonValue]:
    request = body.get('request')
    if not isinstance(request, dict) or request.get('document') is None:
        return body
    request = dict(request)
    content = canonical(request.pop('document')).encode()
    checksum = digest(content)
    path = f'{task_id}/.unified/requests/{uuid4().hex}/document-{checksum}.json'
    immutable_bytes(checked_path(root, path), content)
    request['document_ref'] = RequestDocument(path=path, sha256=checksum).model_dump(mode='json')
    return {**body, 'request': request}


def restore_request(root: Path, body: dict[str, JsonValue]) -> dict[str, JsonValue]:
    import json
    request = body.get('request')
    if not isinstance(request, dict) or 'document_ref' not in request:
        return body
    request = dict(request)
    reference = RequestDocument.model_validate(request.pop('document_ref'))
    content = checked_path(root, reference.path).read_bytes()
    if digest(content) != reference.sha256:
        raise RequestIntegrityError('queued editing document snapshot changed')
    request['document'] = json.loads(content)
    return {**body, 'request': request}


class RequestIntegrityError(ValueError):
    pass
