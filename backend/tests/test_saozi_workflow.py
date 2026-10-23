import hashlib
import json

import pytest

from app.arctime import workflow
from test_arctime_workflow import FakeASR, fake_media


class Selector:
    model = "deepseek-flash"

    def plan(self, directory, cues, duration, progress=None):
        return [{"start": 0.0, "end": duration, "score": None,
                 "reasons": ["尾段"], "title": "完整片段"}]


def test_local_saozi_preserves_original_and_recovers_without_recognition(tmp_path, fake_media):
    source = tmp_path / "original.mp4"
    source.write_bytes(b"original")
    asr = FakeASR()
    directory = workflow.create_run("", tmp_path / "runs", [], None, asr,
                                    saozi=True, local_source=source)
    job = workflow.resume_run(directory, asr, selector=Selector())
    assert source.read_bytes() == b"original"
    assert job["selection"][0]["start"] == 0
    assert job["selection"][0]["end"] == 10
    assert workflow.resume_run(directory, asr, selector=Selector())["state"] == "completed"
    assert asr.calls == 1


def test_saozi_silence_retains_video_without_inventing_subtitles(tmp_path, fake_media):
    asr = FakeASR()
    asr.transcribe = lambda *args: []
    directory = workflow.create_run("https://example.org/replay", tmp_path, [], None, asr, saozi=True)
    job = workflow.resume_run(directory, asr, selector=Selector())
    assert len(job["completed_clips"]) == 1
    assert (directory / "subtitles.srt").read_text() == ""


def test_saozi_requires_selector_before_export(tmp_path, fake_media):
    asr = FakeASR()
    directory = workflow.create_run("https://example.org/replay", tmp_path, [], None, asr, saozi=True)
    with pytest.raises(ValueError, match="配置"):
        workflow.resume_run(directory, asr)


def test_real_asr_empty_speech_exception_preserves_silent_video(tmp_path, fake_media):
    asr = FakeASR()
    def silent(*args):
        raise ValueError("No speech was recognized; check the source audio and language")
    asr.transcribe = silent
    directory = workflow.create_run("https://example.org/replay", tmp_path, [], None, asr, saozi=True)
    assert workflow.resume_run(directory, asr, selector=Selector())["state"] == "completed"


@pytest.mark.parametrize("filename", ["original.mp4", ".saozi-upload-lookalike"])
def test_real_cli_local_call_keeps_original_and_copies_once(tmp_path, fake_media, monkeypatch, record_property, filename):
    from app.arctime import cli, translation
    (tmp_path / "config.json").write_text(json.dumps({"deepseek_api_key": "synthetic-test-key"}))
    source = tmp_path / filename
    payload = b"external-original" * 4096
    source.write_bytes(payload)
    inode = source.stat().st_ino
    copies = []
    copyfile = workflow.shutil.copyfile

    def capture_copy(original, target, *args, **kwargs):
        copies.append((original, target))
        return copyfile(original, target, *args, **kwargs)

    monkeypatch.setattr(workflow.shutil, "copyfile", capture_copy)
    monkeypatch.setattr(cli, "LocalASR", lambda *args: FakeASR())
    monkeypatch.setattr(translation, "_request", lambda client, key, cues, start, model, **kwargs:
                        [{"id": start + index + 1, "zh": "字幕译文"} for index, cue in enumerate(cues)])
    assert cli.main(["run", str(source), "--saozi", "--local", "--language", "zh",
                     "--output-dir", str(tmp_path)]) == 0
    directory = next(tmp_path.glob("*/job.json")).parent
    saved = json.loads((directory / "job.json").read_text())
    assert saved["state"] == "completed"
    assert source.read_bytes() == (directory / "source.mp4").read_bytes() == payload
    assert source.stat().st_ino == inode
    assert (directory / "source.mp4").stat().st_ino != inode
    assert copies == [(source, directory / "source.mp4")]
    assert saved["video_sha256"] == hashlib.sha256(payload).hexdigest()
    record_property("external_copy", json.dumps({"original_sha256": saved["video_sha256"],
                                                 "original_inode_retained": True, "copy_count": len(copies)}))
