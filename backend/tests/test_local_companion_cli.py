import json
import sys

import pytest

from app.arctime import cli


def test_run_parses_repeated_clock_ranges_and_local_options(tmp_path, monkeypatch, capsys):
    captured = {}

    def create(url, root, ranges, count, adapter):
        captured.update(url=url, root=root, ranges=ranges, count=count, adapter=adapter)
        return tmp_path

    monkeypatch.setattr(cli.workflow, "create_run", create)
    monkeypatch.setattr(cli.workflow, "resume_run", lambda *a, **kw: {"state": "completed", "completed_clips": [{}]})
    assert cli.main(["run", "https://example.com/v.mp4", "--range", "01:02", "01:05", "--range", "80", "90",
                     "--model", str(tmp_path / "model.bin"), "--language", "zh"]) == 0
    assert captured["ranges"] == [(62, 65), (80, 90)]
    assert captured["count"] is None
    assert captured["adapter"].language == "zh"
    assert json.loads(capsys.readouterr().out)["clip_count"] == 1


def test_resume_preserves_recorded_asr_configuration(tmp_path, monkeypatch):
    captured = {}

    def resume(directory, **kwargs):
        captured["directory"] = directory
        return {"state": "completed", "completed_clips": []}

    monkeypatch.setattr(cli.workflow, "resume_run", resume)
    assert cli.main(["resume", str(tmp_path)]) == 0
    assert captured["directory"] == tmp_path


def test_highlights_are_mutually_exclusive_with_ranges():
    with pytest.raises(SystemExit) as result:
        cli.main(["run", "https://example.com/v.mp4", "--range", "1", "3", "--highlights", "2"])
    assert result.value.code == 2


def test_invalid_time_does_not_download(monkeypatch):
    monkeypatch.setattr(cli.workflow, "create_run", lambda *a: pytest.fail("download started"))
    assert cli.main(["run", "https://example.com/v.mp4", "--range", "nan", "3"]) == 1


def test_failed_run_prints_recovery_directory(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(cli.workflow, "create_run", lambda *a: tmp_path)
    monkeypatch.setattr(cli.workflow, "resume_run", lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("Local ASR failed")))
    assert cli.main(["run", "https://example.com/v.mp4", "--highlights", "2"]) == 1
    output = capsys.readouterr()
    assert str(tmp_path) in output.err
    assert "example.com" not in output.err


def test_missing_dependency_doctor_returns_nonzero(monkeypatch, capsys):
    monkeypatch.setattr(cli.media, "tool_path", lambda name: (_ for _ in ()).throw(FileNotFoundError("missing")))
    assert cli.main(["doctor"]) == 1
    assert json.loads(capsys.readouterr().out)["ready"] is False


def test_doctor_checks_python_export_dependencies(monkeypatch, capsys):
    monkeypatch.setattr(cli.media, "tool_path", lambda name: name)
    monkeypatch.setattr(cli.LocalASR, "identity", lambda self: {})
    monkeypatch.setattr(cli.importlib, "import_module", lambda name: (_ for _ in ()).throw(ImportError("missing anyio")))
    assert cli.main(["doctor"]) == 1
    assert json.loads(capsys.readouterr().out)["checks"]["python"]["ready"] is False


def test_missing_python_dependency_is_reported_without_traceback(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(cli.workflow, "create_run", lambda *a: tmp_path)
    monkeypatch.setattr(cli.workflow, "resume_run", lambda *a, **kw: (_ for _ in ()).throw(ImportError("missing anyio")))
    assert cli.main(["run", "https://example.com/v.mp4", "--highlights", "2"]) == 1
    assert "Traceback" not in capsys.readouterr().err


def test_local_entrypoint_does_not_import_desktop():
    import subprocess
    result = subprocess.run([sys.executable, "-c",
                             "import sys; from app.arctime import cli; assert 'app.arctime.desktop' not in sys.modules"],
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
