# SERVICES KNOWLEDGE BASE

## OVERVIEW

Service layer bridges workstation queue/run/event state to the legacy media pipeline, with validated resumable chunks and constrained proofreading.

## WHERE TO LOOK

| Task | Location | Notes |
| --- | --- | --- |
| Workstation sources | `source_catalog.py` | Bilibili inspection, local roots, reference/copy source resolution |
| Queue mutations | `workstation_queue.py` | SQLite writer lock, revision conflicts, ordering, claims |
| Execution history | `workstation_runs.py` | `PipelineRun` lifecycle and `StageRun` projection from legacy stages |
| Durable events | `workstation_events.py` | transaction-bound publication, replay cursor, short-session SSE polling |
| Library lifecycle | `task_library_lifecycle.py` | metadata/tags, archive, requeue, guarded deletion |
| Stage orchestration | `task_runner.py` | retry/resume, execution context, run/event synchronization |
| Subprocess control | `pipeline_support.py` | logs, JSONL events, heartbeat, SIGTERM/SIGKILL |
| Cancel/force-kill | `task_control.py` | execution tokens and active process groups |
| ASR | `asr_whisperx.py`, `asr_child_runner.py` | WhisperX, ROCm fallback, manifest publishing |
| Ingest/media | `downloader.py`, `media_prep.py` | BBDown/yt-dlp, ffprobe/ffmpeg |
| Chunk contract | `media_chunks.py` | versioned contiguous media ranges, task-local WAV paths, atomic manifests |
| Translation | `translation_provider.py`, `translation_hf.py` | chunk cache validation, HF adapter, final publication |
| Proofreading | `proofread_deepseek.py` | bounded requests/retries, strict row identity/timing checks, safe audit data |
| Export encoding | `export_encoding.py` | CPU ffmpeg, Windows AMF path conversion and CPU fallback |
| Failure/recovery | `failure_codes.py`, `recovery_actions.py` | normalized stage codes and available recovery actions |
| Highlights | `highlights.py`, `highlight_scoring.py`, `scene_detection.py` | candidate generation and scene fallback |
| Artifacts/storage | `storage.py`, `subtitles.py`, `reporting.py`, `clip_export.py` | task dirs, SRT/JSON, report, exports |
| Runtime | `runtime_profile.py`, `runtime_diagnostics.py`, `runtime_capabilities.py`, `capability_checks.py` | profile detection and health payload |

## CONVENTIONS

- Preserve legacy and v2 mutation bridges: create/retry/control/worker transitions must keep applicable queue entries, run/stage projections, and public events synchronized.
- Acquire `begin_queue_mutation(session)` before related non-queue writes; queue helpers acquire SQLite `BEGIN IMMEDIATE` before reading mutable scheduling state.
- `publish_event()` stages durable events in the caller's transaction; do not commit events independently from their state changes.
- `iter_events()` serializes a page inside a short session, closes it, then yields/sleeps. Never hold a DB session for the stream lifetime.
- Use `ensure_task_dirs()`, `log_file_for_stage()` and `append_stage_log()`; register artifacts with `persist_artifact_metadata()`.
- Resume only validated media/ASR/translation chunk results; preserve atomic publication and source-global timestamp rebasing when merging.
- Proofreading may change text, never segment IDs or timestamps. Persist preproofread JSON/SRT diagnostics before the call; failed final publication must not delete them.
- Failure exceptions should expose stable `code` values; UI/recovery logic depends on them.
- Keep ASR structured events aligned with `ASR_PIPELINE_PHASES`: `model_load`, `vad`, `transcribe`, `align`, `persist`.

## ANTI-PATTERNS

- Do not remove dynamic/lazy imports that avoid circular dependencies or heavy optional imports.
- Do not bypass containment in `source_catalog._resolve_within_root()`, `storage.resolve_task_artifact_path()`, or chunk-path validation; symlink resolution matters.
- Do not treat a present chunk file as a valid cache or publish final subtitles after a proofreading validation failure.
- Do not alter process cancel/force-kill timing without `test_pipeline_support.py` and worker tests.

## TESTS

```bash
(cd backend && .venv/bin/python -m pytest tests/workstation/test_queue_service.py tests/workstation/test_run_projection.py tests/workstation/test_event_stream.py)
(cd backend && .venv/bin/python -m pytest tests/test_media_chunks.py tests/test_asr_whisperx.py tests/test_translation_failure_codes.py tests/test_proofread_deepseek.py)
(cd backend && .venv/bin/python -m pytest tests/test_task_runner.py tests/test_pipeline_support.py tests/test_worker_runtime_warnings.py)
(cd backend && .venv/bin/python -m pytest tests/test_highlights.py tests/test_export_encoding.py)
```

## NOTES

- Commands start at the repository root with the backend venv already prepared.
- `pipeline_support.py` imports `task_control` dynamically to avoid a circular dependency.
