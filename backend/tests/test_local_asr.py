import json
import subprocess

import pytest

from app.arctime import local_asr


@pytest.fixture
def engine(tmp_path, monkeypatch):
    model = tmp_path / "model.bin"
    model.write_bytes(b"lmggtest-model")
    monkeypatch.setattr(local_asr.media, "tool_path", lambda name: name)
    vad = tmp_path / 'vad.bin'
    vad.write_bytes(b'fixture-vad')
    monkeypatch.setattr(local_asr, 'DEFAULT_VAD_MODEL', vad, raising=False)
    monkeypatch.setattr(local_asr, 'VAD_MODEL_SHA256', local_asr.media.fingerprint(vad), raising=False)
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


def test_auto_language_uses_engine_result_and_survives_chunk_cache(tmp_path, engine, monkeypatch):
    from dataclasses import replace
    from pathlib import Path
    engine = replace(engine, language='auto')
    video = tmp_path / 'source.mp4'
    video.write_bytes(b'source')
    calls = fake_tools(monkeypatch)
    original = local_asr.subprocess.run

    def recognize(command, **kwargs):
        result = original(command, **kwargs)
        if command[0] == 'whisper-cli':
            prefix = Path(command[command.index('-of') + 1])
            prefix.with_suffix('.json').write_text(json.dumps({'result': {'language': 'ja'}}))
        return result

    monkeypatch.setattr(local_asr.subprocess, 'run', recognize)
    cues = engine.transcribe(video, tmp_path, 310)
    detected = json.loads((tmp_path / 'asr-language.json').read_bytes())
    assert detected == {'source_sha256': local_asr.media.fingerprint(video), 'language': 'ja'}
    assert all('-oj' in command for command in calls if command[0] == 'whisper-cli')
    (tmp_path / 'asr-language.json').unlink()
    assert engine.transcribe(video, tmp_path, 310) == cues
    assert json.loads((tmp_path / 'asr-language.json').read_bytes()) == detected
    assert len(calls) == 4


def test_auto_language_never_guesses_from_subtitle_text(tmp_path, engine, monkeypatch):
    from dataclasses import replace
    engine = replace(engine, language='auto')
    video = tmp_path / 'source.mp4'
    video.write_bytes(b'source')
    fake_tools(monkeypatch)
    with pytest.raises((ValueError, OSError), match='language|json'):
        engine.transcribe(video, tmp_path, 10)
    assert not (tmp_path / 'asr/chunk-0001.json').exists()


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


@pytest.mark.parametrize('duration,start,end', [(7.167333, 3.5, 8.0), (20.833, 9.38, 21.04)])
def test_observed_live_tail_estimate_is_clipped_even_when_cue_starts_before_tail_window(
        tmp_path, engine, monkeypatch, duration, start, end):
    from app.services.subtitles import SubtitleSegment, render_srt
    video = tmp_path / 'source.mp4'
    video.write_bytes(b'source')
    calls = fake_tools(monkeypatch, content=render_srt([SubtitleSegment('1', start, end, '末尾一句')]))
    cues = engine.transcribe(video, tmp_path, duration)
    assert [(cue.start_seconds, cue.end_seconds, cue.text) for cue in cues] == [(start, duration, '末尾一句')]
    assert engine.transcribe(video, tmp_path, duration) == cues
    assert len(calls) == 2


@pytest.mark.parametrize('duration,end', [(7.167333, 8.168), (0.2, 1.0)])
def test_excessive_nonterminal_live_overrun_is_still_rejected(tmp_path, engine, monkeypatch, duration, end):
    from app.services.subtitles import SubtitleSegment, render_srt
    video = tmp_path / 'source.mp4'
    video.write_bytes(b'source')
    fake_tools(monkeypatch, content=render_srt([SubtitleSegment('1', 0, end, '异常时间')]))
    with pytest.raises(ValueError, match='timestamps exceed chunk duration'):
        engine.transcribe(video, tmp_path, duration)
    assert not (tmp_path / 'asr/chunk-0001.json').exists()


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


@pytest.mark.parametrize('retry_content', ['', '1\n00:00:01,000 --> 00:00:03,000\n有效语音\n'])
def test_invalid_timing_retries_once_with_vad_and_caches_only_verified_result(
        tmp_path, engine, monkeypatch, retry_content):
    video = tmp_path / 'source.mp4'
    video.write_bytes(b'source')
    calls = fake_tools(monkeypatch, content='1\n00:00:00,000 --> 00:00:30,000\n' + 'ව' * 100 + '\n')
    original = local_asr.subprocess.run
    def retry(command, **kwargs):
        result = original(command, **kwargs)
        if '--vad' in command:
            from pathlib import Path
            Path(command[command.index('-of') + 1]).with_suffix('.srt').write_text(retry_content)
        return result
    monkeypatch.setattr(local_asr.subprocess, 'run', retry)
    if retry_content:
        cues = engine.transcribe(video, tmp_path, 22.333)
        assert [(c.start_seconds, c.end_seconds, c.text) for c in cues] == [(1, 3, '有效语音')]
    else:
        with pytest.raises(ValueError, match='No speech was recognized'):
            engine.transcribe(video, tmp_path, 22.333)
    assert len(calls) == 3
    cached = json.loads((tmp_path / 'asr/chunk-0001.json').read_text())
    assert len(cached['segments']) == (1 if retry_content else 0)
    assert cached['key']['asr'] == engine.identity()
    if retry_content:
        engine.transcribe(video, tmp_path, 22.333)
    else:
        with pytest.raises(ValueError, match='No speech was recognized'):
            engine.transcribe(video, tmp_path, 22.333)
    assert len(calls) == 3


