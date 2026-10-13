import signal
import sys

import pytest

from app.arctime import media
from app.arctime.macos import prepare_model


def test_frozen_tools_take_priority_and_missing_tools_do_not_fall_back(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
    monkeypatch.setattr(media.shutil, "which", lambda name: "/opt/homebrew/bin/" + name)
    tool = tmp_path / "ffmpeg"
    tool.write_bytes(b"tool")
    tool.chmod(0o755)
    assert media.tool_path("ffmpeg") == str(tool)
    with pytest.raises(FileNotFoundError):
        media.tool_path("ffprobe")


def test_model_provisioning_is_atomic_and_preserves_existing_model(tmp_path, monkeypatch):
    from app.arctime import macos
    resources, data = tmp_path / "resources", tmp_path / "data"
    (resources / "models").mkdir(parents=True)
    source = resources / "models" / "ggml-small.bin"
    source.write_bytes(b"lmgg-test-model")
    monkeypatch.setattr(macos, "MODEL_SHA256", media.fingerprint(source))
    model = prepare_model(resources, data)
    assert model.read_bytes() == source.read_bytes()
    source.unlink()
    assert prepare_model(resources, data) == model
    model.write_bytes(b"existing-user-model")
    with pytest.raises(ValueError, match="checksum"):
        prepare_model(resources, data)
    assert model.read_bytes() == b"existing-user-model"


def test_invalid_bundled_model_is_never_published(tmp_path):
    resources = tmp_path / "resources"
    (resources / "models").mkdir(parents=True)
    (resources / "models" / "ggml-small.bin").write_bytes(b"bad download")
    with pytest.raises(ValueError, match="checksum"):
        prepare_model(resources, tmp_path / "data")
    assert not (tmp_path / "data/models/ggml-small.bin").exists()


def test_parent_loss_kills_entire_group_without_waiting_for_helper_exit(monkeypatch):
    from app.arctime import macos
    parents = iter([123, 1])
    signals = []
    monkeypatch.setattr(macos.os, "getppid", lambda: next(parents))
    monkeypatch.setattr(macos.os, "getpgrp", lambda: 456)
    monkeypatch.setattr(macos.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(macos.os, "killpg", lambda group, sig: signals.append((group, sig)))
    macos.watch_parent(123)
    assert signals == [(456, signal.SIGKILL)]
