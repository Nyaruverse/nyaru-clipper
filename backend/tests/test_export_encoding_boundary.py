from __future__ import annotations

import subprocess
import sys
import json
from dataclasses import FrozenInstanceError, fields
from pathlib import Path

import pytest


def test_encoding_import_is_independent_of_database_and_settings() -> None:
    script = """
import importlib.abc
import sys

blocked = ('sqlmodel', 'sqlalchemy', 'app.models', 'app.db',
           'app.services.workstation_events', 'app.services.pipeline_support',
           'app.settings', 'pydantic_settings')
class BlockDatabaseImports(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if any(fullname == name or fullname.startswith(name + '.') for name in blocked):
            raise ImportError('Forbidden encoding dependency: ' + fullname)
sys.meta_path.insert(0, BlockDatabaseImports())
from app.services.export_encoding import ExportInvocation, execute_video_export
assert callable(execute_video_export)
assert not any(name in sys.modules for name in blocked)
print('encoding import has no database or settings dependencies')
"""
    result = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, check=False,
        cwd=Path(__file__).resolve().parents[1],
    )
    assert result.returncode == 0, result.stderr
    assert "no database or settings dependencies" in result.stdout


def test_companion_export_does_not_mutate_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.arctime import media
    from app.services import export_encoding
    from app.settings import Settings

    settings = Settings(ffmpeg_binary="configured-ffmpeg")
    before = settings.model_dump()
    monkeypatch.setattr("app.settings.get_settings", lambda: settings)
    monkeypatch.setattr(media, "probe_video", lambda path: 10)
    monkeypatch.setattr(media, "tool_path", lambda name: "bundled-ffmpeg")

    def encode(invocation, config, log_path):
        assert isinstance(config, export_encoding.ExportEncodingConfig)
        assert config.ffmpeg_binary == "bundled-ffmpeg"
        assert config.export_video_backend == settings.export_video_backend
        assert config.windows_ffmpeg_binary == settings.windows_ffmpeg_binary
        invocation.output_path.write_bytes(b"encoded video")
        return export_encoding.ExportExecution("cpu", "libx264", subprocess.CompletedProcess([], 0))

    monkeypatch.setattr(export_encoding, "execute_video_export", encode)
    target = tmp_path / "clip.mp4"
    media.export_clip(tmp_path / "source.mp4", target, 0, 10, [])
    assert target.read_bytes() == b"encoded video"
    assert settings.model_dump() == before


def test_encoding_config_is_frozen_and_narrow() -> None:
    from app.services.export_encoding import ExportEncodingConfig

    config = ExportEncodingConfig(ffmpeg_binary="ffmpeg")
    assert [field.name for field in fields(config)] == [
        "ffmpeg_binary", "export_video_backend", "windows_ffmpeg_binary",
    ]
    with pytest.raises(FrozenInstanceError):
        setattr(config, "ffmpeg_binary", "other-ffmpeg")


@pytest.mark.parametrize("redact_output", [False, True])
def test_command_logging_preserves_redaction_contract(tmp_path: Path, redact_output: bool) -> None:
    from app.services.command_logging import run_logged_command

    secret = r"C:\private\secret source.mp4"
    reference = "managed-video"
    payload = {secret: [secret, {"source": secret}, 4, None]}
    script = "import json,sys; s=sys.argv[1]; print(json.dumps({s:[s,{'source':s},4,None]})); print(s,file=sys.stderr); sys.exit(7)"
    log_path = tmp_path / "logs" / "export.log"
    result = run_logged_command(
        [sys.executable, "-c", script, secret],
        log_path=log_path, redactions={secret: reference}, redact_output=redact_output,
    )
    assert result.returncode == 7
    log = log_path.read_text()
    assert secret not in log
    assert "exit_code=7" in log
    if redact_output:
        assert json.loads(result.stdout) == {reference: [reference, {"source": reference}, 4, None]}
        assert result.stderr == reference + "\n"
        assert json.dumps(secret)[1:-1] not in log
    else:
        assert json.loads(result.stdout) == payload
        assert result.stderr == secret + "\n"


def test_pipeline_support_reexports_one_logging_implementation() -> None:
    from app.services import command_logging, pipeline_support

    assert pipeline_support.run_logged_command is command_logging.run_logged_command
    assert pipeline_support.append_stage_log is command_logging.append_stage_log


@pytest.mark.parametrize("conversion_failure", ["launch", "exit", "empty"])
def test_amf_path_failure_preserves_cpu_command(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, conversion_failure: str,
) -> None:
    from app.services import export_encoding

    invocation = export_encoding.ExportInvocation(tmp_path / "source.mp4", tmp_path / "clip.mp4", 1.25, 4.5, "source-ref")
    commands: list[list[str]] = []

    def run(args: list[str], **kwargs) -> subprocess.CompletedProcess[str]:
        commands.append(args)
        if args[0] == "wslpath":
            if conversion_failure == "launch":
                raise FileNotFoundError("wslpath")
            return subprocess.CompletedProcess(args, 1 if conversion_failure == "exit" else 0, "", "path failure")
        return subprocess.CompletedProcess(args, 0, str(invocation.source_path), str(invocation.source_path))

    monkeypatch.setattr(subprocess, "run", run)
    config = export_encoding.ExportEncodingConfig("cpu-ffmpeg", "windows-amf", Path("windows-ffmpeg.exe"))
    log_path = tmp_path / "export.log"
    result = export_encoding.execute_video_export(invocation, config, log_path)
    assert result.export_backend == "cpu"
    assert commands == [
        ["wslpath", "-w", str(invocation.source_path)],
        ["cpu-ffmpeg", "-y", "-ss", "1.250", "-to", "4.500", "-i", str(invocation.source_path),
         "-c:v", "libx264", "-c:a", "aac", str(invocation.output_path)],
    ]
    log = log_path.read_text()
    assert "reason=wslpath_failed" in log
    assert str(invocation.source_path) not in log
    assert "source-ref" in log


def test_amf_missing_output_falls_back_to_cpu(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.services import export_encoding

    invocation = export_encoding.ExportInvocation(tmp_path / "source.mp4", tmp_path / "clip.mp4", 0, 1, "source-ref")
    commands: list[list[str]] = []
    monkeypatch.setattr(export_encoding, "_convert_wsl_path", lambda path: "windows-" + path.name)

    def run(args: list[str], **kwargs) -> subprocess.CompletedProcess[str]:
        commands.append(args)
        if "libx264" in args:
            invocation.output_path.write_bytes(b"cpu-output")
        return subprocess.CompletedProcess(args, 0, "", "")

    monkeypatch.setattr(export_encoding, "run_logged_command", run)
    config = export_encoding.ExportEncodingConfig("cpu-ffmpeg", "windows-amf", Path("windows-ffmpeg.exe"))
    log_path = tmp_path / "export.log"
    result = export_encoding.execute_video_export(invocation, config, log_path)
    assert result.export_backend == "cpu"
    assert [command[command.index("-c:v") + 1] for command in commands] == ["h264_amf", "libx264"]
    assert invocation.output_path.read_bytes() == b"cpu-output"
    assert "reason=amf_output_missing" in log_path.read_text()