def test_invalid_vad_retry_does_not_cache_or_loop(tmp_path, engine, monkeypatch):
    video = tmp_path / 'source.mp4'
    video.write_bytes(b'source')
    calls = fake_tools(monkeypatch, content='1\n00:00:00,000 --> 00:00:30,000\n异常时间\n')
    with pytest.raises(ValueError, match='timestamps exceed chunk duration'):
        engine.transcribe(video, tmp_path, 22.333)
    assert len(calls) == 3 and '--vad' in calls[-1]
    assert not (tmp_path / 'asr/chunk-0001.json').exists()


@pytest.mark.parametrize('missing', [False, True])
def test_vad_retry_requires_verified_model(tmp_path, engine, monkeypatch, missing):
    video = tmp_path / 'source.mp4'
    video.write_bytes(b'source')
    if missing:
        local_asr.DEFAULT_VAD_MODEL.unlink()
    else:
        local_asr.DEFAULT_VAD_MODEL.write_bytes(b'tampered-vad')
    calls = fake_tools(monkeypatch, content='1\n00:00:00,000 --> 00:00:30,000\n异常时间\n')
    with pytest.raises(RuntimeError, match='VAD'):
        engine.transcribe(video, tmp_path, 22.333)
    assert len(calls) == 2 and not (tmp_path / 'asr/chunk-0001.json').exists()


def test_bundled_whisper_uses_one_library_directory_without_mutating_parent_environment(
        tmp_path, engine, monkeypatch):
    import os
    from pathlib import Path
    tools = tmp_path / 'tools'
    tools.mkdir()
    (tools / 'libomp.dylib').write_bytes(b'fixture-library')
    monkeypatch.setattr(local_asr.media, 'tool_path', lambda name: str(tools / name))
    monkeypatch.setattr(local_asr.sys, 'platform', 'darwin')
    parent = dict(os.environ)
    observed = []
    def run(command, **kwargs):
        if Path(command[0]).name == 'ffmpeg':
            Path(command[-1]).write_bytes(b'audio')
        else:
            observed.append(kwargs.get('env', {}).get('DYLD_LIBRARY_PATH'))
            Path(command[command.index('-of') + 1]).with_suffix('.srt').write_text(
                '1\n00:00:01,000 --> 00:00:03,000\n有效语音\n')
        return subprocess.CompletedProcess(command, 0)
    monkeypatch.setattr(local_asr.subprocess, 'run', run)
    video = tmp_path / 'source.mp4'
    video.write_bytes(b'source')
    assert engine.transcribe(video, tmp_path, 10)[0].text == '有效语音'
    assert observed == [str(tools)] and dict(os.environ) == parent


@pytest.mark.parametrize('failure', ['missing_output', 'process_error'])
def test_vad_retry_failure_never_reuses_first_attempt_subtitles(tmp_path, engine, monkeypatch, failure):
    video = tmp_path / 'source.mp4'
    video.write_bytes(b'source')
    calls = fake_tools(monkeypatch, content='1\n00:00:00,000 --> 00:00:30,000\n异常时间\n')
    original = local_asr.subprocess.run
    def retry(command, **kwargs):
        if '--vad' in command:
            calls.append(command)
            return subprocess.CompletedProcess(command, 1 if failure == 'process_error' else 0)
        return original(command, **kwargs)
    monkeypatch.setattr(local_asr.subprocess, 'run', retry)
    with pytest.raises(RuntimeError, match='failed'):
        engine.transcribe(video, tmp_path, 22.333)
    assert len(calls) == 3 and not (tmp_path / 'asr/chunk-0001.json').exists()


def test_frozen_vad_lookup_requires_bundled_asset_even_when_cache_has_a_valid_model(tmp_path, engine, monkeypatch):
    resources = tmp_path / 'resources'
    (resources / 'models').mkdir(parents=True)
    monkeypatch.setattr(local_asr.sys, '_MEIPASS', str(resources), raising=False)
    with pytest.raises(RuntimeError, match='VAD'):
        local_asr._vad_model()
    bundled = resources / 'models' / local_asr.VAD_MODEL_NAME
    bundled.write_bytes(local_asr.DEFAULT_VAD_MODEL.read_bytes())
    assert local_asr._vad_model() == bundled
    bundled.unlink()
    bundled.symlink_to(local_asr.DEFAULT_VAD_MODEL)
    with pytest.raises(RuntimeError, match='VAD'):
        local_asr._vad_model()
