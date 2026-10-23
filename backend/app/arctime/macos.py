from __future__ import annotations

import argparse
from contextlib import ExitStack
import os
from pathlib import Path
import shutil
import signal
import socket
import sys
import tempfile
import threading
import time

from app.arctime.media import fingerprint, write_json

MODEL_SHA256 = "1be3a9b2063867b937e64e2ec7483364a79917e157fa98c5d94b5c1fffea987b"


def prepare_model(resources: Path, data: Path) -> Path:
    from app.arctime.workflow import exclusive_lock

    data.mkdir(parents=True, mode=0o700, exist_ok=True)
    models = data / "models"
    models.mkdir(mode=0o700, exist_ok=True)
    target = models / "ggml-small.bin"
    with exclusive_lock(data / ".model.lock"):
        if target.exists():
            if target.is_symlink() or fingerprint(target) != MODEL_SHA256:
                raise ValueError("Existing model checksum differs; preserving it. Check the models folder.")
            return target
        source = resources / "models" / target.name
        if fingerprint(source) != MODEL_SHA256:
            raise ValueError("Bundled model checksum differs; rebuild the app.")
        descriptor, name = tempfile.mkstemp(prefix=".model-", dir=models)
        os.close(descriptor)
        try:
            shutil.copyfile(source, name)
            with open(name, "rb") as handle:
                os.fsync(handle.fileno())
            os.replace(name, target)
        finally:
            Path(name).unlink(missing_ok=True)
    return target


def watch_parent(parent_pid: int) -> None:
    while os.getppid() == parent_pid:
        time.sleep(1)
    os.killpg(os.getpgrp(), signal.SIGKILL)


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if args and args[0] == "--yt-dlp":
        import yt_dlp
        yt_dlp.main(args[1:])
        return 0
    if args and args[0] == '--unified-cli':
        from app.arctime.unified_cli import main as unified_main
        return unified_main(args[1:])
    if args and args[0] == '--migration-cli':
        from app.arctime.migration_cli import main as migration_main
        return migration_main(args[1:])

    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--ready", type=Path, required=True)
    parser.add_argument("--parent-pid", type=int, required=True)
    parser.add_argument('--unified-runtime', type=Path)
    parser.add_argument('--migration-guard', type=Path)
    options = parser.parse_args(args)
    if os.getpgrp() != os.getpid():
        os.setsid()
    threading.Thread(target=watch_parent, args=(options.parent_pid,), daemon=True).start()
    resources = Path(sys._MEIPASS) if getattr(sys, "frozen", False) else Path(__file__).resolve().parents[3]
    os.environ["GGML_BACKEND_PATH"] = str(resources)
    os.environ["APP_DATA_DIR"] = str(options.data)
    with ExitStack() as stack:
        return serve(options, resources, stack)


def serve(options: argparse.Namespace, resources: Path, stack: ExitStack) -> int:
    host = None
    if options.unified_runtime is not None:
        from app.services.unified_runtime import open_runtime
        host = open_runtime(options.unified_runtime)
        if options.migration_guard is not None:
            from app.arctime.migration_cli import GuardRecipe
            from app.services.source_seal import Supervisor
            recipe = GuardRecipe.model_validate_json(options.migration_guard.read_bytes())
            if not recipe.guard_root.absolute().is_relative_to(host.guard_root):
                raise ValueError('registered source guard domain required')
            supervisor = stack.enter_context(Supervisor(recipe.domains, recipe.guard_root, host.credential_root, recipe.group_id, recipe.locks))
            supervisor.verify()
            host.supervisor = supervisor
        model = host.model
    else:
        model = prepare_model(resources, options.data)
    from app.arctime.gui import create_app
    import uvicorn
    from app.arctime.http_server import CompanionServer

    app = create_app(host.root if host else options.data / 'runs', model=model, web_dist=resources / "web", host=host)
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen(128)
        port = listener.getsockname()[1]
        write_json(options.ready, {"url": f"http://127.0.0.1:{port}", "pid": os.getpid()})
        try:
            CompanionServer(uvicorn.Config(app, log_level="warning", access_log=False)).run(sockets=[listener])
        finally:
            options.ready.unlink(missing_ok=True)
    return 0
