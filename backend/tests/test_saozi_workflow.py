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
    asr.transcribe = lambda *args, **kwargs: []
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
    def silent(*args, **kwargs):
        raise ValueError("No speech was recognized; check the source audio and language")
    asr.transcribe = silent
    directory = workflow.create_run("https://example.org/replay", tmp_path, [], None, asr, saozi=True)
    assert workflow.resume_run(directory, asr, selector=Selector())["state"] == "completed"
