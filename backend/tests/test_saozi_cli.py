import json

from app.arctime import cli


def test_local_saozi_cli_uses_config_and_preserves_input(tmp_path, monkeypatch):
    (tmp_path / "config.json").write_text(json.dumps({"deepseek_api_key":"test-key"}))
    source = tmp_path / "input.mp4"
    source.write_bytes(b"original")
    captured = {}
    def create(*args, **kwargs):
        captured.update(kwargs)
        return tmp_path
    monkeypatch.setattr(cli.workflow,"create_run",create)
    monkeypatch.setattr(cli.workflow,"resume_run",lambda *args,**kwargs:{"state":"completed","completed_clips":[]})
    assert cli.main(["run",str(source),"--saozi","--local","--output-dir",str(tmp_path)]) == 0
    assert captured["local_source"] == source
    assert captured["saozi"] is True
    assert source.read_bytes() == b"original"


def test_saozi_cli_missing_key_does_not_import_or_download(tmp_path, monkeypatch):
    monkeypatch.setattr(cli.workflow,"create_run",lambda *args,**kwargs: (_ for _ in ()).throw(AssertionError("must not download")))
    assert cli.main(["run","https://example.org/video","--saozi","--output-dir",str(tmp_path)]) == 1


def test_live_requires_saozi_before_work(tmp_path):
    assert cli.main(["run","https://live.bilibili.com/12345","--highlights","2","--live","--output-dir",str(tmp_path)]) == 1


def test_live_translation_failure_does_not_abort_capture(tmp_path, monkeypatch):
    from app.arctime import saozi_live, saozi_translation
    (tmp_path / "config.json").write_text(json.dumps({"deepseek_api_key":"test-key"}))
    completed = []
    def fail(*args, **kwargs):
        raise ValueError("provider unavailable")
    def capture(directory, *args, bilingual, **kwargs):
        bilingual(directory, False)
        completed.append("recording continued")
        bilingual(directory, True)
        return {"saozi":True,"state":"completed","completed_clips":[]}
    monkeypatch.setattr(saozi_translation, "translate", fail)
    monkeypatch.setattr(saozi_live, "run_live", capture)
    assert cli.main(["run","https://live.bilibili.com/12345","--saozi","--live","--output-dir",str(tmp_path)]) == 1
    assert completed == ["recording continued"]
