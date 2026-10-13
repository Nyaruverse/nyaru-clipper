# BACKEND TESTS KNOWLEDGE BASE

## OVERVIEW

Pytest regressions for legacy/v2 APIs, queue/run/events, migrations, pipeline/media/ML boundaries, and generated contracts. Configuration is in `backend/pyproject.toml`.

## WHERE TO LOOK

| Task | Location | Notes |
| --- | --- | --- |
| API behavior | `test_tasks_api.py`, `test_runtime_api.py`, `test_clip_export_api.py`, `test_retry_api.py` | TestClient + temp DB/data |
| Pipeline | `test_task_runner.py`, `test_e2e_pipeline.py`, `test_retry_resume.py` | canonical stage order and retry state |
| Process control | `test_pipeline_support.py`, `test_worker_runtime_warnings.py` | task_control shims, heartbeat, cancel/kill |
| ASR/runtime | `test_asr_whisperx.py`, `test_runtime_capabilities.py`, `test_runtime_doctor.py` | fake ML deps and runtime matrices |
| Media/features | `test_downloader.py`, `test_media_prep.py`, `test_highlights.py`, `test_clip_export.py` | subprocess and artifact fixtures |
| Workstation queue | `workstation/test_queue_api.py`, `workstation/test_queue_service.py` | revision conflicts, ordering, scheduling transitions |
| Workstation library/run/events | `workstation/test_task_library_api.py`, `workstation/test_task_library_repository.py`, `workstation/test_run_projection.py`, `workstation/test_event_stream.py` | typed projections and durable events |
| Source/create | `workstation/test_source_catalog.py`, `workstation/test_task_create_api.py` | local-root containment and v2 creation |
| Migrations | `workstation/test_domain_migration.py`, `test_schema_migration.py` | idempotency, legacy backfill, failed-startup recovery |
| Chunk/proofread/export | `test_media_chunks.py`, `test_proofread_deepseek.py`, `test_translation_failure_codes.py`, `test_export_encoding.py` | integrity, stable failures, AMF/CPU fallback |
| Tooling | `test_requirements_export.py` | root-relative shellouts, requirements/installers, deterministic OpenAPI and checked-in contract |
| Temp environment | `test_pytest_environment.py`, `../sitecustomize.py` | inherited WSL /mnt temp paths; Linux assertions |

## CONVENTIONS

- Fixtures are file-local (`backend_env`, `client`, or inline setup); no shared `conftest.py` exists.
- Set `APP_DATA_DIR` and `APP_DATABASE_URL` to `tmp_path` before importing/initializing app modules that use runtime state.
- Reuse the file's `_reset_runtime_state()` pattern or `reset_db_runtime()` when switching databases; the DB engine is cached.
- Monkeypatch environment and fake modules before importing `app.*` under test.
- External tools/ML libraries are faked with `monkeypatch.setattr`, `subprocess.run` stubs, or `sys.modules` shims.
- Assert DB state through `session_scope()` and `sqlmodel.select(...)` when behavior affects persisted rows.
- There are no custom pytest markers; target by file path. `asyncio_mode = "auto"` covers asynchronous tests.
- Workstation fixtures use temporary SQLite state; verify conflict snapshots and queue/run/event effects together with legacy rows.

## ANTI-PATTERNS

- Do not initialize persistent app state before env monkeypatches in tests that require temporary storage.
- Do not replace fake ML/tool shims with real model/tool downloads.
- Do not delete heavy regression tests to make smoke faster.

## COMMANDS

Run from repository root after preparing the backend environment:

```bash
(cd backend && .venv/bin/python -m pytest)
(cd backend && .venv/bin/python -m pytest tests/workstation)
(cd backend && .venv/bin/python -m pytest tests/test_media_chunks.py tests/test_asr_whisperx.py tests/test_task_runner.py)
(cd backend && .venv/bin/python -m pytest tests/test_proofread_deepseek.py tests/test_translation_failure_codes.py tests/test_export_encoding.py)
(cd backend && .venv/bin/python -m pytest tests/test_requirements_export.py)
```

## NOTES

- `test_task_runner.py` and `test_asr_whisperx.py` are intentionally large regression suites.
- `test_requirements_export.py` validates root-relative generated requirements behavior; preserve repo-root shellout assumptions.
- `test_pytest_environment.py` currently asserts `/tmp`-based Linux paths without a platform guard; a macOS full-suite result has this portability limit.
- Tooling tests can invoke dependency resolution. Unit/pipeline stubs do not establish live provider or GPU acceptance.
