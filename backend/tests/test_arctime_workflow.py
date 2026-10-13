import json

import pytest

from app.arctime import workflow
from app.services.subtitles import SubtitleSegment, render_srt


class FakeASR:
    def __init__(self):
        self.calls = 0
        self.failure = False

    def identity(self):
        return {"engine": "local-test", "model_sha256": "test"}

    def transcribe(self, video, directory, duration):
        self.calls += 1
        if self.failure:
            raise RuntimeError("local engine failed")
        return [SubtitleSegment("1", 1, 3, "哈哈！太强了！哈哈！")]


@pytest.fixture
def fake_media(monkeypatch):
    def download(url, directory):
        path = directory / "source.mp4"
        path.write_bytes(b"source")
        return path

    def export(source, target, start, end, segments):
        target.write_bytes(b"export")
        target.with_suffix(".srt").write_text(render_srt(workflow.media.clip_subtitles(segments, start, end)))

    monkeypatch.setattr(workflow.media, "download_video", download)
    monkeypatch.setattr(workflow.media, "probe_video", lambda p: 10.0)
    monkeypatch.setattr(workflow.media, "export_clip", export)


def new_run(tmp_path, asr, ranges=None, highlights=None):
    return workflow.create_run("https://example.com/v.mp4", tmp_path, [(1, 4)] if ranges is None else ranges, highlights, asr)


def test_complete_local_run_resume_does_not_retranscribe(tmp_path, fake_media):
    asr = FakeASR()
    directory = new_run(tmp_path, asr)
    result = workflow.resume_run(directory, asr)
    assert result["state"] == "completed"
    assert result["version"] == 2
    assert len(result["completed_clips"]) == 1
    assert asr.calls == 1
    assert "example.com" not in (directory / "job.json").read_text()
    assert (directory / "transcript.txt").read_text().strip() == "哈哈！太强了！哈哈！"
    assert json.loads((directory / "transcript.json").read_text())["segments"][0]["start_seconds"] == 1
    assert workflow.resume_run(directory, asr)["state"] == "completed"
    assert asr.calls == 1


def test_failed_local_recognition_can_retry(tmp_path, fake_media):
    asr = FakeASR()
    directory = new_run(tmp_path, asr)
    asr.failure = True
    with pytest.raises(RuntimeError):
        workflow.resume_run(directory, asr)
    assert json.loads((directory / "job.json").read_text())["state"] == "transcribing"
    asr.failure = False
    assert workflow.resume_run(directory, asr)["state"] == "completed"
    assert asr.calls == 2


def test_changed_video_is_rejected_before_asr(tmp_path, fake_media):
    asr = FakeASR()
    directory = new_run(tmp_path, asr)
    job = json.loads((directory / "job.json").read_text())
    (directory / job["video"]).write_bytes(b"different")
    with pytest.raises(ValueError, match="changed"):
        workflow.resume_run(directory, asr)
    assert asr.calls == 0


def test_changed_model_is_rejected_before_asr(tmp_path, fake_media):
    asr = FakeASR()
    directory = new_run(tmp_path, asr)
    asr.identity = lambda: {"engine": "local-test", "model_sha256": "changed"}
    with pytest.raises(ValueError, match="configuration changed"):
        workflow.resume_run(directory, asr)
    assert asr.calls == 0


def test_invalid_ranges_are_rejected_before_asr(tmp_path, fake_media):
    asr = FakeASR()
    with pytest.raises(ValueError):
        new_run(tmp_path, asr, ranges=[(0, 11)])
    assert asr.calls == 0


def test_lock_excludes_concurrent_runs(tmp_path):
    with workflow.exclusive_lock(tmp_path / "lock"):
        with pytest.raises(RuntimeError, match="busy"):
            with workflow.exclusive_lock(tmp_path / "lock"):
                pytest.fail("second lock acquired")


