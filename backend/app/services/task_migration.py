from __future__ import annotations

import json
from pathlib import Path
from typing import Literal
from uuid import UUID, uuid4

from sqlalchemy import Engine
from sqlmodel import Session, select

from app.arctime.subtitle_document import SubtitleDocument, validate_source
from app.models_migration import MigrationBatch, MigrationDependency, MigrationGroup, MigrationMember, MigrationSource
from app.models_unified import TaskBinding
from app.services.migration_groups import create_group, require_quiescent
from app.services.migration_snapshot import (
    Candidate, SourceRoots, TaskMetadata, archive_sources, copy_context, generation, inventory, public_json, read_candidate,
)
from app.services.source_seal import Supervisor
from app.services.task_artifacts import ResolvedArtifacts
from app.services.task_operations import OperationConflict, bind_task, canonical, digest
from app.services.unified_database import begin_unified_mutation
from app.services.unified_files import checked_path, immutable_bytes
from pydantic import JsonValue


class Migrator:
    def __init__(self, engine: Engine, root: Path, settings_root: Path, *, recovery_bundle: Path | None = None,
                 recovery_bundle_sha256: str | None = None) -> None:
        self.engine, self.root, self.settings_root = engine, root.absolute(), settings_root.absolute()
        self.recovery_bundle, self.recovery_bundle_sha256 = recovery_bundle, recovery_bundle_sha256

    def register(self, identifier: UUID, roots: SourceRoots, *, origin: Literal['companion', 'workstation'],
                 mode: Literal['initial', 'relocate', 'restore'] = 'initial', expected_generation: str | None = None) -> str:
        if any(destination.is_relative_to(source) or source.is_relative_to(destination)
                for source in roots.roots for destination in (self.root, self.settings_root)):
            raise OperationConflict('new task/settings domains overlap historical source')
        if self.engine.url.database and any(Path(self.engine.url.database).absolute().is_relative_to(source) for source in roots.roots):
            raise OperationConflict('unified database is inside a historical source domain')
        current_generation = generation(inventory(roots), roots.public_runtime)
        with Session(self.engine) as session:
            begin_unified_mutation(session)
            source = session.get(MigrationSource, str(identifier))
            if source is not None:
                if source.origin != origin:
                    raise OperationConflict('registered source origin changed')
                previous_group = session.get(MigrationGroup, source.group_id)
                reopening = previous_group is not None and previous_group.state == 'thawed'
                if source.roots_json == roots.model_dump_json() and not reopening:
                    return source.group_id
                if source.roots_json != roots.model_dump_json() and (mode == 'initial' or expected_generation != current_generation or expected_generation != source.registered_generation):
                    raise OperationConflict('renamed/restored source requires explicit generation matching')
                if session.exec(select(TaskBinding).where(TaskBinding.source_instance_id == str(identifier), TaskBinding.state == 'activated')).first():
                    raise OperationConflict('active source relocation requires a new protected epoch')
                previous = SourceRoots.model_validate_json(source.roots_json)
                aliases = json.loads(source.path_aliases_json)
                for role in ('tasks', 'media'):
                    old, new = getattr(previous, role), getattr(roots, role)
                    if old is not None and new is not None and old != new:
                        aliases = {key: str(new) if value == str(old) else value for key, value in aliases.items()}
                        aliases[str(old)] = str(new)
                source.path_aliases_json = canonical(aliases)
                source.roots_json = roots.model_dump_json()
                if reopening:
                    group = create_group(session)
                    if group.ever_activated:
                        raise OperationConflict('register all source domains before activating the new epoch')
                    source.group_id, source.registered_generation = group.id, current_generation
            else:
                if mode != 'initial':
                    raise OperationConflict('restore/relocate requires an existing external source identity')
                for other in session.exec(select(MigrationSource)).all():
                    if any(first.is_relative_to(second) or second.is_relative_to(first)
                            for first in SourceRoots.model_validate_json(other.roots_json).roots for second in roots.roots):
                        raise OperationConflict('source roots already registered; independent branches require independent copies')
                group = create_group(session)
                if group.ever_activated:
                    raise OperationConflict('register all source domains before activation of this guarded epoch')
                source = MigrationSource(id=str(identifier), group_id=group.id, origin=origin, roots_json=roots.model_dump_json(),
                    registered_generation=current_generation)
            group_id = source.group_id
            session.add(source)
            session.commit()
            return group_id

    def prepare(self, source_id: UUID, context: ResolvedArtifacts, document: SubtitleDocument, *,
                metadata: TaskMetadata, history: JsonValue = None, batch_id: str | None = None) -> str:
        if context.source.source_instance_id != source_id:
            raise OperationConflict('candidate source instance mismatch')
        public_json(history)
        validate_source(document, context.document(document.style))
        with Session(self.engine) as session:
            source = session.get(MigrationSource, str(source_id))
            if source is None:
                raise OperationConflict('register external source identity before preparation')
            roots = SourceRoots.model_validate_json(source.roots_json)
            group_id, origin = source.group_id, source.origin
        for reference in context.source.files:
            path = context.source.checked(reference)
            normalized = self.root / f'.unified/import-normalization/{source_id}'
            if not any(path.is_relative_to(root) for root in roots.roots) and not path.is_relative_to(normalized):
                raise OperationConflict('unregistered external media dependency')
        files = inventory(roots)
        checksum = generation(files, roots.public_runtime)
        prefix = f'.unified/imports/{source_id}/{checksum}'
        archive_sources(self.root, roots, files, prefix + '/archive')
        copied = copy_context(self.root, context.source, f'.unified/results/import-{source_id}-{checksum}/{context.source.task_id}')
        base = context.document(document.style)
        migrated = document.model_copy(update={'source_fingerprint': copied.fingerprint})
        validate_source(document, base)
        candidate = Candidate(source_id=source_id, legacy_id=context.source.legacy_id, generation=checksum,
            files=files, context=copied, document=migrated, legacy_fingerprint=document.source_fingerprint, metadata=metadata, history=history,
            public_runtime=roots.public_runtime)
        body = candidate.model_dump_json().encode()
        name = f'{prefix}/{context.source.task_id}-{digest(body)}.json'
        immutable_bytes(checked_path(self.root, name), body)
        with Session(self.engine) as session:
            begin_unified_mutation(session)
            group = session.get(MigrationGroup, group_id)
            if group is None or group.state != 'open':
                raise OperationConflict('migration epoch is not open')
            binding = session.get(TaskBinding, context.source.task_id)
            if binding is not None and binding.state == 'withdrawn':
                binding.state = 'prepared'
            if binding is not None and binding.source_generation != checksum and binding.state != 'activated':
                binding.source_generation = checksum
                session.add(binding)
            binding = bind_task(session, source_id, context.source.legacy_id, checksum, origin=origin)
            if binding.state == 'activated':
                return self._existing_batch(session, binding.task_id, checksum)
            if batch_id is None:
                duplicate = session.exec(select(MigrationMember).where(MigrationMember.task_id == binding.task_id,
                    MigrationMember.candidate_sha256 == digest(body), MigrationMember.state.in_(['prepared', 'verified']))).first()
                if duplicate is not None:
                    return duplicate.batch_id
            batch = session.get(MigrationBatch, batch_id) if batch_id else None
            if batch is not None and (batch.source_id != str(source_id) or batch.state != 'prepared'):
                raise OperationConflict('batch source/state changed')
            if batch is None:
                batch = MigrationBatch(id=batch_id or uuid4().hex, group_id=group_id, source_id=str(source_id),
                    package_path=prefix + '/archive/settings', package_sha256=checksum)
                session.add(batch)
                session.flush()
                session.add(MigrationDependency(id=uuid4().hex, group_id=group_id, batch_id=batch.id,
                    source_id=str(source_id), generation=checksum, kind='source-and-global-package'))
            existing = session.exec(select(MigrationMember).where(MigrationMember.batch_id == batch.id,
                MigrationMember.task_id == binding.task_id)).first()
            if existing is None:
                session.add(MigrationMember(id=uuid4().hex, batch_id=batch.id, task_id=binding.task_id,
                    generation=checksum, candidate_path=name, candidate_sha256=digest(body)))
            elif existing.candidate_sha256 != digest(body):
                raise OperationConflict('batch member changed; prepare a new batch')
            binding.root_group_id = group_id
            registered = session.get(MigrationSource, str(source_id))
            registered.registered_generation = checksum
            session.add_all([binding, registered])
            result = batch.id
            session.commit()
            return result

    def _existing_batch(self, session: Session, task_id: str, checksum: str) -> str:
        member = session.exec(select(MigrationMember).where(MigrationMember.task_id == task_id,
            MigrationMember.generation == checksum, MigrationMember.state == 'activated')).first()
        if member is None:
            raise OperationConflict('activated mapping has no matching migration proof')
        return member.batch_id

    def verify(self, batch_id: str) -> None:
        with Session(self.engine) as session:
            begin_unified_mutation(session)
            batch = session.get(MigrationBatch, batch_id)
            if batch is None or batch.state not in {'prepared', 'verified'}:
                raise OperationConflict('batch is not eligible for verification')
            members = session.exec(select(MigrationMember).where(MigrationMember.batch_id == batch_id)).all()
            if not members:
                raise OperationConflict('empty migration batch')
            for member in members:
                candidate = read_candidate(self.root, member.candidate_path, member.candidate_sha256)
                if candidate.context.task_id != member.task_id or candidate.generation != member.generation:
                    raise OperationConflict('candidate identity mismatch')
                member.state = 'verified'
                session.add(member)
            batch.state = 'verified'
            session.add(batch)
            session.commit()

    def activate(self, batch_id: str, supervisor: Supervisor) -> None:
        if self.recovery_bundle is None or self.recovery_bundle_sha256 is None:
            raise OperationConflict('verified independent recovery reader/helper bundle is required before activation')
        from app.services.recovery_bundle import verify_bundle
        verify_bundle(self.recovery_bundle, self.recovery_bundle_sha256)
        seal = supervisor.verify()
        with Session(self.engine) as session:
            begin_unified_mutation(session)
            require_quiescent(session)
            batch = session.get(MigrationBatch, batch_id)
            if batch is None or batch.group_id != seal.root_group_id or batch.state not in {'verified', 'activated'}:
                raise OperationConflict('verified batch/continuous Supervisor ownership required')
            if batch.state == 'activated':
                from app.services.migration_ownership import verify_ownership
                verify_ownership(self.engine, supervisor)
                return
            if not all(any(root.is_relative_to(domain) for domain in supervisor.sources)
                    for registered in session.exec(select(MigrationSource).where(MigrationSource.group_id == batch.group_id)).all()
                    for root in SourceRoots.model_validate_json(registered.roots_json).roots):
                raise OperationConflict('all root-group sources must be covered by the same Supervisor')
            source = session.get(MigrationSource, batch.source_id)
            roots = SourceRoots.model_validate_json(source.roots_json) if source else None
            if roots is None or any(not any(root.is_relative_to(domain) for domain in supervisor.sources) for root in roots.roots):
                raise OperationConflict('source domain missing from persistent seal')
            if roots.public_runtime is None:
                raise OperationConflict('explicit complete public host settings package required before activation')
            checksum = generation(inventory(roots), roots.public_runtime)
            if source.origin == 'workstation':
                from app.services.migration_workstation import require_workstation_stopped
                require_workstation_stopped(roots, self.root)
            else:
                from app.services.task_import import discover_companion
                if any(item.eligibility == 'active' for item in discover_companion(roots.tasks, UUID(source.id))):
                    raise OperationConflict('old Companion task or secondary writer is still active')
            if checksum != batch.package_sha256:
                raise OperationConflict('global package generation changed')
            from app.services.migration_globals import activate_package
            activate_package(session, self.settings_root, checked_path(self.root, batch.package_path), UUID(batch.source_id), checksum)
            from app.services.migration_globals import activate_runtime_settings
            activate_runtime_settings(session, self.settings_root, roots.public_runtime, UUID(batch.source_id), checksum)
            members = session.exec(select(MigrationMember).where(MigrationMember.batch_id == batch_id)).all()
            for member in members:
                if member.state not in {'verified', 'activated'} or checksum != member.generation:
                    raise OperationConflict('source changed after preparation; prepare and verify a fresh generation')
                candidate = read_candidate(self.root, member.candidate_path, member.candidate_sha256)
                from app.services.migration_activation import activate_candidate
                activate_candidate(session, self.root, candidate, batch)
                member.state = 'activated'
                session.add(member)
            group = session.get(MigrationGroup, batch.group_id)
            if group is None or group.state != 'open':
                raise OperationConflict('root group is not open')
            from app.services.migration_ownership import Ownership
            ownership = Ownership(sealed_record=(supervisor.guard_root / 'sealed.json').absolute(),
                sealed_sha256=digest((supervisor.guard_root / 'sealed.json').read_bytes()),
                recovery_bundle=self.recovery_bundle.absolute(), recovery_bundle_sha256=self.recovery_bundle_sha256)
            if group.ownership_json not in {'{}', ownership.model_dump_json()}:
                raise OperationConflict('group already belongs to another guard/recovery epoch')
            group.ownership_json = ownership.model_dump_json()
            group.ever_activated, batch.state = True, 'activated'
            session.add_all([group, batch])
            session.commit()

    def thaw(self, group_id: str, supervisor: Supervisor) -> None:
        from app.services.migration_thaw import thaw
        thaw(self.engine, group_id, supervisor)
