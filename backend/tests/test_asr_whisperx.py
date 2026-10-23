from __future__ import annotations

import json
import sys
import time
import types
from pathlib import Path

import pytest


def _reset_runtime_state() -> None:
    try:
        from app.db import reset_db_runtime
    except ModuleNotFoundError:
        return
    reset_db_runtime()


@pytest.fixture()
def backend_env(tmp_path, monkeypatch) -> dict[str, Path | str]:
    data_dir = tmp_path / "data"
    db_path = tmp_path / "task-state.sqlite3"
    monkeypatch.setenv("APP_DATA_DIR", str(data_dir))
    monkeypatch.setenv("APP_DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("APP_WHISPERX_MODEL_NAME", "large-v3")
    monkeypatch.setenv("APP_WHISPERX_LANGUAGE", "zh")
    monkeypatch.setenv("APP_WHISPERX_DEVICE", "cpu")
    monkeypatch.setenv("APP_WHISPERX_COMPUTE_TYPE", "int8")
    _reset_runtime_state()
    return {"data_dir": data_dir, "db_path": db_path}


@pytest.fixture(autouse=True)
def task_control_shim(monkeypatch):
    shim = types.ModuleType("app.services.task_control")
    shim.ensure_current_execution_context = lambda session, *, task_id: None
    monkeypatch.setitem(sys.modules, "app.services.task_control", shim)
    yield


def _create_task(source_url: str) -> str:
    from app.db import init_db, session_scope
    from app.repositories.tasks import create_task

    init_db()
    with session_scope() as session:
        payload, _ = create_task(session, source_url)
        return payload["task_id"]


def _prepare_audio_fixture(data_dir: Path, task_id: str) -> Path:
    audio_path = data_dir / "tasks" / task_id / "work" / "asr-input.wav"
    audio_path.parent.mkdir(parents=True, exist_ok=True)
    audio_path.write_bytes(b"RIFFfixture")
    return audio_path


def _prepare_media_chunk_fixture(data_dir: Path, task_id: str) -> Path:
    from app.services.media_chunks import build_media_chunk_manifest, write_media_chunk_manifest_atomically

    work_dir = data_dir / "tasks" / task_id / "work"
    manifest = build_media_chunk_manifest(10.0, work_dir=work_dir)
    audio_path = manifest.chunks[0].audio_path
    audio_path.parent.mkdir(parents=True, exist_ok=True)
    audio_path.write_bytes(b"RIFFfixture")
    write_media_chunk_manifest_atomically(work_dir / "media-chunks.json", manifest)
    return audio_path


class _FakeModel:
    def __init__(self, transcription_result: dict):
        self.transcription_result = transcription_result

    def transcribe(self, audio_path: str, *, batch_size: int, language: str) -> dict:
        assert audio_path.endswith(".wav")
        assert batch_size >= 1
        return {
            **self.transcription_result,
            "language": language,
        }


class _FakeWhisperX:
    def __init__(self, *, transcription_result: dict, aligned_result: dict):
        self.transcription_result = transcription_result
        self.aligned_result = aligned_result

    def load_model(self, model_name: str, device: str, *, compute_type: str, download_root: str | None = None):
        assert model_name == "large-v3"
        assert device == "cpu"
        assert compute_type == "int8"
        return _FakeModel(self.transcription_result)

    def load_align_model(
        self,
        *,
        language_code: str,
        device: str,
        model_name: str | None = None,
        model_dir: str | None = None,
        model_cache_only: bool = False,
    ):
        assert language_code == "zh"
        assert device == "cpu"
        assert model_cache_only is False
        return object(), {"language_code": language_code, "align_model_name": model_name or "default-align"}

    def align(
        self,
        segments: list[dict],
        align_model,
        metadata: dict,
        audio_path: str,
        device: str,
        *,
        return_char_alignments: bool,
    ) -> dict:
        assert segments == self.transcription_result["segments"]
        assert audio_path.endswith(".wav")
        assert metadata["language_code"] == "zh"
        assert device == "cpu"
        assert return_char_alignments is False
        return self.aligned_result


def test_transcribe_fixture_audio_persists_alignment_json_and_srt(backend_env, monkeypatch) -> None:
    task_id = _create_task("https://www.bilibili.com/video/BV1as411c7mR")
    audio_path = _prepare_audio_fixture(Path(backend_env["data_dir"]), task_id)
    fake_whisperx = _FakeWhisperX(
        transcription_result={
            "segments": [
                {"start": 0.0, "end": 1.2, "text": " 你好 ", "words": [{"word": "你好", "start": 0.0, "end": 1.2}]},
                {"start": 1.2, "end": 2.8, "text": "世界", "words": []},
            ]
        },
        aligned_result={
            "segments": [
                {"start": 0.0, "end": 1.2, "text": "你好", "words": [{"word": "你好", "start": 0.0, "end": 1.2, "score": 0.95}]},
                {"start": 1.2, "end": 2.8, "text": "世界", "words": []},
            ],
            "language": "zh",
        },
    )

    monkeypatch.setattr("app.services.asr_whisperx._load_whisperx_module", lambda: fake_whisperx)
    clock = {"value": 100.0}

    def _fake_perf_counter() -> float:
        clock["value"] += 0.25
        return clock["value"]

    monkeypatch.setattr("app.services.asr_whisperx.time.perf_counter", _fake_perf_counter)

    from app.services.asr_whisperx import execute_asr_pipeline
    from app.settings import get_settings

    result = execute_asr_pipeline(audio_path=audio_path, work_dir=audio_path.parent, settings=get_settings())

    assert result.audio_path == audio_path
    assert result.transcript_path.exists()
    assert result.subtitle_path.exists()
    assert result.raw_alignment_path.exists()
    assert result.elapsed_seconds > 0
    assert result.model_metadata["provider"] == "whisperx"
    assert result.model_metadata["model_name"] == "large-v3"

    transcript_payload = json.loads(result.transcript_path.read_text(encoding="utf-8"))
    assert [segment["id"] for segment in transcript_payload["segments"]] == ["seg-0001", "seg-0002"]
    assert transcript_payload["segments"][0]["words"][0]["text"] == "你好"
    assert transcript_payload["elapsed_seconds"] == result.elapsed_seconds

    assert result.subtitle_path.read_text(encoding="utf-8") == (
        "1\n"
        "00:00:00,000 --> 00:00:01,200\n"
        "你好\n\n"
        "2\n"
        "00:00:01,200 --> 00:00:02,800\n"
        "世界\n"
    )
    assert json.loads(result.raw_alignment_path.read_text(encoding="utf-8"))["language"] == "zh"

def test_missing_model_is_terminal(backend_env, monkeypatch) -> None:
    task_id = _create_task("https://www.bilibili.com/video/BV1bs411c7mS")
    audio_path = _prepare_audio_fixture(Path(backend_env["data_dir"]), task_id)

    class _MissingModelWhisperX:
        def load_model(self, *args, **kwargs):
            raise FileNotFoundError("missing model files")

    monkeypatch.setattr("app.services.asr_whisperx._load_whisperx_module", lambda: _MissingModelWhisperX())

    from app.services.asr_whisperx import AsrPipelineError, execute_asr_pipeline
    from app.settings import get_settings

    with pytest.raises(AsrPipelineError) as exc_info:
        execute_asr_pipeline(audio_path=audio_path, work_dir=audio_path.parent, settings=get_settings())

    assert exc_info.value.code == "missing_model"
    assert "provision" in str(exc_info.value).lower()


def test_oom_is_classified(backend_env, monkeypatch) -> None:
    task_id = _create_task("https://www.bilibili.com/video/BV1cs411c7mT")
    audio_path = _prepare_audio_fixture(Path(backend_env["data_dir"]), task_id)

    class _OomWhisperX:
        def load_model(self, *args, **kwargs):
            raise RuntimeError("CUDA out of memory while loading model")

    monkeypatch.setattr("app.services.asr_whisperx._load_whisperx_module", lambda: _OomWhisperX())

    from app.services.asr_whisperx import AsrPipelineError, execute_asr_pipeline
    from app.settings import get_settings

    with pytest.raises(AsrPipelineError) as exc_info:
        execute_asr_pipeline(audio_path=audio_path, work_dir=audio_path.parent, settings=get_settings())

    assert exc_info.value.code == "oom"


def test_rocm_cuda_request_falls_back_to_cpu_float32(backend_env, monkeypatch) -> None:
    task_id = _create_task("https://www.bilibili.com/video/BV1rocmfallback001")
    audio_path = _prepare_audio_fixture(Path(backend_env["data_dir"]), task_id)
    monkeypatch.setenv("APP_WHISPERX_DEVICE", "cuda")
    monkeypatch.setenv("APP_WHISPERX_COMPUTE_TYPE", "float16")

    observed: dict[str, object] = {}

    class _FallbackWhisperX(_FakeWhisperX):
        def load_model(self, model_name: str, device: str, *, compute_type: str, download_root: str | None = None):
            observed["load_model_device"] = device
            observed["load_model_compute_type"] = compute_type
            return _FakeModel(self.transcription_result)

        def load_align_model(
            self,
            *,
            language_code: str,
            device: str,
            model_name: str | None = None,
            model_dir: str | None = None,
            model_cache_only: bool = False,
        ):
            observed["align_device"] = device
            return super().load_align_model(
                language_code=language_code,
                device=device,
                model_name=model_name,
                model_dir=model_dir,
                model_cache_only=model_cache_only,
            )

    fake_whisperx = _FallbackWhisperX(
        transcription_result={"segments": [{"start": 0.0, "end": 1.0, "text": "你好"}]},
        aligned_result={"segments": [{"start": 0.0, "end": 1.0, "text": "你好", "words": []}]},
    )

    class _FakeCTranslate2:
        @staticmethod
        def get_supported_compute_types(device: str):
            if device == "cuda":
                raise RuntimeError("CUDA failed with error CUDA driver version is insufficient for CUDA runtime version")
            assert device == "cpu"
            return {"float32", "int8", "int8_float32"}

    monkeypatch.setattr("app.services.asr_whisperx._load_whisperx_module", lambda: fake_whisperx)
    monkeypatch.setattr("app.services.asr_whisperx._load_ctranslate2_module", lambda: _FakeCTranslate2())
    monkeypatch.setattr(
        "app.services.asr_whisperx.detect_runtime_profile",
        lambda: {
            "detected_profile": "wsl-rocm",
            "accelerator": {"torch_build_family": "rocm"},
            "platform": {"is_wsl": True},
        },
    )

    from app.services.asr_whisperx import execute_asr_pipeline
    from app.settings import get_settings

    result = execute_asr_pipeline(audio_path=audio_path, work_dir=audio_path.parent, settings=get_settings())

    assert observed == {
        "load_model_device": "cpu",
        "load_model_compute_type": "float32",
        "align_device": "cpu",
    }
    assert result.model_metadata["device"] == "cpu"
    assert result.model_metadata["compute_type"] == "float32"
    assert result.model_metadata["requested_device"] == "cuda"
    assert result.model_metadata["requested_compute_type"] == "float16"
    assert "runtime_warning" in result.model_metadata


def test_alignment_failure_is_classified(backend_env, monkeypatch) -> None:
    task_id = _create_task("https://www.bilibili.com/video/BV1ds411c7mU")
    audio_path = _prepare_audio_fixture(Path(backend_env["data_dir"]), task_id)
    fake_whisperx = _FakeWhisperX(
        transcription_result={"segments": [{"start": 0.0, "end": 1.0, "text": "你好"}]},
        aligned_result={"segments": [{"text": "missing timestamps"}]},
    )

    monkeypatch.setattr("app.services.asr_whisperx._load_whisperx_module", lambda: fake_whisperx)

    from app.services.asr_whisperx import AsrPipelineError, execute_asr_pipeline
    from app.settings import get_settings

    with pytest.raises(AsrPipelineError) as exc_info:
        execute_asr_pipeline(audio_path=audio_path, work_dir=audio_path.parent, settings=get_settings())

    assert exc_info.value.code == "alignment_failed"


def test_missing_model_recovery_payload_describes_main_and_alignment_targets(
    backend_env,
    monkeypatch,
) -> None:
    monkeypatch.setenv("APP_WHISPERX_MODEL_NAME", "large-v3")
    monkeypatch.setenv(
        "APP_WHISPERX_ALIGNMENT_MODEL_NAME",
        "jonatasgrosman/wav2vec2-large-xlsr-53-chinese-zh-cn",
    )
    monkeypatch.setenv("APP_WHISPERX_MODEL_CACHE_DIR", str(Path(backend_env["data_dir"]) / "models" / "whisperx"))

    from app.services.asr_whisperx import build_asr_missing_model_recovery
    from app.settings import get_settings

    recovery = build_asr_missing_model_recovery(get_settings())

    assert recovery["stage"] == "asr"
    assert recovery["kind"] == "missing_model"
    assert [model["key"] for model in recovery["models"]] == ["whisperx", "alignment"]
    assert all(model["target_dir"] for model in recovery["models"])
    assert all(model["download_supported"] is True for model in recovery["models"])


def test_download_asr_missing_models_downloads_only_requested_missing_assets(
    backend_env,
    monkeypatch,
) -> None:
    model_root = Path(backend_env["data_dir"]) / "models"
    monkeypatch.setenv("APP_WHISPERX_MODEL_CACHE_DIR", str(model_root / "whisperx"))

    snapshot_calls: list[tuple[str, str]] = []
    faster_whisper_calls: list[tuple[str, str]] = []

    def fake_download_snapshot(*, repo_id: str, local_dir: str, **kwargs):
        snapshot_calls.append((repo_id, local_dir))
        Path(local_dir).mkdir(parents=True, exist_ok=True)
        (Path(local_dir) / "config.json").write_text("{}", encoding="utf-8")
        return local_dir

    def fake_download_faster_whisper_model(model_ref: str, output_dir: str, **kwargs):
        faster_whisper_calls.append((model_ref, output_dir))
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        (Path(output_dir) / "config.json").write_text("{}", encoding="utf-8")
        (Path(output_dir) / "model.bin").write_bytes(b"fixture")
        return output_dir

    monkeypatch.setattr("app.services.asr_whisperx.snapshot_download", fake_download_snapshot)
    monkeypatch.setattr(
        "app.services.asr_whisperx.download_faster_whisper_model",
        fake_download_faster_whisper_model,
    )

    from app.services.asr_whisperx import download_asr_missing_models
    from app.settings import get_settings

    result = download_asr_missing_models(
        get_settings(),
        requested_keys=["whisperx", "alignment"],
    )

    assert [item["key"] for item in result["models"]] == ["whisperx", "alignment"]
    assert faster_whisper_calls == [
        ("large-v3", result["models"][0]["target_dir"]),
    ]
    assert snapshot_calls == [
        (
            "jonatasgrosman/wav2vec2-large-xlsr-53-chinese-zh-cn",
            result["models"][1]["target_dir"],
        ),
    ]
    assert all(item["status"] == "downloaded" for item in result["models"])


def test_transcribe_uses_recovery_target_directories_when_models_are_present_locally(
    backend_env,
    monkeypatch,
) -> None:
    task_id = _create_task("https://www.bilibili.com/video/BV1localsnap001")
    audio_path = _prepare_audio_fixture(Path(backend_env["data_dir"]), task_id)
    model_root = Path(backend_env["data_dir"]) / "models" / "whisperx"
    monkeypatch.setenv("APP_WHISPERX_MODEL_CACHE_DIR", str(model_root))
    from app.services.asr_whisperx import build_asr_missing_model_recovery
    from app.settings import get_settings
    recovery = build_asr_missing_model_recovery(get_settings())
    main_target = Path(recovery["models"][0]["target_dir"])
    alignment_target = Path(recovery["models"][1]["target_dir"])
    main_target.mkdir(parents=True, exist_ok=True)
    alignment_target.mkdir(parents=True, exist_ok=True)
    (main_target / "config.json").write_text("{}", encoding="utf-8")
    (main_target / "model.bin").write_bytes(b"fixture")
    (alignment_target / "config.json").write_text("{}", encoding="utf-8")
    monkeypatch.setenv("APP_WHISPERX_MODEL_CACHE_DIR", str(model_root))

    observed: dict[str, str | None] = {}

    class _LocalPathWhisperX(_FakeWhisperX):
        def load_model(self, model_name: str, device: str, *, compute_type: str, download_root: str | None = None):
            observed["main_model_name"] = model_name
            observed["main_download_root"] = download_root
            assert device == "cpu"
            assert compute_type == "int8"
            return _FakeModel(self.transcription_result)

        def load_align_model(
            self,
            *,
            language_code: str,
            device: str,
            model_name: str | None = None,
            model_dir: str | None = None,
            model_cache_only: bool = False,
        ):
            observed["align_model_name"] = model_name
            observed["align_model_dir"] = model_dir
            return super().load_align_model(
                language_code=language_code,
                device=device,
                model_name=model_name,
                model_dir=model_dir,
                model_cache_only=model_cache_only,
            )

    fake_whisperx = _LocalPathWhisperX(
        transcription_result={"segments": [{"start": 0.0, "end": 1.0, "text": "你好"}]},
        aligned_result={"segments": [{"start": 0.0, "end": 1.0, "text": "你好", "words": []}]},
    )
    monkeypatch.setattr("app.services.asr_whisperx._load_whisperx_module", lambda: fake_whisperx)

    from app.services.asr_whisperx import execute_asr_pipeline

    execute_asr_pipeline(audio_path=audio_path, work_dir=audio_path.parent, settings=get_settings())

    assert observed["main_model_name"] == str(main_target)
    assert observed["align_model_name"] == str(alignment_target)
    assert observed["align_model_dir"] == str(alignment_target)


def test_child_runner_emits_success_protocol_and_manifest(backend_env, monkeypatch, capsys) -> None:
    task_id = _create_task("https://www.bilibili.com/video/BV1childsuccess001")
    _prepare_media_chunk_fixture(Path(backend_env["data_dir"]), task_id)
    fake_whisperx = _FakeWhisperX(
        transcription_result={
            "segments": [
                {"start": 0.0, "end": 1.2, "text": "你好", "words": [{"word": "你好", "start": 0.0, "end": 1.2}]},
                {"start": 1.2, "end": 2.8, "text": "世界", "words": []},
            ]
        },
        aligned_result={
            "segments": [
                {"start": 0.0, "end": 1.2, "text": "你好", "words": [{"word": "你好", "start": 0.0, "end": 1.2, "score": 0.95}]},
                {"start": 1.2, "end": 2.8, "text": "世界", "words": []},
            ],
            "language": "zh",
        },
    )

    clock = {"value": 100.0}

    def _fake_perf_counter() -> float:
        clock["value"] += 0.25
        return clock["value"]

    original_load_model = fake_whisperx.load_model

    def noisy_load_model(*args, **kwargs):
        print("third-party model startup notice")
        return original_load_model(*args, **kwargs)

    monkeypatch.setattr(fake_whisperx, "load_model", noisy_load_model)
    monkeypatch.setattr("app.services.asr_whisperx._load_whisperx_module", lambda: fake_whisperx)
    monkeypatch.setattr("app.services.asr_whisperx.time.perf_counter", _fake_perf_counter)

    from app.services.asr_child_runner import run_asr_child

    result = run_asr_child(task_id, 0)

    captured = capsys.readouterr()
    events = [json.loads(line) for line in captured.out.splitlines() if line.strip()]
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))

    assert result.status == "success"
    assert [event["event"] for event in events] == [
        "phase_start",
        "heartbeat",
        "phase_complete",
        "phase_start",
        "heartbeat",
        "phase_complete",
        "phase_start",
        "heartbeat",
        "phase_complete",
        "phase_start",
        "heartbeat",
        "phase_complete",
        "phase_start",
        "heartbeat",
        "phase_complete",
        "success",
    ]
    assert [event["phase"] for event in events] == [
        "model_load",
        "model_load",
        "model_load",
        "vad",
        "vad",
        "vad",
        "transcribe",
        "transcribe",
        "transcribe",
        "align",
        "align",
        "align",
        "persist",
        "persist",
        "persist",
        "persist",
    ]
    assert Path(events[-1]["manifest_path"]) == result.manifest_path

    assert set(manifest.keys()) == {
        "status",
        "elapsed_ms_total",
        "phases",
        "artifacts",
        "model_metadata",
        "error",
        "cache_identity",
    }
    assert manifest["status"] == "success"
    assert manifest["elapsed_ms_total"] > 0
    assert [phase["name"] for phase in manifest["phases"]] == ["model_load", "vad", "transcribe", "align", "persist"]
    assert all(phase["status"] == "success" for phase in manifest["phases"])
    assert manifest["artifacts"]["transcript_path"].endswith("asr-chunks/chunk-0000/asr-segments.json")
    assert manifest["artifacts"]["subtitle_path"].endswith("subtitles.zh.srt")
    assert manifest["artifacts"]["raw_alignment_path"].endswith("asr-alignment-raw.json")
    assert manifest["model_metadata"]["model_name"] == "large-v3"
    assert manifest["error"] is None
    assert "third-party model startup notice" in captured.err


