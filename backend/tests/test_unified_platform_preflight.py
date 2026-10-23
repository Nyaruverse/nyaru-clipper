from __future__ import annotations

import fcntl
import os
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.skipif(sys.platform not in {'darwin', 'linux'} or os.geteuid() == 0,
                    reason='Permission-seal preflight requires an ordinary POSIX user; root cannot certify it')
def test_persistent_permission_seal_and_read_only_lock_reacquisition(tmp_path: Path) -> None:
    root = tmp_path / 'old-root'
    root.mkdir()
    source = root / 'source.mp4'
    source.write_bytes(b'protected fixture source')
    lock = root / '.lock'
    lock.touch(mode=0o600)
    credential = tmp_path / 'separate-credential-fixture'
    credential.write_bytes(b'fixture credential reference remains separate')
    holder = subprocess.Popen([sys.executable, '-u', '-c',
        'import fcntl,sys; f=open(sys.argv[1],"r+"); fcntl.flock(f,fcntl.LOCK_EX); print("HELD",flush=True); sys.stdin.read()',
        str(lock)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    try:
        assert holder.stdout is not None and holder.stdout.readline().strip() == 'HELD'
        source.chmod(0o400)
        lock.chmod(0o400)
        root.chmod(0o500)
        for action in [
            'open(root/"source.mp4","wb")',
            'open(root/"new-file","wb")',
            '(root/"source.mp4").unlink()',
            '(root/"source.mp4").rename(root/"replaced.mp4")',
            'os.open(root/".lock",os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)',
        ]:
            probe = subprocess.run([sys.executable, '-c',
                'import os,sys; from pathlib import Path; root=Path(sys.argv[1]); ' + action, str(root)],
                capture_output=True, text=True, timeout=10)
            assert probe.returncode != 0 and 'PermissionError' in probe.stderr, action
        holder.kill()
        holder.wait(timeout=10)
        descriptor = os.open(lock, os.O_RDONLY | os.O_NOFOLLOW)
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        finally:
            os.close(descriptor)
        assert source.read_bytes() == b'protected fixture source'
        assert not (root / 'new-file').exists()
        assert credential.read_bytes() == b'fixture credential reference remains separate'
        assert root.stat().st_mode & 0o777 == 0o500
        assert source.stat().st_mode & 0o777 == 0o400
    finally:
        if holder.poll() is None:
            holder.kill()
            holder.wait(timeout=10)
        if holder.stdin is not None:
            holder.stdin.close()
        if holder.stdout is not None:
            holder.stdout.close()
        root.chmod(0o700)
        source.chmod(0o600)
        lock.chmod(0o600)
