# BACKEND KNOWLEDGE BASE

## OVERVIEW

FastAPI + SQLModel package: legacy task execution and v2 workstation projections share SQLite state and the worker.

## STRUCTURE

```text
backend/
├── app/
│   ├── api/routes/      # legacy tasks + workstation v2 HTTP/SSE endpoints
│   ├── api/schemas/     # typed workstation transport contracts
│   ├── repositories/    # legacy serialization + workstation projections
│   ├── services/        # queue/run/event domain + media/ML pipeline
│   ├── main.py          # FastAPI entrypoint
│   ├── worker.py        # queue claims + legacy job checkpoints
│   ├── models.py        # task, queue, run, source, tag, event tables
│   ├── db_migrations.py # Alembic upgrade + metadata backfill
│   └── settings.py      # APP_ env settings
├── alembic/versions/    # workstation schema/data revisions
├── tests/               # pytest suite; see tests/AGENTS.md
└── pyproject.toml       # dependency + pytest source of truth
```

## WHERE TO LOOK

| Task | Location | Notes |
| --- | --- | --- |
| API startup | `app/main.py` | initializes task root, DB, runtime capability log |
| Env settings | `app/settings.py` | `APP_` settings; optional DeepSeek env file |
| DB/session | `app/db.py` | cached engine, `reset_db_runtime()`, session helpers |
| Migrations | `app/db_migrations.py`, `alembic/versions/` | upgrade before `create_all`; retryable metadata backfill |
| Workstation contracts | `app/api/schemas/workstation.py` | frozen Pydantic list/overview/recovery schemas |
| Workstation queries | `app/repositories/workstation.py` | filters, readiness, search, sanitized public projections |
| Legacy serialization | `app/repositories/tasks.py` | dict payloads, create/retry compatibility bridge |
| Routes | `app/api/routes/tasks.py`, `app/api/routes/workstation_*.py` | legacy HTTP and v2 tasks/sources/queue/events |
| Scheduling/checkpoints | `app/models.py`, `app/worker.py` | `QueueEntry`/`QueueState` schedule; `TaskJob` tracks execution |
| Runtime doctor | `app/runtime_doctor.py` | CLI-facing capability summary |

## CONVENTIONS

- Imports assume `backend/` on the Python path; run the commands below from the repository root with the backend venv already prepared.
- Ordinary DB routes use `Depends(get_session)` and commit mutations explicitly; worker units use `session_scope()`.
- Workstation repositories return typed schemas; legacy task serializers return JSON-ready dicts. Preserve both contracts.
- `utc_now()` from `models.py` is the timestamp source for persisted rows.
- `QueueEntry`/`QueueState` own scheduling order/revision; `TaskJob` retains checkpoint/recovery state and `TaskStage` the legacy stage projection.
- `get_settings()` rereads settings on each call; the DB engine is cached separately. Clear it with `reset_db_runtime()` when changing DB configuration in tests.
- `init_db()` runs Alembic and metadata backfill; table creation alone is not a schema upgrade.

## ANTI-PATTERNS

- Do not drop workstation projection sanitization: local absolute paths and operator configuration must not leak through visible text or artifact metadata.
- Do not impose request-scoped DB sessions on migrations or SSE; these own separate bounded sessions.
- Do not put ML/model imports at startup if they can stay lazy; optional deps must not break API boot.
- Do not hard-block startup on runtime warnings; health reports visibility instead.

## COMMANDS

```bash
(cd backend && .venv/bin/python -m pytest tests/workstation/)
(cd backend && .venv/bin/python -m pytest tests/test_schema_migration.py)
```

## NOTES

- Each command above starts at the repository root; service-specific tests are listed in `app/services/AGENTS.md`.