def test_child_runner_emits_classified_failure_protocol(backend_env, monkeypatch, capsys) -> None:
    task_id = _create_task("https://www.bilibili.com/video/BV1childfailure001")
    _prepare_media_chunk_fixture(Path(backend_env["data_dir"]), task_id).unlink()
    clock = {"value": 200.0}

    def _fake_perf_counter() -> float:
        clock["value"] += 0.25
        return clock["value"]

    monkeypatch.setattr("app.services.asr_whisperx.time.perf_counter", _fake_perf_counter)

    from app.services.asr_child_runner import run_asr_child

    result = run_asr_child(task_id, 0)

    captured = capsys.readouterr()
    events = [json.loads(line) for line in captured.out.splitlines() if line.strip()]
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))

    assert result.status == "failed"
    assert [event["event"] for event in events] == ["failure"]
    assert events[0]["phase"] == "model_load"
    assert events[0]["code"] == "missing_input"

    assert set(manifest.keys()) == {
        "status",
        "elapsed_ms_total",
        "phases",
        "artifacts",
        "model_metadata",
        "error",
    }
    assert manifest["status"] == "failed"
    assert manifest["error"]["code"] == "missing_input"
    assert manifest["error"]["phase"] == "model_load"
    assert [phase["status"] for phase in manifest["phases"]] == ["failed", "pending", "pending", "pending", "pending"]
    assert manifest["artifacts"]["transcript_path"] is None
    assert manifest["artifacts"]["subtitle_path"] is None
    assert manifest["artifacts"]["raw_alignment_path"] is None


