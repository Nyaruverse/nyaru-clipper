from pathlib import Path

from sqlmodel import Session

from app.arctime.migration_cli import GuardRecipe
from app.arctime.unified_host import NativeHost
from app.models_migration import MigrationGroup
from app.services.migration_ownership import Ownership
from app.services.recovery_bundle import verify_bundle
from app.services.source_seal import SealRecord
from app.services.task_operations import OperationConflict, canonical
from app.services.unified_files import checked_path, immutable_bytes
from app.services.unified_runtime import RuntimeManifest


def export_recipes(host: NativeHost, manifest: RuntimeManifest, guard_path: Path, output: Path) -> None:
    recipe = GuardRecipe.model_validate_json(guard_path.read_bytes())
    if not recipe.guard_root.absolute().is_relative_to(host.guard_root):
        raise OperationConflict('recovery recipe guard is outside the registered domain')
    seal = SealRecord.model_validate_json(checked_path(recipe.guard_root, 'sealed.json').read_bytes())
    if seal.root_group_id != recipe.group_id or seal.roots != tuple(map(str, recipe.domains)) or seal.locks != tuple(sorted(map(str, recipe.locks))):
        raise OperationConflict('recovery recipe differs from the durable guard journal')
    if manifest.recovery_bundle is None or manifest.recovery_bundle_sha256 is None:
        raise OperationConflict('pin the independent recovery reader/helper first')
    verify_bundle(manifest.recovery_bundle, manifest.recovery_bundle_sha256)
    with Session(host.engine) as session:
        group = session.get(MigrationGroup, recipe.group_id)
        if group is None or group.state not in {'open', 'withdrawing'}:
            raise OperationConflict('recovery group is missing or already closed')
        if group.ownership_json != '{}':
            ownership = Ownership.model_validate_json(group.ownership_json)
            if (ownership.recovery_bundle, ownership.recovery_bundle_sha256) != (manifest.recovery_bundle, manifest.recovery_bundle_sha256):
                raise OperationConflict('retain the exact reader/helper pinned by this ownership epoch')
    roles = {'unified_db': manifest.data / 'db', 'task_root': host.root, 'settings_root': host.settings_root,
        'guard_root': host.guard_root, 'global_package_root': manifest.data / 'packages', 'migration_registry': manifest.data / 'registry'}
    locks = (host.root / '.gui.lock', host.guard_root / '.heavy.lock', recipe.guard_root / '.guard.lock')
    if any(not path.is_file() for path in locks) or not host.credential_root.is_dir():
        raise OperationConflict('registered recovery locks or credential reference are missing; do not create replacements')
    if any(output.absolute().is_relative_to(root) or root.is_relative_to(output.absolute())
            for root in (*roles.values(), host.credential_root, manifest.recovery_bundle.parent, *recipe.domains)):
        raise OperationConflict('recovery recipes must be outside all original and reader domains')
    output.mkdir(mode=0o700, parents=True, exist_ok=False)
    bundle = {'path': str(manifest.recovery_bundle), 'sha256': manifest.recovery_bundle_sha256}
    snapshot = {'version': 1, 'root_group_id': recipe.group_id, 'roots': {name: str(path) for name, path in roles.items()},
        'credential_root': str(host.credential_root), 'locks': list(map(str, sorted(locks))),
        'database': 'unified.sqlite3', 'reader_bundle': bundle}
    thaw = {'version': 1, 'database': str(manifest.data / 'db/unified.sqlite3'),
        'credential_root': str(host.credential_root), 'bundle_sha256': manifest.recovery_bundle_sha256,
        'guard': recipe.model_dump(mode='json')}
    immutable_bytes(output / 'snapshot.json', canonical(snapshot).encode())
    immutable_bytes(output / 'thaw.json', canonical(thaw).encode())
