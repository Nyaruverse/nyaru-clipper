from __future__ import annotations

import json
import os
import re
import shutil
import signal
import subprocess
import time
from pathlib import Path

from recovery_manifest import formats, verify
from recovery_storage import RecoveryError, checked, independent, inventory, json_write, object_value, sha, string


def legacy_browser(manifest: Path, output: Path) -> int:
    value, roles, _ = verify(manifest)
    legacy = object_value(value.get('legacy'))
    reader_reference = object_value(value.get('reader_bundle'))
    bundle_path = Path(string(reader_reference.get('path')))
    if sha(bundle_path) != reader_reference.get('sha256'):
        raise RecoveryError('archived recovery bundle mismatch')
    formats(bundle_path)
    bundle = object_value(json.loads(bundle_path.read_bytes()))
    helper_reference = object_value(bundle.get('legacy_helper'))
    helper = checked(bundle_path.parent, string(helper_reference.get('path')))
    snapshot_root = Path(string(legacy.get('snapshot')))
    if helper_reference.get('offline_abi') != 'nyaru-local-recovery-v1' or sha(helper) != helper_reference.get('sha256'):
        raise RecoveryError('qualified archived helper missing')
    if inventory(snapshot_root) != object_value(legacy.get('files')):
        raise RecoveryError('archived legacy working source changed')
    if any(Path(name).name == 'config.json' or any(part.startswith('.chatgpt') for part in Path(name).parts)
            for name in inventory(snapshot_root)):
        raise RecoveryError('legacy recovery source contains private authorization configuration')
    originals = [Path(string(object_value(member).get('source'))) for member in object_value(value['roots']).values()]
    independent([*sorted(set(originals)), manifest.absolute().parent, snapshot_root, output.absolute(), bundle_path.parent])
    output.mkdir(parents=True, exist_ok=False, mode=0o700)
    working, ready = output / 'working', output / 'ready.json'
    shutil.copytree(snapshot_root, working, copy_function=shutil.copyfile)
    environment = {**os.environ, 'NYARU_RECOVERY_LOCAL_ONLY': '1'}
    with (output / 'helper.log').open('xb') as log:
        process = subprocess.Popen([str(helper), '--data', str(working), '--ready', str(ready), '--parent-pid', str(os.getpid())],
            env=environment, stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True)
        previous_handlers = {}
        def interrupted(_number: int, _frame) -> None:
            raise KeyboardInterrupt
        for number in (signal.SIGINT, signal.SIGTERM):
            previous_handlers[number] = signal.signal(number, interrupted)
        try:
            deadline = time.monotonic() + 45
            while not ready.exists():
                if process.poll() is not None or time.monotonic() >= deadline:
                    raise RecoveryError('archived helper failed to become ready; evidence retained')
                time.sleep(.1)
            status = object_value(json.loads(ready.read_bytes()))
            if re.fullmatch(r'http://127\.0\.0\.1:[1-9][0-9]{0,4}', string(status.get('url'))) is None or status.get('pid') != process.pid:
                raise RecoveryError('invalid archived helper ready record')
            print(json.dumps({'url': status['url'], 'working': str(working)}, ensure_ascii=False), flush=True)
            return process.wait()
        finally:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait(timeout=5)
            ready.unlink(missing_ok=True)
            json_write(output / 'helper-closed.json', {'pid': process.pid, 'returncode': process.returncode})
            for number, handler in previous_handlers.items():
                signal.signal(number, handler)