def test_child_runner_rejects_noncanonical_task_id(backend_env) -> None:
    from app.services.asr_child_runner import run_asr_child

    with pytest.raises(ValueError, match="Invalid task_id"):
        run_asr_child("../escape", 0)


def test_merge_asr_chunk_segments_rebases_times_and_assigns_global_ids() -> None:
    # Given: two contiguous chunk-local transcript payloads with duplicate local IDs.
    from app.services.asr_whisperx import merge_asr_chunk_segments
    from app.services.media_chunks import MediaChunk
    from app.services.subtitles import SubtitleSegment, SubtitleWord

    chunks = [
        (
            MediaChunk(0, 0.0, 300.0, Path("/tmp/chunk-0000.wav")),
            [SubtitleSegment("seg-0001", 1.0, 2.0, "第一句", [SubtitleWord("第一", 1.0, 1.5)])],
        ),
        (
            MediaChunk(1, 300.0, 301.0, Path("/tmp/chunk-0001.wav")),
            [SubtitleSegment("seg-0001", 0.0, 0.5, "第二句", [SubtitleWord("第二", 0.0, 0.5)])],
        ),
    ]

    # When: the parent merges the validated chunk transcripts.
    merged = merge_asr_chunk_segments(chunks)

    # Then: timestamps are source-global and IDs are unique and ordered.
    assert [(segment.id, segment.start_seconds, segment.end_seconds) for segment in merged] == [
        ("seg-000001", 1.0, 2.0),
        ("seg-000002", 300.0, 300.5),
    ]
    assert merged[1].words is not None
    assert merged[1].words[0].start_seconds == 300.0


