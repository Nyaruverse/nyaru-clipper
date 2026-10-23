from __future__ import annotations

import os
import signal
import subprocess
import sys
from pathlib import Path

import pytest

from app.services.source_seal import GuardError, Supervisor


@pytest.mark.skipif(sys.platform != "darwin", reason="Requires the actual macOS immutable protection profile")
def test_supervisor_crash_keeps_seal_and_readonly_locks_can_be_reacquired(tmp_path: Path) -> None:
    source, guard, credentials = [tmp_path / name for name in ("old", "guard", "credentials")]
    source.mkdir()
    credentials.mkdir()
    (source / ".gui.lock").touch(mode=0o600)
    (source / "task").mkdir()
    (source / "task/.lock").touch(mode=0o600)
    (source / "task/video.mp4").write_bytes(b"old source")
    credential = credentials / "token-fixture"
    credential.write_bytes(b"synthetic protected bytes")
    credential.chmod(0o600)
    modes = {path.relative_to(source).as_posix(): path.stat().st_mode & 0o777 for path in [source, *source.rglob("*")]}
    code = "from pathlib import Path; import sys; from app.services.source_seal import Supervisor; source,guard,credentials=map(Path,sys.argv[1:]); supervisor=Supervisor((source,),guard,credentials,'group-a',(source/'.gui.lock',source/'task/.lock')); supervisor.__enter__(); supervisor.seal(); print('sealed',flush=True); input()"
    child = subprocess.Popen([sys.executable, "-c", code, str(source), str(guard), str(credentials)],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        assert child.stdout.readline().strip() == "sealed", child.stderr.read() if child.poll() is not None else ""
        child.send_signal(signal.SIGKILL)
        child.wait(timeout=10)
        with pytest.raises(PermissionError):
            (source / "task/video.mp4").write_bytes(b"old program edit")
        with pytest.raises(PermissionError):
            (source / "new-task").mkdir()
        with pytest.raises(PermissionError):
            source.rename(tmp_path / "replacement")
        with Supervisor((source,), guard, credentials, "group-a", (source / ".gui.lock", source / "task/.lock")) as supervisor:
            supervisor.verify()
            with pytest.raises(GuardError, match="dependencies"):
                supervisor.thaw(dependencies_released=lambda group: False)
            supervisor.thaw(dependencies_released=lambda group: group == "group-a")
        assert {path.relative_to(source).as_posix(): path.stat().st_mode & 0o777 for path in [source, *source.rglob("*")]} == modes
        assert credential.read_bytes() == b"synthetic protected bytes" and credential.stat().st_mode & 0o777 == 0o600
    finally:
        if child.poll() is None:
            child.kill()
            child.wait(timeout=10)
        for path in sorted([source, *source.rglob("*")], key=lambda path: len(path.parts)):
            os.chflags(path, 0)
            path.chmod(modes[path.relative_to(source).as_posix()])


def test_credentials_in_source_protection_domain_block_supervisor(tmp_path: Path) -> None:
    source = tmp_path / "old"
    source.mkdir()
    (source / ".gui.lock").touch()
    with pytest.raises(GuardError, match="credential"):
        Supervisor((source,), tmp_path / "guard", source / "auth", "group-a", (source / ".gui.lock",))
