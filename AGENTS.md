# Cross-project persistent memory

For non-trivial tasks that may depend on the user's long-term preferences, prior decisions, or project history, start at:

`/Users/drm/Library/CloudStorage/OneDrive-个人/obsidian/Codex-Memory/00-System/Start Here.md`

1. Read `Start Here.md` first, then apply `Memory Policy.md`.
2. Match the working directory, project aliases, and task keywords through `Codex-Memory/02-Projects/Projects Index.md`.
3. Read the smallest relevant set, normally 4 to 6 files: relevant profile notes plus the matched project's Overview, latest Progress, Backlog, and Decisions only when historical rationale is needed.
4. Do not bulk-read Daily, Weekly, or Archive. Expand only for deeper evidence and state why.
5. Missing memory is not evidence of no history or progress. Re-verify volatile facts live.
6. After change tasks, record only durable, verified goals, decisions, progress, blockers, or next actions. Answer-only requests, diagnosis, and read-only audits do not change project memory unless explicitly requested.
7. Before memory writes, enforce `Memory Policy.md`: never store passwords, keys, tokens, cookies, verification codes, recovery codes, reusable credentials, secret environment values, or unredacted sensitive information. Preserve hand-written content and log conflicts rather than overwriting it.

# PROJECT KNOWLEDGE BASE

**Verified:** 2026-10-09 (Asia/Shanghai)
**Commit / Branch:** unavailable; this local directory has no usable Git metadata.

## OVERVIEW

Nyaru-Clipper is a trusted-LAN, single-GPU VOD workstation with a FastAPI/SQLModel backend and React/TypeScript UI. It accepts ended Bilibili VODs or configured local sources, runs chunked WhisperX ASR and Chinese-to-Japanese translation/proofreading, optionally scores highlights, and exports user-approved clips.

## STRUCTURE

```text
nyaru-clipper/
├── backend/        # legacy + v2 API, queue/events, Alembic, pipeline, pytest
├── web/            # workstation UI + shared legacy review, generated API types
├── docs/           # English / zh-CN operational and user docs
├── infra/docker/   # fallback Docker runtime only
├── scripts/        # uv/pnpm install, dev, smoke, requirements export helpers
├── data/           # runtime state/cache/artifacts; do not hand-edit
└── .sisyphus/      # workflow evidence and notepads; not live runtime state
```

## WHERE TO LOOK

| Task | Location | Notes |
| --- | --- | --- |
| Start API | `backend/app/main.py` | FastAPI app, lifespan init, CORS, router mount |
| Worker lifecycle | `backend/app/worker.py` | single GPU-bound worker, stale-job recovery |
| Task schema/status | `backend/app/models.py` | legacy task tables + workstation sources/queue/runs/events |
| HTTP contracts | `backend/app/api/routes/`, `backend/app/api/schemas/workstation.py` | legacy `/api/tasks` and typed `/api/v2` |
| Migrations | `backend/app/db_migrations.py`, `backend/alembic/` | startup upgrade and metadata backfill |
| Queue/events/library | `backend/app/services/workstation_*.py`, `backend/app/repositories/workstation.py` | scheduling, durable events, typed projections |
| Pipeline orchestration | `backend/app/services/task_runner.py` | stage order, retry/resume, execution context |
| ASR pipeline | `backend/app/services/asr_whisperx.py` | WhisperX/ROCm fallback/manifest/artifacts |
| Frontend entry | `web/src/main.tsx`, `web/src/App.tsx`, `web/src/router.tsx` | React root, query client, routes |
| Workstation UI | `web/src/workstation/` | library, queue, creation drawer, task overview, SSE |
| API client/types | `web/src/workstation/api/client.ts`, `web/src/generated/api-schema.ts`, `web/src/lib/api.ts` | generated v2 client + shared legacy review API |
| Deployment path | `docs/deployment-guide.md` | primary uv+pnpm path; Docker fallback |
| Operator rules | `docs/operator-manual.md` | LAN-only, single-worker, storage/runtime rules |
| Smoke/release | `scripts/release_smoke_*.sh`, `scripts/AGENTS.md` | host/profile contracts and current coverage limits |

## CODE MAP

Grounded in source and ast-grep. Python/TypeScript LSP servers are unavailable; semantic reference centrality is unmeasured for all rows.