def test_merge_asr_chunk_segments_clamps_short_adjacent_overlap() -> None:
    # Given: WhisperX emits a 100 ms overlap at a segment boundary.
    from app.services.asr_whisperx import merge_asr_chunk_segments
    from app.services.media_chunks import MediaChunk
    from app.services.subtitles import SubtitleSegment

    chunks = [
        (
            MediaChunk(0, 0.0, 10.0, Path("/tmp/chunk-0000.wav")),
            [
                SubtitleSegment("a", 1.0, 3.0, "甲"),
                SubtitleSegment("b", 2.9, 4.0, "乙"),
            ],
        )
    ]

    # When: the parent merges the chunk transcript.
    merged = merge_asr_chunk_segments(chunks)

    # Then: the second segment begins at the prior segment boundary.
    assert [(segment.start_seconds, segment.end_seconds) for segment in merged] == [(1.0, 3.0), (3.0, 4.0)]


def test_merge_asr_chunk_segments_rejects_overlapping_global_output() -> None:
    # Given: a chunk transcript whose local segments overlap.
    from app.services.asr_whisperx import AsrFailure, merge_asr_chunk_segments
    from app.services.media_chunks import MediaChunk
    from app.services.subtitles import SubtitleSegment

    chunks = [
        (
            MediaChunk(0, 0.0, 10.0, Path("/tmp/chunk-0000.wav")),
            [
                SubtitleSegment("a", 1.0, 3.0, "甲"),
                SubtitleSegment("b", 2.0, 4.0, "乙"),
            ],
        )
    ]

    # When / Then: corrupted output cannot reach the canonical transcript.
    with pytest.raises(AsrFailure) as raised:
        merge_asr_chunk_segments(chunks)
    assert raised.value.code == "invalid_chunk_output"


