from __future__ import annotations

import argparse
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

    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--ready", type=Path, required=True)
    parser.add_argument("--parent-pid", type=int, required=True)
    options = parser.parse_args(args)
    if os.getpgrp() != os.getpid():
        os.setsid()
    threading.Thread(target=watch_parent, args=(options.parent_pid,), daemon=True).start()
    resources = Path(sys._MEIPASS) if getattr(sys, "frozen", False) else Path(__file__).resolve().parents[3]
    os.environ["GGML_BACKEND_PATH"] = str(resources)
    os.environ["APP_DATA_DIR"] = str(options.data)
    model = prepare_model(resources, options.data)
    from app.arctime.gui import create_app
    import uvicorn

    app = create_app(options.data / "runs", model=model, web_dist=resources / "web")
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen(128)
        port = listener.getsockname()[1]
        write_json(options.ready, {"url": f"http://127.0.0.1:{port}", "pid": os.getpid()})
        try:
            uvicorn.Server(uvicorn.Config(app, log_level="warning", access_log=False)).run(sockets=[listener])
        finally:
            options.ready.unlink(missing_ok=True)
    return 0
