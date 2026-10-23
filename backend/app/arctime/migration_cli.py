from __future__ import annotations

import argparse
import json
import socket
from pathlib import Path
from uuid import UUID
from typing import Literal, assert_never

from pydantic import BaseModel, ConfigDict, TypeAdapter
from sqlmodel import Session

from app.arctime.gui import create_app
from app.models_migration import MigrationSource
from app.services.migration_groups import cancel_batch, rollback_category
from app.services.migration_snapshot import SourceRoots
from app.services.source_seal import Supervisor
from app.services.task_migration import Migrator
from app.services.task_operations import OperationConflict
from app.services.unified_files import immutable_bytes
from app.services.unified_runtime import RuntimeManifest, open_runtime


class GuardRecipe(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    group_id: str
    domains: tuple[Path, ...]
    locks: tuple[Path, ...]
    guard_root: Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Explicit migration; discovery/preparation never starts engines')
    parser.add_argument('--runtime', type=Path, required=True)
    commands = parser.add_subparsers(dest='command', required=True)
    register = commands.add_parser('register')
    register.add_argument('--source', type=UUID, required=True)
    register.add_argument('--origin', choices=('companion', 'workstation'), required=True)
    register.add_argument('--roots', type=Path, required=True)
    register.add_argument('--mode', choices=('initial', 'relocate', 'restore'), default='initial')
    register.add_argument('--expected-generation')
    register.add_argument('--public-settings', type=Path)
    capture = commands.add_parser('capture-public')
    capture.add_argument('--output', type=Path, required=True)
    recovery = commands.add_parser('recovery-recipes')
    recovery.add_argument('--guard', type=Path, required=True)
    recovery.add_argument('--output-root', type=Path, required=True)
    prepare = commands.add_parser('prepare')
    prepare.add_argument('--source', type=UUID, required=True)
    prepare.add_argument('--legacy-id', required=True)
    prepare.add_argument('--batch')
    for name in ('verify', 'cancel'):
        command = commands.add_parser(name)
        command.add_argument('--batch', required=True)
    category = commands.add_parser('category')
    category.add_argument('--group', required=True)
    pin = commands.add_parser('pin-recovery')
    pin.add_argument('--bundle', type=Path, required=True)
    pin.add_argument('--sha256', required=True)
    for name in ('takeover', 'serve-guarded', 'thaw'):
        command = commands.add_parser(name)
        command.add_argument('--guard', type=Path, required=True)
        if name == 'takeover':
            command.add_argument('--batch', action='append', required=True)
        if name != 'thaw':
            command.add_argument('--port', type=int, default=0)
            command.add_argument('--host', default='127.0.0.1')
    options = parser.parse_args(argv)
    manifest = RuntimeManifest.model_validate_json(options.runtime.read_bytes())
    if options.command == 'pin-recovery':
        from app.services.recovery_bundle import verify_bundle
        verify_bundle(options.bundle, options.sha256)
        pinned = manifest.model_copy(update={'recovery_bundle': options.bundle.absolute(), 'recovery_bundle_sha256': options.sha256})
        target = manifest.data / f'runtime-recovery-{options.sha256}.json'
        immutable_bytes(target, pinned.model_dump_json().encode())
        print(target)
        return 0
    host = open_runtime(options.runtime)
    if options.command == 'recovery-recipes':
        from app.services.recovery_recipes import export_recipes
        export_recipes(host, manifest, options.guard, options.output_root)
        print(options.output_root)
        return 0
    if options.command == 'capture-public':
        from app.arctime.companion_llm import LLMConfig, PublicPreferences
        from app.services.public_runtime_settings import PUBLIC_FIELDS, PublicRuntimeSettings
        from app.settings import get_settings
        manager = LLMConfig(host.root, settings_root=host.settings_root, credential_root=host.credential_root, preferences=host.globals)
        try:
            if manager.config_error:
                raise OperationConflict('public provider configuration is invalid; preserve the private original')
            value = PublicRuntimeSettings(settings=get_settings().model_dump(mode='json', include=PUBLIC_FIELDS),
                companion=PublicPreferences(deepseek_model=manager.translation_model, llm_provider=manager.llm_provider,
                    chatgpt_model=manager.chatgpt_model), cpp_model=host.model, cpp_threads=host.threads)
            if options.output.absolute().is_relative_to(host.credential_root):
                raise OperationConflict('public snapshot output cannot enter the credential domain')
            immutable_bytes(options.output, value.model_dump_json().encode())
            print(options.output)
        finally:
            manager.chatgpt.close()
        return 0
    migration = Migrator(host.engine, host.root, host.settings_root, recovery_bundle=manifest.recovery_bundle,
        recovery_bundle_sha256=manifest.recovery_bundle_sha256)
    if options.command in {'takeover', 'serve-guarded', 'thaw'}:
        recipe = GuardRecipe.model_validate_json(options.guard.read_bytes())
        if not recipe.guard_root.absolute().is_relative_to(host.guard_root):
            raise OperationConflict('source guard record must belong to the registered unified guard domain')
        with Supervisor(recipe.domains, recipe.guard_root, host.credential_root, recipe.group_id, recipe.locks) as supervisor:
            if options.command == 'thaw':
                migration.thaw(recipe.group_id, supervisor)
                print(json.dumps({'group': recipe.group_id, 'state': 'thawed'}))
                return 0
            supervisor.seal()
            if options.command == 'takeover':
                for batch_id in options.batch:
                    migration.activate(batch_id, supervisor)
            host.supervisor = supervisor
            import uvicorn
            from app.arctime.http_server import CompanionServer
            from app.services.host_binding import private_host
            address = private_host(options.host)
            with socket.socket() as listener:
                listener.bind((address, options.port))
                listener.listen(128)
                print(json.dumps({'url': f'http://{address}:{listener.getsockname()[1]}', 'group': recipe.group_id}), flush=True)
                CompanionServer(uvicorn.Config(create_app(host.root, model=host.model, host=host, bind_host=address),
                    log_level='warning', access_log=False)).run(sockets=[listener])
        return 0
    action = TypeAdapter(Literal['register', 'prepare', 'verify', 'cancel', 'category']).validate_python(options.command)
    match action:
        case 'register':
            roots = SourceRoots.model_validate_json(options.roots.read_bytes())
            if options.public_settings is not None:
                from app.services.public_runtime_settings import PublicRuntimeSettings
                roots = roots.model_copy(update={'public_runtime': PublicRuntimeSettings.model_validate_json(options.public_settings.read_bytes())})
            print(migration.register(options.source, roots, origin=options.origin, mode=options.mode,
                expected_generation=options.expected_generation))
        case 'prepare':
            with Session(host.engine) as session:
                source = session.get(MigrationSource, str(options.source))
                if source is None:
                    raise OperationConflict('source identity is not registered')
                roots, origin = SourceRoots.model_validate_json(source.roots_json), source.origin
            origin_kind = TypeAdapter(Literal['companion', 'workstation']).validate_python(origin)
            match origin_kind:
                case 'companion':
                    from app.services.migration_companion import prepare_companion
                    print(prepare_companion(migration, options.source, roots, legacy_id=options.legacy_id, batch_id=options.batch))
                case 'workstation':
                    from app.services.migration_workstation import prepare_workstation
                    print(prepare_workstation(migration, options.source, roots, database_name=roots.database_name,
                        legacy_id=options.legacy_id, batch_id=options.batch))
                case unreachable:
                    assert_never(unreachable)
        case 'verify':
            migration.verify(options.batch)
            print(json.dumps({'batch': options.batch, 'state': 'verified'}))
        case 'cancel':
            with Session(host.engine) as session:
                result = cancel_batch(session, options.batch).state
                session.commit()
                print(result)
        case 'category':
            with Session(host.engine) as session:
                print(rollback_category(session, options.group))
        case unreachable:
            assert_never(unreachable)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
