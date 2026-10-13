import json
import subprocess

import pytest

from app.arctime import local_asr


@pytest.fixture
def engine(tmp_path, monkeypatch):
    model = tmp_path / "model.bin"
    model.write_bytes(b"lmggtest-model")
    monkeypatch.setattr(local_asr.media, "tool_path", lambda name: name)
    return local_asr.LocalASR(model, language="zh")


def fake_tools(monkeypatch, content=None, fail=False):
    calls = []

    def run(command, **kwargs):
        calls.append(command)
        if command[0] == "ffmpeg":
            from pathlib import Path
            Path(command[-1]).write_bytes(b"audio")
        elif not fail:
            from pathlib import Path
            prefix = Path(command[command.index("-of") + 1])
            prefix.with_suffix(".srt").write_text(
                "1\n00:00:01,000 --> 00:00:03,000\n你好！\n" if content is None else content
            )
        return subprocess.CompletedProcess(command, 1 if fail else 0, "", "")

    monkeypatch.setattr(local_asr.subprocess, "run", run)
    return calls


def test_chunks_rebase_timestamps_and_reuse_cache(tmp_path, engine, monkeypatch):
    video = tmp_path / "source.mp4"
    video.write_bytes(b"source")
    calls = fake_tools(monkeypatch)
    cues = engine.transcribe(video, tmp_path, 310)
    assert [(s.start_seconds, s.end_seconds) for s in cues] == [(1, 3), (301, 303)]
    assert len(calls) == 4
    assert "-tr" not in calls[1]
    assert calls[1][calls[1].index("-l") + 1] == "zh"
    assert engine.transcribe(video, tmp_path, 310) == cues
    assert len(calls) == 4


def test_changed_source_does_not_reuse_cached_text(tmp_path, engine, monkeypatch):
    video = tmp_path / "source.mp4"
    video.write_bytes(b"source")
    calls = fake_tools(monkeypatch)
    engine.transcribe(video, tmp_path, 10)
    video.write_bytes(b"different")
    engine.transcribe(video, tmp_path, 10)
    assert len(calls) == 4


def test_tampered_cache_is_recomputed(tmp_path, engine, monkeypatch):
    video = tmp_path / "source.mp4"
    video.write_bytes(b"source")
    calls = fake_tools(monkeypatch)
    engine.transcribe(video, tmp_path, 10)
    cached = tmp_path / "asr" / "chunk-0001.json"
    payload = json.loads(cached.read_text())
    payload["segments"][0]["text"] = "tampered"
    cached.write_text(json.dumps(payload))
    assert engine.transcribe(video, tmp_path, 10)[0].text == "你好！"
    assert len(calls) == 4


@pytest.mark.parametrize("content", ["", "1\n00:00:01,000 --> 00:00:15,000\nwrong timing\n"])
def test_empty_or_out_of_bounds_asr_does_not_publish_success(tmp_path, engine, monkeypatch, content):
    video = tmp_path / "source.mp4"
    video.write_bytes(b"source")
    fake_tools(monkeypatch, content=content)
    with pytest.raises(ValueError):
        engine.transcribe(video, tmp_path, 10)
    assert not (tmp_path / "subtitles.srt").exists()


def test_process_error_preserves_no_successful_chunk(tmp_path, engine, monkeypatch):
    video = tmp_path / "source.mp4"
    video.write_bytes(b"source")
    fake_tools(monkeypatch, fail=True)
    with pytest.raises(RuntimeError, match="failed"):
        engine.transcribe(video, tmp_path, 10)
    assert not (tmp_path / "asr" / "chunk-0001.json").exists()


def test_small_terminal_timestamp_overrun_is_clipped_and_cached(tmp_path, engine, monkeypatch):
    video = tmp_path / "source.mp4"
    video.write_bytes(b"source")
    calls = fake_tools(monkeypatch, content="1\n00:04:57,000 --> 00:04:59,000\n前一句\n\n"
                       "2\n00:04:59,000 --> 00:05:01,000\n跨越分块边界\n")
    cues = engine.transcribe(video, tmp_path, 300)
    assert [(cue.start_seconds, cue.end_seconds) for cue in cues] == [(297, 299), (299, 300)]
    assert engine.transcribe(video, tmp_path, 300) == cues
    assert len(calls) == 2
    cached = json.loads((tmp_path / "asr/chunk-0001.json").read_text())
    assert cached["segments"][-1]["end_seconds"] == 300