| Symbol / Area | Type | Location | Role |
| --- | --- | --- | --- |
| `api_router` | FastAPI router | `backend/app/api/routes/__init__.py` | mounts legacy and workstation v2 routers |
| `CANONICAL_STAGES` | shared contract | `backend/app/models.py`, `web/src/lib/types.ts` | `ingest → media_prep → asr → translation → highlight → export → report` |
| `TaskExecutionControl` | DB model | `backend/app/models.py` | cancellation, force-kill, process-group tracking |
| `claim_next_job` | worker function | `backend/app/worker.py` | queue-driven claim with one-running-job guard |
| `begin_queue_mutation` | service function | `backend/app/services/workstation_queue.py` | SQLite writer lock before queue mutation |
| `upgrade_database` | migration function | `backend/app/db_migrations.py` | Alembic head + retryable metadata backfill |
| `run_task_pipeline` | orchestrator | `backend/app/services/task_runner.py` | executes/resumes stages, persists statuses |
| `run_tracked_structured_process_group_command` | process runner | `backend/app/services/pipeline_support.py` | JSONL progress, heartbeat, cancel/kill escalation |
| `transcribe_task_audio` / ASR helpers | ML service | `backend/app/services/asr_whisperx.py` | aligned transcript, subtitles, recovery metadata |
| `AppRouter` | UI route map | `web/src/router.tsx` | workstation entry + legacy task redirect |
| `WorkstationRouter` | nested routes | `web/src/workstation/routes/WorkstationRouter.tsx` | library, queue, task overview, dev showcase |
| `useWorkstationEvents` | React hook | `web/src/workstation/api/useWorkstationEvents.ts` | SSE invalidation, reconnect, polling fallback |

## CONVENTIONS

- Primary workflow is host `uv + pnpm`; Docker is fallback only.
- Python is `>=3.11,<3.12`; backend venv is expected at `backend/.venv`.
- Frontend package is isolated under `web/`; no root package/workspace config.
- `backend/requirements*.txt` are generated by `scripts/export_backend_requirements.sh`; never hand-edit them.
- Dev scripts configure repository `data/` for SQLite, task artifacts and model caches; raw Python defaults also probe `/data`.
- Keep backend/frontend `CANONICAL_STAGES` synchronized. V2 contracts generate `web/openapi.json` and `web/src/generated/api-schema.ts`; legacy shared types remain in `web/src/lib/types.ts`.
- Legacy review copy uses `web/src/lib/copy/`; workstation components also contain inline Chinese copy. No i18n framework exists.

## ANTI-PATTERNS (THIS PROJECT)

- Do not expose this app directly to the public internet; auth/TLS/rate limits/multi-user isolation are out of scope.
- Do not scale `worker` horizontally in MVP; assume one active GPU-bound worker.
- Do not treat `uv sync --project backend --frozen` as the Linux CUDA or WSL ROCm install contract; use the profile scripts.
- Do not edit `data/`, `.worktrees/`, virtualenvs, `node_modules`, `web/dist`, or test result artifacts as source.
- Do not download model weights during image build.
- Do not introduce Redis/Celery/Prefect in the first-pass MVP architecture.

## UNIQUE STYLES

- Docs are maintained as parallel English / zh-CN pairs: `name.md` and `name.zh-CN.md`.
- Runtime capability issues are visibility-first: warnings surface in health/worker logs but usually do not block startup.
- ASR progress is emitted as structured JSONL from a child process and mirrored to `execution_progress`.
- Failed ASR missing-model state exposes a recovery payload for the UI.

## COMMANDS

```bash
./scripts/install_backend_linux_cuda.sh
./scripts/install_backend_wsl_rocm.sh
pnpm --dir web install --frozen-lockfile
./scripts/dev_up.sh
./scripts/dev_api.sh
./scripts/dev_worker.sh
./scripts/dev_web.sh
./scripts/check_wsl_rocm.sh
./scripts/release_smoke_non_docker.sh
./scripts/release_smoke_wsl_rocm.sh
./scripts/release_smoke_docker.sh
./scripts/export_backend_requirements.sh --check
pnpm --dir web build
```

## NOTES

- `APP_BILIBILI_COOKIE_PATH` is a file path, not pasted cookie text.
- LAN browser access requires `VITE_API_BASE_URL=http://<host-ip>:8000/api` before starting web.
- If WSL doctor reports `hip_build_no_device`, follow `docs/deployment-guide.md` before changing project code.
- Release-smoke selection and platform coverage limits are documented in `scripts/AGENTS.md`.
- Child instructions: `backend/AGENTS.md`, `backend/app/services/AGENTS.md`, `backend/tests/AGENTS.md`, `web/AGENTS.md`, `web/src/workstation/AGENTS.md`, `docs/AGENTS.md`, `scripts/AGENTS.md`.
