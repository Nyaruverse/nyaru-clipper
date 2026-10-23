from __future__ import annotations

import json
import subprocess

import pytest

from app.services.highlight_scoring import SceneWindow, score_candidate_windows


@pytest.fixture()
def highlight_input(tmp_path, monkeypatch):
    from app.db import init_db, reset_db_runtime, session_scope
    from app.repositories.tasks import create_task
    from app.services.storage import ensure_task_dirs

    monkeypatch.setenv("APP_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("APP_DATABASE_URL", f"sqlite:///{tmp_path / 'state.sqlite3'}")
    reset_db_runtime()
    init_db()
    with session_scope() as session:
        task, _ = create_task(session, "https://www.bilibili.com/video/BV1hs411c7mW")
    task_id = task["task_id"]
    directories = ensure_task_dirs(task_id)
    (directories["raw"] / "source.mp4").write_bytes(b"current-source")
    (directories["work"] / "subtitles.zh-ja.json").write_text(json.dumps({"segments": [{
        "id": "seg-1", "start_seconds": 10, "end_seconds": 20,
        "text": "不会吧！！太强了！！哈哈哈哈！！太神了太神了！！" * 2,
    }]}), encoding="utf-8")
    (directories["work"] / "media-probe.json").write_text(
        json.dumps({"format": {"duration": "20"}}), encoding="utf-8",
    )
    yield task_id, directories
    reset_db_runtime()


def _analyze(task_id: str):
    from app.db import session_scope
    from app.services.highlights import analyze_task_highlights

    with session_scope() as session:
        return analyze_task_highlights(
            session, task_id, scene_windows=[SceneWindow("scene-1", 10, 30)],
        )


@pytest.mark.parametrize("duration", [None, 0, -1, float("nan"), float("inf"), True])
def test_unknown_duration_retains_scene_range_without_inventing_media_end(duration):
    candidates = score_candidate_windows(
        [SceneWindow("scene-1", 10, 30)], [], media_end_s=duration, min_score=0,
    )

    assert candidates[0]["default_range"] == {"start_s": 10, "end_s": 30}
    assert candidates[0]["source_signals"]["media_end_s"] is None


@pytest.mark.parametrize("duration, expected_end", [(60, 32), (31, 31)])
def test_known_duration_pads_empty_subtitle_scene_and_clamps_to_source(duration, expected_end):
    candidates = score_candidate_windows(
        [SceneWindow("scene-1", 10, 30)], [], media_end_s=duration, min_score=0,
    )

    assert candidates[0]["default_range"] == {"start_s": 8, "end_s": expected_end}
    assert candidates[0]["source_signals"]["media_end_s"] == duration


def test_scene_after_known_media_end_is_not_an_export_candidate():
    candidates = score_candidate_windows(
        [SceneWindow("scene-1", 10, 30)], [], media_end_s=5, min_score=0,
    )

    assert candidates == []


def test_silent_tail_uses_current_probe_and_serves_same_default_range(highlight_input, monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import app

    task_id, directories = highlight_input
    monkeypatch.setattr(
        "app.services.media_prep.run_logged_command",
        lambda *args, **kwargs: subprocess.CompletedProcess(args, 0, '{"format":{"duration":"60"}}', ""),
    )

    result = _analyze(task_id)

    candidate = result.candidates[0]
    assert candidate["default_range"] == {"start_s": 8, "end_s": 32}
    assert candidate["source_signals"]["media_end_s"] == 60
    with TestClient(app) as client:
        artifacts = client.get(f"/api/tasks/{task_id}/artifacts").json()
        artifact = next(item for item in artifacts if item["kind"] == "highlight_candidates_json")
        response = client.get(artifact["path"])
    assert response.status_code == 200
    assert response.json()["candidates"][0]["default_range"] == {"start_s": 8, "end_s": 32}


@pytest.mark.parametrize("probe_output", [
    '{}', '[]', '{"format":{"duration":null}}', '{"format":{"duration":true}}',
    '{"format":{"duration":"nan"}}', '{"format":{"duration":"inf"}}',
    '{"format":{"duration":"-1"}}', '{"format":{"duration":"0"}}', 'invalid json',
])
def test_invalid_probe_cannot_turn_subtitle_or_scene_end_into_duration(highlight_input, monkeypatch, probe_output):
    monkeypatch.setattr(
        "app.services.media_prep.run_logged_command",
        lambda *args, **kwargs: subprocess.CompletedProcess(args, 0, probe_output, ""),
    )

    result = _analyze(highlight_input[0])

    assert result.candidates[0]["default_range"] == {"start_s": 10, "end_s": 30}
    assert result.candidates[0]["source_signals"]["media_end_s"] is None


@pytest.mark.parametrize("failure", ["source_missing", "probe_missing", "probe_failed"])
def test_unavailable_source_duration_is_explicit(highlight_input, monkeypatch, failure):
    task_id, directories = highlight_input
    if failure == "source_missing":
        (directories["raw"] / "source.mp4").unlink()

    def probe(*args, **kwargs):
        if failure == "probe_missing":
            raise FileNotFoundError("ffprobe")
        return subprocess.CompletedProcess(args, 1, "", "invalid media")

    monkeypatch.setattr("app.services.media_prep.run_logged_command", probe)

    result = _analyze(task_id)

    assert result.candidates[0]["default_range"] == {"start_s": 10, "end_s": 30}
    assert result.candidates[0]["source_signals"]["media_end_s"] is None


def test_empty_transcript_is_success_without_candidates(highlight_input):
    task_id, directories = highlight_input
    (directories["work"] / "subtitles.zh-ja.json").write_text('{"segments":[]}', encoding="utf-8")

    result = _analyze(task_id)

    assert result.candidates == []
    assert result.no_candidates is not None


def test_replaced_source_is_reprobed_instead_of_reusing_bound_metadata(highlight_input):
    task_id, directories = highlight_input
    source = directories["raw"] / "source.mp4"
    for duration, expected_end in [(60, 32), (31, 31)]:
        subprocess.run([
            "ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=size=16x16:rate=1",
            "-t", str(duration), "-c:v", "mpeg4", str(source),
        ], check=True, capture_output=True)

        result = _analyze(task_id)

        assert result.candidates[0]["source_signals"]["media_end_s"] == duration
        assert result.candidates[0]["default_range"] == {"start_s": 8, "end_s": expected_end}