@pytest.mark.parametrize("end", ["00:05:02,040", "00:05:12,000", "00:05:30,000"])
def test_terminal_asr_window_overrun_is_clipped(tmp_path, engine, monkeypatch, end):
    video = tmp_path / "source.mp4"
    video.write_bytes(b"source")
    fake_tools(monkeypatch, content=f"1\n00:04:57,960 --> {end}\n末尾一句\n")
    cues = engine.transcribe(video, tmp_path, 300)
    assert [(cue.start_seconds, cue.end_seconds, cue.text) for cue in cues] == [(297.96, 300, "末尾一句")]


@pytest.mark.parametrize("timing", ["00:04:57,960 --> 00:05:30,001", "00:02:00,000 --> 00:05:02,040"])
def test_nonterminal_or_excessive_asr_overrun_is_rejected(tmp_path, engine, monkeypatch, timing):
    video = tmp_path / "source.mp4"
    video.write_bytes(b"source")
    fake_tools(monkeypatch, content=f"1\n{timing}\n异常时间\n")
    with pytest.raises(ValueError, match="timestamps exceed chunk duration"):
        engine.transcribe(video, tmp_path, 300)
    assert not (tmp_path / "asr/chunk-0001.json").exists()


def test_fractional_final_chunk_clips_end_without_zero_length_cues(tmp_path, engine, monkeypatch):
    video = tmp_path / "source.mp4"
    video.write_bytes(b"source")
    fake_tools(monkeypatch, content="1\n00:00:07,000 --> 00:00:09,000\n最后一句\n\n"
               "2\n00:00:08,300 --> 00:00:09,000\n音频以外\n")
    cues = engine.transcribe(video, tmp_path, 8.27225)
    assert len(cues) == 1
    assert (cues[0].start_seconds, cues[0].end_seconds) == (7, 8.27225)


def test_zero_duration_asr_fragment_merges_into_contiguous_previous_cue(tmp_path, engine, monkeypatch):
    video = tmp_path / "source.mp4"
    video.write_bytes(b"source")
    calls = fake_tools(monkeypatch, content="1\n00:00:56,260 --> 00:00:58,760\n上一句\n\n"
                       "2\n00:00:58,760 --> 00:00:58,760\n补充文字\n\n"
                       "3\n00:00:58,760 --> 00:01:02,080\n下一句\n")
    cues = engine.transcribe(video, tmp_path, 300)
    assert [(cue.start_seconds, cue.end_seconds, cue.text) for cue in cues] == [
        (56.26, 58.76, "上一句\n补充文字"), (58.76, 62.08, "下一句")]
    assert engine.transcribe(video, tmp_path, 300) == cues
    assert len(calls) == 2


@pytest.mark.parametrize("timing", ["00:00:01,000 --> 00:00:01,000", "00:00:02,000 --> 00:00:01,000"])
def test_isolated_zero_or_reversed_asr_cue_is_rejected(tmp_path, engine, monkeypatch, timing):
    video = tmp_path / "source.mp4"
    video.write_bytes(b"source")
    fake_tools(monkeypatch, content=f"1\n{timing}\n文字\n")
    with pytest.raises(ValueError, match="positive cue durations"):
        engine.transcribe(video, tmp_path, 10)
    assert not (tmp_path / "asr/chunk-0001.json").exists()


def test_missing_or_invalid_model_fails_preflight(tmp_path, monkeypatch):
    monkeypatch.setattr(local_asr.media, "tool_path", lambda name: name)
    with pytest.raises(FileNotFoundError):
        local_asr.LocalASR(tmp_path / "missing.bin").identity()
    model = tmp_path / "invalid.bin"
    model.write_text("not a model")
    with pytest.raises(ValueError, match="GGML"):
        local_asr.LocalASR(model).identity()


def test_silent_chunk_is_allowed_if_other_chunks_contain_speech(tmp_path, engine, monkeypatch):
    video = tmp_path / "source.mp4"
    video.write_bytes(b"source")
    original = fake_tools(monkeypatch)
    runner = local_asr.subprocess.run

    def partly_silent(command, **kwargs):
        result = runner(command, **kwargs)
        if command[0] == "whisper-cli" and "chunk-0001" in command[command.index("-of") + 1]:
            from pathlib import Path
            Path(command[command.index("-of") + 1]).with_suffix(".srt").write_text("")
        return result

    monkeypatch.setattr(local_asr.subprocess, "run", partly_silent)
    cues = engine.transcribe(video, tmp_path, 310)
    assert [(s.start_seconds, s.end_seconds) for s in cues] == [(301, 303)]
    assert len(original) == 4