def test_manifest_path_traversal_is_rejected(tmp_path, fake_media):
    asr = FakeASR()
    directory = new_run(tmp_path, asr)
    job = json.loads((directory / "job.json").read_text())
    job["video"] = "../../outside.mp4"
    workflow.write_manifest(directory, job)
    with pytest.raises(ValueError, match="path"):
        workflow.resume_run(directory, asr)


def test_subtitle_source_beyond_video_is_rejected(tmp_path, fake_media):
    asr = FakeASR()
    directory = new_run(tmp_path, asr)
    asr.transcribe = lambda *args: [SubtitleSegment("1", 1, 15, "wrong video")]
    with pytest.raises(ValueError, match="duration"):
        workflow.resume_run(directory, asr)


def test_partial_export_resume_preserves_completed_clips(tmp_path, fake_media, monkeypatch):
    asr = FakeASR()
    directory = new_run(tmp_path, asr, ranges=[(1, 4), (5, 8)])
    export = workflow.media.export_clip
    calls = []

    def fail_second(source, target, start, end, segments):
        calls.append(start)
        if start == 5:
            raise RuntimeError("failed second export")
        export(source, target, start, end, segments)

    monkeypatch.setattr(workflow.media, "export_clip", fail_second)
    with pytest.raises(RuntimeError):
        workflow.resume_run(directory, asr)
    assert len(json.loads((directory / "job.json").read_text())["completed_clips"]) == 1
    monkeypatch.setattr(workflow.media, "export_clip", export)
    assert workflow.resume_run(directory, asr)["state"] == "completed"
    assert calls == [1, 5]
    assert asr.calls == 1


def test_old_cloud_job_is_rejected_without_loading_desktop(tmp_path):
    workflow.write_manifest(tmp_path, {"version": 1, "state": "submission_pending"})
    with pytest.raises(ValueError, match="cloud"):
        workflow.resume_run(tmp_path, FakeASR())


def test_highlights_use_local_transcript(tmp_path, fake_media):
    asr = FakeASR()
    directory = new_run(tmp_path, asr, ranges=[], highlights=2)
    job = workflow.resume_run(directory, asr)
    assert len(job["completed_clips"]) == 1
    assert job["selection"][0]["score"] >= .55


def test_crash_after_export_recovers_existing_pair(tmp_path, fake_media, monkeypatch):
    asr = FakeASR()
    directory = new_run(tmp_path, asr, ranges=[(0, 10)])
    write = workflow.write_manifest

    def fail_checkpoint(directory, job):
        if job["state"] == "exporting" and job["completed_clips"]:
            raise OSError("checkpoint interrupted")
        write(directory, job)

    monkeypatch.setattr(workflow, "write_manifest", fail_checkpoint)
    with pytest.raises(OSError):
        workflow.resume_run(directory, asr)
    existing = (directory / "clip-001.mp4").read_bytes()
    monkeypatch.setattr(workflow, "write_manifest", write)
    assert workflow.resume_run(directory, asr)["state"] == "completed"
    assert (directory / "clip-001.mp4").read_bytes() == existing


def test_tampered_transcript_is_rejected(tmp_path, fake_media):
    asr = FakeASR()
    directory = new_run(tmp_path, asr)
    workflow.resume_run(directory, asr)
    (directory / "subtitles.srt").write_text("tampered")
    with pytest.raises(ValueError, match="changed"):
        workflow.resume_run(directory, asr)


def test_resume_recovers_subtitle_only_publication_gap(tmp_path, fake_media, monkeypatch):
    asr = FakeASR()
    directory = new_run(tmp_path, asr, ranges=[(0, 10)])
    export = workflow.media.export_clip

    def interrupted(source, target, start, end, segments):
        target.with_suffix(".srt").write_text(render_srt(workflow.media.clip_subtitles(segments, start, end)))
        raise RuntimeError("interrupted before video publication")

    monkeypatch.setattr(workflow.media, "export_clip", interrupted)
    with pytest.raises(RuntimeError):
        workflow.resume_run(directory, asr)
    monkeypatch.setattr(workflow.media, "export_clip", export)
    assert workflow.resume_run(directory, asr)["state"] == "completed"
    assert asr.calls == 1