def test_run_pipeline_phase_emits_ongoing_heartbeats_during_long_running_work(monkeypatch) -> None:
    observed_events: list[tuple[str, int]] = []

    class _Observer:
        def phase_start(self, phase: str, *, phase_index: int, phase_count: int, message: str) -> None:
            observed_events.append(("phase_start", 0))

        def heartbeat(
            self,
            phase: str,
            *,
            phase_index: int,
            phase_count: int,
            elapsed_ms: int,
            message: str,
        ) -> None:
            observed_events.append(("heartbeat", elapsed_ms))

        def phase_complete(self, phase: str, *, phase_index: int, phase_count: int, elapsed_ms: int) -> None:
            observed_events.append(("phase_complete", elapsed_ms))

    from app.services.asr_whisperx import AsrPhaseResult, _run_pipeline_phase

    phase_results = {"transcribe": AsrPhaseResult(name="transcribe", status="pending")}

    def _slow_action() -> str:
        time.sleep(0.35)
        return "done"

    result = _run_pipeline_phase(
        phase="transcribe",
        phase_results=phase_results,
        observer=_Observer(),
        action=_slow_action,
    )

    heartbeat_events = [event for event in observed_events if event[0] == "heartbeat"]

    assert result == "done"
    assert len(heartbeat_events) >= 2
    assert heartbeat_events[0][1] == 0
    assert any(elapsed_ms > 0 for _, elapsed_ms in heartbeat_events[1:])


