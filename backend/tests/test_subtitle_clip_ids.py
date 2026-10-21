import json
from collections.abc import Callable
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.arctime import media, subtitle_exports
from app.arctime.companion_manager import JobManager
from app.arctime.subtitle_exports import SubtitleExports, read_exports
from test_subtitle_api import finished as finished, payload, wait_export


@pytest.fixture
def numbered_clips(finished: tuple[TestClient, Path], monkeypatch: pytest.MonkeyPatch) -> tuple[TestClient, Path]:
    client, directory = finished
    job = json.loads((directory / "job.json").read_bytes())
    job["completed_clips"] = []
    job["selection"] = job["selection"] * 2
    for index in (999, 1000):
        video = directory / f"clip-{index:03d}.mp4"
        subtitle = video.with_suffix(".srt")
        video.write_bytes((directory / "clip-001.mp4").read_bytes())
        subtitle.write_bytes((directory / "clip-001.srt").read_bytes())
        job["completed_clips"].append({
            "video": video.name, "subtitles": subtitle.name,
            "video_sha256": media.fingerprint(video),
            "subtitles_sha256": media.fingerprint(subtitle),
        })
    media.write_json(directory / "job.json", job)
    monkeypatch.setattr(subtitle_exports, "video_dimensions", lambda path: (640, 360))
    return client, directory


@pytest.mark.parametrize("index", [999, 1000])
def test_manual_http_exports_numbered_clip(numbered_clips: tuple[TestClient, Path], index: int) -> None:
    # Given a completed clip using the generator's minimum-width numbering.
    client, directory = numbered_clips
    video = f"clip-{index:03d}.mp4"
    request = payload(client, video=video)

    # When the real HTTP export route handles the request.
    response = client.post("/companion-api/jobs/abcdef123456/subtitle-export", json=request)

    # Then the registered ASS is readable through the download route and on disk.
    assert response.status_code == 202, response.text
    result = wait_export(client)
    assert result["active"]["state"] == "completed", result
    output, = result["outputs"]
    assert output["video"] == video and output["kind"] == "ass"
    product = directory / output["filename"]
    assert media.fingerprint(product) == output["sha256"]
    download = client.get(f"/companion-api/jobs/abcdef123456/files/{product.name}?download=true")
    assert download.status_code == 200
    assert download.content == product.read_bytes()
    assert "Dialogue:" in download.text and "こんにちは" in download.text


@pytest.mark.parametrize("index", [999, 1000])
def test_automatic_live_exports_numbered_clip(
    numbered_clips: tuple[TestClient, Path], monkeypatch: pytest.MonkeyPatch, index: int,
) -> None:
    # Given a completed clip in an ongoing recording, with only encoding faked.
    client, directory = numbered_clips
    job = json.loads((directory / "job.json").read_bytes())
    video = f"clip-{index:03d}.mp4"
    job.update(state="recording", live=True)
    job["completed_clips"] = [clip for clip in job["completed_clips"] if clip["video"] == video]
    job["subtitle_template"] = client.get("/companion-api/subtitle-settings").json()["templates"][0]
    media.write_json(directory / "job.json", job)
    encoded: list[str] = []

    def encode(source: Path, working: Path, duration: float, notify: Callable[[str], None]) -> Path:
        assert source.name == video and duration > 0
        content = (working / "subtitle.ass").read_text(encoding="utf-8")
        assert "Dialogue:" in content and "こんにちは" in content
        encoded.append(source.name)
        product = working / "burn.mp4"
        product.write_bytes(b"encoded test boundary")
        return product

    monkeypatch.setattr(subtitle_exports, "burn_clip", encode)
    manager = JobManager(directory.parent, directory / "unused-model", 1)
    try:
        # When the real automatic export entry point runs both output kinds.
        SubtitleExports(manager).export_live(directory, job)
    finally:
        manager.executor.shutdown(wait=True)
        manager.chatgpt.close()

    # Then both products are registered and the real ASS contains the clip cues.
    result = read_exports(directory)
    assert result.active is not None and result.active.state == "completed", job
    assert "subtitle_style_error" not in job
    assert {(output.video, output.kind) for output in result.outputs} == {(video, "ass"), (video, "burn")}
    assert encoded == [video]
    for output in result.outputs:
        product = directory / output.filename
        assert media.fingerprint(product) == output.sha256
        if output.kind == "ass":
            content = product.read_text(encoding="utf-8")
            assert "Dialogue:" in content and "こんにちは" in content


@pytest.mark.parametrize("video", [
    "clip-99.mp4", "clip-100a.mp4", "clip--1000.mp4", "clip-1000.mp4.bak",
    "../clip-1000.mp4", "other/clip-1000.mp4", "/tmp/clip-1000.mp4", "clip-1000\\.mp4",
])
def test_http_rejects_invalid_clip_names(numbered_clips: tuple[TestClient, Path], video: str) -> None:
    # Given a request with an invalid filename or path.
    client, directory = numbered_clips
    request = payload(client, video=video)
    # When the HTTP boundary parses it.
    response = client.post("/companion-api/jobs/abcdef123456/subtitle-export", json=request)
    # Then no export is accepted or published.
    assert response.status_code == 422, response.text
    assert not list(directory.glob("styled-*"))


def test_http_rejects_unfinished_task(numbered_clips: tuple[TestClient, Path]) -> None:
    # Given a valid completed clip belonging to a task that is still running.
    client, directory = numbered_clips
    job = json.loads((directory / "job.json").read_bytes())
    job["state"] = "recording"
    media.write_json(directory / "job.json", job)
    # When a manual export is requested.
    response = client.post("/companion-api/jobs/abcdef123456/subtitle-export", json=payload(client, video="clip-1000.mp4"))
    # Then the completion guard remains enforced.
    assert response.status_code == 409 and "完成" in response.text
    assert not list(directory.glob("styled-*"))


@pytest.mark.parametrize("outside", [False, True])
def test_http_rejects_clip_outside_completed_membership(numbered_clips: tuple[TestClient, Path], outside: bool) -> None:
    # Given an existing clip that is either unregistered here or belongs elsewhere.
    client, directory = numbered_clips
    target = directory.parent / "123456abcdef" if outside else directory
    target.mkdir(exist_ok=True)
    (target / "clip-1001.mp4").write_bytes((directory / "clip-1000.mp4").read_bytes())
    # When the current task is asked to export that filename.
    response = client.post("/companion-api/jobs/abcdef123456/subtitle-export", json=payload(client, video="clip-1001.mp4"))
    # Then a four-digit filename alone cannot establish task membership.
    assert response.status_code == 409 and "已完成切片" in response.text
    assert not list(directory.glob("styled-*"))


@pytest.mark.parametrize("extension", ["mp4", "srt"])
def test_http_rejects_changed_clip_hash(numbered_clips: tuple[TestClient, Path], extension: str) -> None:
    # Given a registered four-digit clip whose source or subtitles were changed.
    client, directory = numbered_clips
    (directory / f"clip-1000.{extension}").write_bytes(b"tampered")
    # When the normal export route validates its inputs.
    response = client.post("/companion-api/jobs/abcdef123456/subtitle-export", json=payload(client, video="clip-1000.mp4"))
    # Then integrity rejection still happens before publication.
    assert response.status_code == 409 and "已改变" in response.text
    assert not list(directory.glob("styled-*"))
