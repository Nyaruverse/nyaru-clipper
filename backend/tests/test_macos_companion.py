import signal
import subprocess
import sys
from pathlib import Path

import pytest

from app.arctime import media
from app.arctime.macos import prepare_model


@pytest.mark.skipif(sys.platform != "darwin", reason="requires macOS Foundation and swiftc")
def test_native_registered_runtime_default_and_explicit_override(tmp_path: Path) -> None:
    source = (Path(__file__).resolve().parents[2] / "desktop/macos/App.swift").read_text()
    start = source.index('            let runtime = try option("--unified-runtime")')
    end = source.index('            let guardRecipe', start)
    harness = tmp_path / "runtime-selection.swift"
    harness.write_text(
        'import Foundation\nlet arguments = CommandLine.arguments\n'
        'let registeredRuntime = URL(fileURLWithPath: arguments[1]).appendingPathComponent("unified/runtime.json")\n'
        'func option(_ name: String) throws -> String? { arguments.count > 2 ? arguments[2] : nil }\n'
        + source[start:end] + '\nprint(runtime ?? "legacy")\n'
    )
    executable = tmp_path / "runtime-selection"
    subprocess.run(["/usr/bin/swiftc", str(harness), "-o", str(executable)], check=True, timeout=60)
    def selected(*extra: str) -> str:
        return subprocess.check_output([str(executable), str(tmp_path), *extra], text=True).strip()
    assert selected() == "legacy"
    manifest = tmp_path / "unified/runtime.json"
    manifest.parent.mkdir(); manifest.write_text('{}')
    assert selected() == str(manifest)
    assert selected('/explicit/fixture/runtime.json') == '/explicit/fixture/runtime.json'


@pytest.mark.skipif(sys.platform != "darwin", reason="requires macOS AppKit and swiftc")
def test_native_quit_marks_only_discard_as_destructive(tmp_path: Path) -> None:
    source = (Path(__file__).resolve().parents[2] / "desktop/macos/App.swift").read_text()
    start = source.index('            alert.addButton(withTitle: "保存并退出")')
    end = source.index("            alert.beginSheetModal", start)
    harness = tmp_path / "quit-buttons.swift"
    harness.write_text(
        "import AppKit\n"
        "let app = NSApplication.shared\nlet alert = NSAlert()\n" + source[start:end] + "\n"
        'print(alert.buttons.map { "\\($0.title): destructive=\\($0.hasDestructiveAction)" }.joined(separator: "\\n"))\n'
        "guard alert.buttons.count == 3,\n"
        '      alert.buttons[0].keyEquivalent == "\\r",\n'
        "      !alert.buttons[0].hasDestructiveAction,\n"
        "      !alert.buttons[1].hasDestructiveAction,\n"
        "      alert.buttons[2].hasDestructiveAction else { exit(1) }\n"
    )
    executable = tmp_path / "quit-buttons"
    subprocess.run(["/usr/bin/swiftc", str(harness), "-o", str(executable)], check=True, timeout=60)
    result = subprocess.run([str(executable)], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.skipif(sys.platform != "darwin", reason="requires macOS Foundation and swiftc")
@pytest.mark.parametrize("existing", [False, True], ids=["missing-log", "existing-log"])
def test_native_log_retains_output_across_reopen(tmp_path: Path, existing: bool) -> None:
    # Given the current production logging seam and an isolated log directory.
    source = (Path(__file__).resolve().parents[2] / "desktop/macos/App.swift").read_text()
    start = source.index('            let logURL = data.appendingPathComponent("app.log")')
    end = source.index("            let process = Process()", start)
    harness = tmp_path / "logging.swift"
    harness.write_text(
        "import Foundation\n"
        "let data = URL(fileURLWithPath: CommandLine.arguments[1], isDirectory: true)\n"
        "var log: FileHandle?\n" + source[start:end] + "\n"
        "let process = Process()\n"
        'process.executableURL = URL(fileURLWithPath: "/bin/sh")\n'
        'process.arguments = ["-c", "printf \'stdout-marker\\n\'; printf \'stderr-marker\\n\' >&2"]\n'
        "process.standardOutput = log\nprocess.standardError = log\n"
        "try process.run()\nprocess.waitUntilExit()\n"
        "try log?.close()\nexit(process.terminationStatus)\n"
    )
    executable = tmp_path / "logging"
    subprocess.run(["/usr/bin/swiftc", str(harness), "-o", str(executable)], check=True, timeout=60)
    log_path = tmp_path / "app.log"
    previous = b"previous-failure-marker\n" if existing else b""
    if existing:
        log_path.write_bytes(previous)

    # When the native logging seam is opened, written by a child, closed and reopened.
    subprocess.run([str(executable), str(tmp_path)], check=True, timeout=10)
    subprocess.run([str(executable), str(tmp_path)], check=True, timeout=10)

    # Then both streams from both launches follow the original bytes exactly.
    assert log_path.read_bytes() == previous + b"stdout-marker\nstderr-marker\n" * 2


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