def test_generic_model_directory_does_not_override_requested_model(backend_env, monkeypatch):
    from app.services import asr_whisperx as asr
    from app.settings import get_settings
    root = Path(backend_env["data_dir"]) / "models"
    monkeypatch.setenv("APP_WHISPERX_MODEL_CACHE_DIR", str(root))
    for name in ("whisperx", "alignment"):
        target = root / name
        target.mkdir(parents=True)
        (target / "config.json").write_text("{}")
        (target / "model.bin").write_bytes(b"old")
    monkeypatch.setenv("APP_WHISPERX_MODEL_NAME", "small")
    monkeypatch.setenv("APP_WHISPERX_ALIGNMENT_MODEL_NAME", "org/new-alignment")
    assert asr._resolve_main_model_ref(get_settings()) == "small"
    assert asr._resolve_alignment_model_ref(get_settings()) == "org/new-alignment"


@pytest.mark.parametrize("change", ["audio", "model", "language", "alignment", "local_model", "legacy"])
def test_asr_cache_identity_rejects_changed_dependencies(backend_env, monkeypatch, change):
    from app.services import asr_whisperx as asr
    from app.services.asr_child_runner import run_asr_child
    from app.services.media_chunks import load_media_chunk_manifest
    task_id = _create_task("https://www.bilibili.com/video/BV1identityasr")
    audio = _prepare_media_chunk_fixture(Path(backend_env["data_dir"]), task_id)
    local_model = Path(backend_env["data_dir"]) / "local-model"
    local_model.mkdir()
    (local_model / "model.bin").write_bytes(b"model-one")
    monkeypatch.setenv("APP_WHISPERX_MODEL_NAME", str(local_model))
    fake = _FakeWhisperX(transcription_result={"segments": [{"start": 0, "end": 1, "text": "hello"}]}, aligned_result={"segments": [{"start": 0, "end": 1, "text": "hello"}]})
    monkeypatch.setattr(fake, "load_model", lambda *args, **kwargs: _FakeModel(fake.transcription_result))
    monkeypatch.setattr(asr, "_load_whisperx_module", lambda: fake)
    result = run_asr_child(task_id, 0)
    work = audio.parent.parent
    chunk = load_media_chunk_manifest(work / "media-chunks.json").chunks[0]
    assert asr.load_valid_asr_chunk_manifest(task_id, work_dir=work, chunk=chunk) is not None
    if change == "audio":
        audio.write_bytes(b"RIFFchanged")
    elif change == "local_model":
        (local_model / "model.bin").write_bytes(b"model-two")
    elif change == "legacy":
        payload = json.loads(result.manifest_path.read_text())
        payload.pop("cache_identity", None)
        result.manifest_path.write_text(json.dumps(payload))
    else:
        key = {"model": "MODEL_NAME", "language": "LANGUAGE", "alignment": "ALIGNMENT_MODEL_NAME"}[change]
        monkeypatch.setenv("APP_WHISPERX_" + key, "changed")
    assert asr.load_valid_asr_chunk_manifest(task_id, work_dir=work, chunk=chunk) is None


