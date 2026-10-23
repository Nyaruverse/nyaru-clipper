from __future__ import annotations

from pathlib import Path
from uuid import UUID, uuid4, uuid5

from sqlmodel import Session

from app.arctime.subtitle_style import SubtitleStyle
from app.arctime.subtitle_templates import ProjectTemplate, StudioSettings, StyleTemplate
from app.models_unified import GlobalHead, GlobalVersion
from app.services.task_operations import OperationConflict, digest
from app.services.unified_files import checked_path, file_sha256, immutable_bytes
from app.services.public_runtime_settings import PublicRuntimeSettings


def activate_runtime_settings(session: Session, root: Path, value: PublicRuntimeSettings, source: UUID, generation: str) -> None:
    body = value.model_dump_json().encode()
    _register(session, root, f'migration-packages/{source}/{generation}/runtime-public.json', body)
    if session.get(GlobalHead, 'runtime/settings.json') is None:
        _register(session, root, 'runtime/settings.json', body)
    if session.get(GlobalHead, 'llm/preferences.json') is None:
        _register(session, root, 'llm/preferences.json', value.companion.model_dump_json().encode())


def _register(session: Session, root: Path, key: str, body: bytes) -> None:
    prior = session.get(GlobalHead, key)
    checksum = digest(body)
    if prior is not None:
        if prior.body_sha256 != checksum or prior.deleted:
            raise OperationConflict('migration public setting conflicts with existing content')
        return
    relative = f'.unified/global/{digest(key)}/r1-{checksum}'
    immutable_bytes(checked_path(root, relative), body)
    session.add_all([GlobalHead(key=key, revision=1, body_sha256=checksum, body_path=relative),
        GlobalVersion(id=uuid4().hex, key=key, revision=1, body_sha256=checksum, body_path=relative)])
    session.flush()


def activate_package(session: Session, settings_root: Path, source_root: Path, source_id: UUID, generation: str) -> None:
    templates = source_root / 'templates'
    namespace = uuid5(source_id, generation)
    projects = {}
    for path in sorted((templates / 'projects').glob('*.json')):
        item = ProjectTemplate.model_validate_json(path.read_bytes())
        if path.name != item.id + '.json':
            raise OperationConflict('source project identity mismatch')
        blob = checked_path(templates, 'projects/' + item.id + '.atpj')
        if blob.stat().st_size != item.size or file_sha256(blob) != item.sha256:
            raise OperationConflict('source project body hash mismatch')
        identifier = uuid5(namespace, 'project:' + item.id).hex
        projects[item.id] = identifier
        copied = item.model_copy(update={'id': identifier, 'name': item.name + ' · ' + str(source_id)[:8]})
        _register(session, settings_root, f'templates/projects/{identifier}.atpj', blob.read_bytes())
        _register(session, settings_root, f'templates/projects/{identifier}.json', copied.model_dump_json().encode())
    styles = {'nyaru': 'nyaru', 'default': 'default', 'white': 'white'}
    for path in sorted((templates / 'styles').glob('*.json')):
        item = StyleTemplate.model_validate_json(path.read_bytes())
        if path.name != item.id + '.json' or item.builtin:
            raise OperationConflict('source style identity mismatch')
        if item.arctime_template_id is not None and item.arctime_template_id not in projects:
            raise OperationConflict('unresolved source project binding')
        identifier = uuid5(namespace, 'style:' + item.id).hex
        styles[item.id] = identifier
        copied = item.model_copy(update={'id': identifier, 'name': item.name + ' · ' + str(source_id)[:8],
            'arctime_template_id': projects.get(item.arctime_template_id)})
        _register(session, settings_root, f'templates/styles/{identifier}.json', copied.model_dump_json().encode())
    for name, schema in [('defaults.json', SubtitleStyle), ('studio-settings.json', StudioSettings)]:
        path = templates / name
        if not path.is_file():
            continue
        value = schema.model_validate_json(path.read_bytes())
        if isinstance(value, StudioSettings):
            if value.default_template_id is not None and value.default_template_id not in styles:
                raise OperationConflict('unresolved source default template')
            value = value.model_copy(update={'default_template_id': styles.get(value.default_template_id)})
        body = value.model_dump_json().encode()
        _register(session, settings_root, f'migration-packages/{source_id}/{generation}/{name}', body)
        if session.get(GlobalHead, 'templates/' + name) is None:
            _register(session, settings_root, 'templates/' + name, body)
