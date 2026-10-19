import json

import httpx
import pytest
from pydantic import SecretStr

from app.arctime import media, translation, workflow
from app.services.subtitles import SubtitleSegment, render_srt


def fixture_run(tmp_path):
    cues = [SubtitleSegment(str(i), i, i + .8, f"こんにちは{i}") for i in range(1, 4)]
    (tmp_path / "subtitles.srt").write_text(render_srt(cues))
    job = {"version": 2, "state": "completed", "subtitles": "subtitles.srt",
           "artifacts": {"subtitles.srt": media.fingerprint(tmp_path / "subtitles.srt")},
           "completed_clips": [{"video": "clip-001.mp4"}], "selection": [{"start": 1.5, "end": 3.5}]}
    workflow.write_manifest(tmp_path, job)
    return cues


@pytest.mark.parametrize("model", ["deepseek-flash"])
def test_translation_preserves_source_and_timings_and_recovers_batches(tmp_path, monkeypatch, model):
    fixture_run(tmp_path)
    original = {p.name: media.fingerprint(p) for p in tmp_path.iterdir()}
    monkeypatch.setattr(translation, "BATCH_SIZE", 2)
    calls = []
    fail = True

    def respond(request):
        nonlocal fail
        payload = json.loads(request.content)
        assert payload["model"] == model
        assert payload["thinking"] == {"type": "disabled"}
        rows = json.loads(payload["messages"][1]["content"])["segments"]
        calls.append([r["id"] for r in rows])
        if len(calls) == 2 and fail:
            fail = False
            return httpx.Response(401, text="secret-key must not escape")
        result = {"segments": [{"id": r["id"], "zh": "你好"} for r in rows]}
        return httpx.Response(200, json={"choices": [{"finish_reason": "stop", "message": {"content": json.dumps(result)}}]})

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        with pytest.raises(ValueError, match="API Key"):
            translation.translate_run(tmp_path, SecretStr("secret-key"), client=client, model=model)
        state = translation.translate_run(tmp_path, SecretStr("secret-key"), client=client, model=model)
    assert calls == [[1, 2], [3], [3]]
    assert state["state"] == "completed"
    assert state["identity"]["model"] == model
    assert "secret-key" not in (tmp_path / "translation.json").read_text()
    for name, digest in original.items():
        assert media.fingerprint(tmp_path / name) == digest
    full = media.read_subtitles(tmp_path / "subtitles.ja-zh.srt")
    assert [(c.start_seconds, c.end_seconds) for c in full] == [(1, 1.8), (2, 2.8), (3, 3.8)]
    assert full[0].text == "こんにちは1\n你好"
    clip = media.read_subtitles(tmp_path / "clip-001.ja-zh.srt")
    assert (clip[0].start_seconds, clip[0].end_seconds) == (0, .3)
    assert clip[-1].end_seconds == 2


@pytest.mark.parametrize("rows", [[], [{"id": 1, "zh": ""}], [{"id": 2, "zh": "你好"}],
                                 [{"id": 1, "zh": "你好"}, {"id": 1, "zh": "重复"}],
                                 [{"id": True, "zh": "你好"}], [{"id": 1, "zh": "00:01 --> 00:02"}]])
def test_rejects_invalid_provider_rows(rows):
    with pytest.raises(ValueError):
        translation.validate_rows(rows, [1])


def test_corrupted_checkpoint_and_changed_source_are_not_reused(tmp_path):
    fixture_run(tmp_path)
    media.write_json(tmp_path / "translation.json", {"identity": {}, "batches": [["fake"]]})
    with pytest.raises(ValueError, match="配置|字幕|缓存"):
        translation.translate_run(tmp_path, SecretStr("key"))
    (tmp_path / "translation.json").unlink()
    (tmp_path / "subtitles.srt").write_text("changed")
    with pytest.raises(ValueError, match="字幕"):
        translation.translate_run(tmp_path, SecretStr("key"))


def test_truncated_response_never_publishes(tmp_path):
    fixture_run(tmp_path)
    def respond(request):
        return httpx.Response(200, json={"choices": [{"finish_reason": "length", "message": {"content": "{}"}}]})
    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        with pytest.raises(ValueError, match="不完整"):
            translation.translate_run(tmp_path, SecretStr("key"), client=client)
    assert not (tmp_path / "subtitles.ja-zh.srt").exists()


def test_completed_checkpoint_requires_all_rows_and_outputs(tmp_path, monkeypatch):
    fixture_run(tmp_path)
    monkeypatch.setattr(translation, "_request", lambda client, key, cues, start, model, **kwargs: [{"id": start + i + 1, "zh": "你好"} for i, cue in enumerate(cues)])
    state = translation.translate_run(tmp_path, SecretStr("key"))
    unchanged = media.fingerprint(tmp_path / "translation.json")
    with pytest.raises(ValueError, match="缓存"):
        translation.translate_run(tmp_path, SecretStr("key"), model="deepseek-v4-pro")
    assert media.fingerprint(tmp_path / "translation.json") == unchanged
    original = json.loads(json.dumps(state))
    state["batches"] = []
    media.write_json(tmp_path / "translation.json", state)
    with pytest.raises(ValueError, match="缓存"):
        translation.translate_run(tmp_path, SecretStr("key"))
    original["artifacts"] = {}
    media.write_json(tmp_path / "translation.json", original)
    with pytest.raises(ValueError, match="缓存"):
        translation.translate_run(tmp_path, SecretStr("key"))