def test_child_revokes_success_before_overwriting_and_rejects_mutated_audio(backend_env, monkeypatch):
    from app.services import asr_whisperx as asr, asr_child_runner as child
    task_id = _create_task("https://www.bilibili.com/video/BV1mutateasr")
    audio = _prepare_media_chunk_fixture(Path(backend_env["data_dir"]), task_id)
    fake = _FakeWhisperX(transcription_result={"segments": [{"start": 0, "end": 1, "text": "hello"}]}, aligned_result={"segments": [{"start": 0, "end": 1, "text": "hello"}]})
    monkeypatch.setattr(asr, "_load_whisperx_module", lambda: fake)
    first = child.run_asr_child(task_id, 0)
    original = child.execute_asr_pipeline
    def mutate(**kwargs):
        assert not first.manifest_path.exists()
        result = original(**kwargs)
        audio.write_bytes(b"RIFFchanged")
        return result
    monkeypatch.setattr(child, "execute_asr_pipeline", mutate)
    result = child.run_asr_child(task_id, 0)
    assert result.status == "failed"
    assert json.loads(result.manifest_path.read_text())["status"] == "failed"


def test_merge_rejects_chunks_from_different_model_configurations(backend_env, monkeypatch):
    from app.services import asr_whisperx as asr
    from app.services.asr_child_runner import run_asr_child
    from app.services.media_chunks import build_media_chunk_manifest, write_media_chunk_manifest_atomically
    task_id = _create_task("https://www.bilibili.com/video/BV1mixedconfig")
    work = Path(backend_env["data_dir"]) / "tasks" / task_id / "work"
    manifest = build_media_chunk_manifest(2, work_dir=work, chunk_seconds=1)
    for chunk in manifest.chunks:
        chunk.audio_path.parent.mkdir(exist_ok=True)
        chunk.audio_path.write_bytes(b"RIFFfixture")
    write_media_chunk_manifest_atomically(work / "media-chunks.json", manifest)
    fake = _FakeWhisperX(transcription_result={"segments": [{"start": 0, "end": 1, "text": "hello"}]}, aligned_result={"segments": [{"start": 0, "end": 1, "text": "hello"}]})
    monkeypatch.setattr(asr, "_load_whisperx_module", lambda: fake)
    assert run_asr_child(task_id, 0).status == "success"
    monkeypatch.setenv("APP_WHISPERX_BATCH_SIZE", "4")
    assert run_asr_child(task_id, 1).status == "success"
    with pytest.raises(asr.AsrFailure, match="must be re-run"):
        asr.merge_asr_chunk_artifacts(task_id, work_dir=work, chunks=manifest.chunks)
    assert not (work / asr.ASR_AGGREGATE_MANIFEST_FILENAME).exists()
