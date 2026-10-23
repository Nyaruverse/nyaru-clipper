# Phase Two: Release Validation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `subagent-driven-development` or `executing-plans` task by task. Check steps only after execution and evidence capture.

**Goal:** Resolve original findings #12, #32, #43 and #44 so dependency checks, database readiness, browser selection and release smoke report trustworthy results.

**Architecture:** Keep host `uv + pnpm` primary, Docker fallback and the independent macOS Companion. Reuse existing scripts/routes; establish dependency, health and browser contracts before integrating smoke. Accept all four findings separately.

**Tech Stack:** Python `>=3.11,<3.12`, Bash, uv, FastAPI, SQLite, React/TypeScript, pnpm `10.33.2`, Playwright and pytest.

Chinese counterpart with the same task interfaces, code and commands: [实施计划](/Users/drm/project/nyaru-clipper/docs/superpowers/plans/2026-10-21-phase2-release-validation.zh-CN.md). Sources: [original plan](/Users/drm/project/nyaru-clipper/docs/code-improvement-plan-2026-10-20.md), [phase-one results](/Users/drm/project/nyaru-clipper/docs/phase1-improvement-results-2026-10-21.md).

## Global Constraints

- Execution result: **all four implemented and freshly accepted together with phase one in the recorded scope; final gate APPROVE, no blockers,13 accepted/31 pending**. See [phase-two results](/Users/drm/project/nyaru-clipper/docs/phase2-improvement-results-2026-10-21.md) for actual commands/counts/platform limits. Baseline and proposed code preserve preparation-time design; checks indicate retained evidence. The full-platform rollout checkbox remains open.
- Continue `/Users/drm/project/nyaru-clipper`, branch `codex/code-improvement-2026-10-21`. Preserve every uncommitted phase-one change/document and the original Companion worktrees; no reset or reimport.
- Preparation added plans/preflight records only. The user subsequently authorized this implementation and isolated temporary validation. No app installation, business services/recording/monitoring, commit, push or merge.
- Implementation uses disposable DB/media/ports/data, synthetic inputs and no real account/provider. Override Compose's existing `../data` mounts before isolated acceptance.
- Retain trusted local/LAN, single-user, single-GPU-worker architecture; no public authentication or GPU redesign.
- Never hand-edit generated requirements/OpenAPI/types, introduce incidental runtime upgrades or weaken failing assertions.
- Preserve per-finding red/green, actual-surface evidence and limits. A nonempty test list does not establish a browser/release pass.
- Maintain paired operational docs. Local reviewable delivery does not authorize publication or app installation.

## Verified starting point

On 2026-10-21, branch above at HEAD `e8ea71085cf5c6ff6f671499872f5c166d31f89b`, 181 dirty entries. `backend/.venv` is absent; the isolated phase-one evidence interpreter remains executable. Older handoff app/runtime snapshots are historical.

Phase-one historical acceptance: 290 targeted passes; full backend 970 passes/one failure, not rerun during preparation. The remaining test assumes a real checkout `.venv`; make its interpreter-preference fixture self-contained under #32 without deleting/skipping it.

| ID | Source observation at preparation | Deliverable | Preparation state |
| --- | --- | --- | --- |
| #32 Medium | Checks compile into fresh temporary outputs; installers resolve all three profiles | Pin-constrained validation, explicit upgrade, selected-profile checks | planned |
| #43 Medium | Health obtains an engine without querying; Compose probes `/` | Bounded real DB readiness and consistent consumers | planned |
| #44 Low | Browser path is in `use.executablePath` | Correct `use.launchOptions.executablePath`, observed browser launch | planned |
| #12 Medium | Shared smoke selects missing `e2e/task-flow.spec.ts` | Current workstation tests and a separate Companion delivery smoke | planned |

Only discovery ran: five existing workstation files list **17 tests**, no browser launched. [List evidence](/Users/drm/project/nyaru-clipper/.omo/evidence/phase2-preparation-2026-10-21/workstation-test-list-corrected.log). An earlier root-directory Corepack invocation selected system pnpm and failed; preserve that log. Run Corepack inside `web/` to select the pinned version; do not change global configuration or disable version checks.

## Order and contracts

**#32 → #43 → #44 → #12 → integration acceptance**. #43/#44 may run independently with assigned ownership; #12 must not concurrently edit the browser configuration with #44.

- `pyproject.toml` defines requirements/profiles; the three checked-in generated requirements files define fixed runtime versions for their installation paths. `uv.lock` keeps its development-environment role; do not silently replace runtime pins with its different versions.
- Proposed exporter interface: `--check --profile base|linux-cuda|wsl-rocm|all`; explicit `--upgrade` alone may select new versions. Default profile remains all; `--output PATH` remains base-only.
- Keep `/api/health` as readiness: DB readable → HTTP200, `status=ok,database=ok`; unavailable → HTTP503, `status=error,database=error`. Preserve runtime summary and normal fields; GPU warnings remain visibility-only.
- Workstation uses Vite and existing specs. Companion uses its own backend-served same-origin UI/API and separate Playwright config without Vite webServer.

### Task 1: #32 deterministic pinned validation

**Files:** Modify `/Users/drm/project/nyaru-clipper/scripts/export_backend_requirements.sh`, `/Users/drm/project/nyaru-clipper/scripts/_backend_profile_common.sh`, `/Users/drm/project/nyaru-clipper/backend/tests/test_requirements_export.py`; update both deployment guides and `scripts/AGENTS.md`. Regenerate requirements only through the script if necessary; preserve runtime versions by default.

**Interfaces:** Existing declarations/pins/Python3.11 in; exit status/generated files out. Installer passes its profile. Check writes temporary outputs only and never invokes an unselected profile compiler.

- [x] Build an isolated checkout fixture containing the real script, declarations and pins. Its `.venv/bin/python` wrapper executes `shlex.quote(sys.executable)`; PATH `python3` exits77. Prove venv preference, explicit `BACKEND_PYTHON` priority and clear missing-interpreter failure without modifying the actual checkout venv.
- [x] Controlled uv fixture records argv and returns simulated newer versions only when unconstrained. Change visible latest versions between two checks: both must pass with fixed pins. Raise a copied declaration minimum beyond its pin: check must fail. Force ROCm resolution to fail: base/CUDA must not invoke it. Keep missing-file, comparison-drift and shared-pin assertions.
- [x] Add profile/upgrade parsing. Build constraints from authoritative existing pins **before** resolution, not from freshly resolved output. Strip comments/project/index options from constraints; keep existing ROCm index configuration. Core base invocation:

  ```bash
  compile_args=()
  if ((UPGRADE)); then
    compile_args+=(--upgrade)
  else
    write_constraints_file "${DEFAULT_OUTPUT_PATH}" "${GENERIC_CONSTRAINTS_PATH}"
    compile_args+=(--constraints "${GENERIC_CONSTRAINTS_PATH}")
  fi
  uv pip compile "${GENERIC_INPUT_PATH}" --project "${BACKEND_DIR}" \
    --python-version 3.11 --python-platform x86_64-unknown-linux-gnu \
    --no-header --no-annotate "${compile_args[@]}" >"${GENERIC_RAW_PATH}"
  ```

  Profile compilers also constrain their own fixed artifact. Check base plus selected profile, reject conflicting shared pins and `--check --upgrade`. `--output` implies base and rejects an explicit non-base profile. Upgrade compiles base first, then builds profile constraints from the candidate base. Missing pins require explicit bootstrap/upgrade. Fixed metadata/cache may still be required: do not claim empty-cache offline support. Updating base pins explicitly requires consistent regeneration of all three artifacts.
- [x] Installer calls `bash "${ROOT_DIR}/scripts/export_backend_requirements.sh" --check --profile "${profile_name}"`; retain venv-before-check-before-sync and WSL HIP build ordering. Run:

  ```bash
  cd /Users/drm/project/nyaru-clipper
  PYTHONPATH=backend .omo/evidence/phase1-improvement-2026-10-21/venv/bin/python -m pytest backend/tests/test_requirements_export.py -q
  BACKEND_PYTHON="$PWD/.omo/evidence/phase1-improvement-2026-10-21/venv/bin/python" ./scripts/export_backend_requirements.sh --check --profile base
  ./scripts/install_backend_linux_cuda.sh --dry-run
  ./scripts/install_backend_wsl_rocm.sh --dry-run
  ```

  Require passing checks, unchanged artifact hashes in check mode and no unselected solver calls; retain red/green, versions, argv and hashes.

### Task 2: #43 bounded database readiness

**Files:** `/Users/drm/project/nyaru-clipper/backend/app/api/routes/health.py`, `/Users/drm/project/nyaru-clipper/backend/tests/test_runtime_api.py`, `/Users/drm/project/nyaru-clipper/scripts/dev_up.sh`, `/Users/drm/project/nyaru-clipper/scripts/_release_smoke_common.sh`, `/Users/drm/project/nyaru-clipper/infra/docker-compose.yml`, paired deployment/operator docs. Regenerate OpenAPI/types with existing generators if a documented503 changes the schema.

**Interfaces:** `healthcheck(response: Response) -> dict[str, object]`; private `_database_is_readable() -> bool`. A separate read-only persistent-SQLite connection avoids stale engine/file handles and leaves business-session timeouts unchanged.

- [x] Prove healthy200 → real temporary DB directory unavailable503 → restored200, disposing business connections for the fault. Test a real exclusive SQLite lock with a one-second busy timeout and failure under two seconds. Missing DB/table fails without creating a file. Response must not expose URL/path/raw exception.
- [x] Parse `make_url(get_database_url())`; open `Path(...).resolve().as_uri() + '?mode=ro'` with `sqlite3.connect(uri=True, timeout=1.0)` and `contextlib.closing`. Query:

  ```python
  connection.execute("SELECT 1 FROM task LIMIT 1").fetchone()
  ```

  Empty table is healthy. Catch `sqlite3.Error`, `OSError`, URL `ValueError` and return false. Current product uses persistent SQLite: unsupported in-memory/other dialects must report not-ready rather than querying a different newly created DB. Set `response.status_code = 503` on failure; retain runtime summary. Do not claim write/capacity checks.
- [x] Compose API probe changes `/` to `/api/health`; startup/smoke require successful HTTP plus status/database ok, retaining bounded waits and process cleanup. Do not introduce another ambiguous health URL.
- [x] Run `PYTHONPATH=backend .omo/evidence/phase1-improvement-2026-10-21/venv/bin/python -m pytest backend/tests/test_runtime_api.py -q`; then actual temporary uvicorn healthy/fault/recovery HTTP, timing and consumer status. Repeat in an isolated container before claiming container acceptance.

### Task 3: #44 browser executable selection

**Files:** `/Users/drm/project/nyaru-clipper/web/playwright.config.ts`, paired deployment docs. No application UI or personal browser changes.

**Interfaces:** Same `PLAYWRIGHT_CHROME_EXECUTABLE`; unset retains bundled Chromium behavior.

- [x] Capture effective project `use.launchOptions` through a disposable reporter's `onBegin(config)`, showing the pre-fix omission without dumping environment values.
- [x] Replace only the existing spread:

  ```typescript
  ...(chromeExecutablePath === undefined
    ? {}
    : { launchOptions: { executablePath: chromeExecutablePath } }),
  ```

- [x] Observe actual launch, trace and process exit using:

  ```bash
  cd /Users/drm/project/nyaru-clipper/web
  PLAYWRIGHT_CHROME_EXECUTABLE='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' DEBUG=pw:browser corepack pnpm exec playwright test e2e/workstation-shell.spec.ts -g 'declares Chinese' --reporter=line
  env -u PLAYWRIGHT_CHROME_EXECUTABLE corepack pnpm exec playwright test e2e/workstation-shell.spec.ts -g 'declares Chinese' --reporter=line
  ```

  Only the system Chrome file was verified during preparation; default-browser availability is unproven. Prepare the pinned runner's browser dependency if needed. Test an invalid path produces a clear failure without fallback. Use temporary profiles, keep the sandbox, and do not treat `--list` or `browserType.executablePath()` as proof of the override.

### Task 4: #12 workstation and Companion release smoke

**Files:** Modify `/Users/drm/project/nyaru-clipper/scripts/_release_smoke_common.sh` and affected smoke entries. Create `/Users/drm/project/nyaru-clipper/backend/tests/test_release_smoke_scripts.py`, `/Users/drm/project/nyaru-clipper/scripts/release_smoke_companion.sh`, `/Users/drm/project/nyaru-clipper/web/playwright.companion.config.ts`, `/Users/drm/project/nyaru-clipper/web/e2e/companion-release.spec.ts`; update paired deployment docs and `scripts/AGENTS.md`. These new paths are planned, not existing artifacts.

**Interfaces:** Preserve `run_downstream_smoke_suite()` and error propagation. Companion accepts disposable root and optional frozen backend, using its own loopback port/origin.

- [x] Exercise the actual shell helper with disposable executable wrappers: backend/unit/build/browser failures propagate nonzero and prevent subsequent stages; empty runner selection is nonzero. Never pass with no tests. All failure paths clean only owned processes/fixtures.
- [x] Keep full frontend unit/build steps; replace missing task-flow spec with the five observed files. Do not hardcode the snapshot count17. Main config ignores `**/companion-release.spec.ts` after adding that spec. Use the prepared interpreter for backend pytest instead of `uv run` implicitly syncing dependencies.

  ```bash
  pnpm --dir "${ROOT_DIR}/web" exec playwright test \
    e2e/workstation-shell.spec.ts e2e/workstation-task-create.spec.ts \
    e2e/workstation-queue.spec.ts e2e/workstation-task-overview.spec.ts \
    e2e/task-library-controls.spec.ts --reporter=line
  ```

- [x] Companion script starts existing `python -m app.arctime.cli gui`, with an owned temporary `--output-dir` and loopback `--port`, against the built frontend. Use Task1's verified interpreter and `PYTHONPATH=/Users/drm/project/nyaru-clipper/backend`. Allocate a free loopback port using a Python socket; fail explicitly if binding loses the race. Wait for real `/companion-api/jobs` and terminate/wait its child on exit, never using default data. Frozen macOS mode uses existing `--data/--ready/--parent-pid`, never the installed app. Separate Playwright config reuses main `use`, sets origin/testMatch, omits Vite webServer. Test:

  ```typescript
  import { expect, test } from "@playwright/test";

  test("Companion serves its jobs and settings from the actual backend", async ({ page, request }) => {
    const jobs = await request.get("/companion-api/jobs");
    expect(jobs.ok()).toBe(true);
    expect(await jobs.json()).toEqual([]);
    const settings = await request.get("/companion-api/studio-settings");
    expect(settings.ok()).toBe(true);
    await page.goto("/");
    await page.getByRole("button", { name: "设置", exact: true }).click();
    await expect(page.getByRole("heading", { name: "设置中心" })).toBeVisible();
    await page.getByRole("button", { name: "返回工作区" }).click();
    await expect(page.getByRole("button", { name: "设置", exact: true })).toBeVisible();
  });
  ```

  No mocks for its same-origin jobs/settings. No task creation, model call or real auth; keep existing Companion backend/frontend regression suites separately.
- [ ] Execute each supported host/WSL/Docker entry and the separate Companion entry, recording actual browser and overall exit status after discovery. Workstation E2Es mostly mock API: do not claim live downloads/ASR. macOS without `setsid` can run supported components/Companion only; Linux/container results never substitute for real WSL GPU acceptance.

## Integration acceptance and delivery

- [x] Independent red/green and matching workflow for all four IDs; smoke alone cannot close four findings.
- [x] #32's old interpreter-preference failure is self-contained and passes; no phase-one environment exemption at phase-two closure.
- [x] Alongside quick regressions in the phase-one interpreter, create isolated `.omo/evidence/phase2-release-validation-2026-10-21/venv` from the actual fixed base requirements, add exact test dependencies `pytest==8.4.2`, `pytest-asyncio==0.26.0` and Companion's declared `yt-dlp==2026.8.19`, run `uv pip check` and acceptance tests, and verify runtime pins were preserved. Development-environment versions do not substitute for runtime-artifact acceptance.
- [x] Rerun the phase-one290 file scope, full backend, frontend type/build and affected browser cases; report actual new counts, never skip/delete old failures. On macOS use `/tmp` for the existing Linux-temp assertion rather than refactoring unrelated tests.
- [x] Save commands/versions/exit codes/JUnit/traces/screenshots/timings/hashes to `.omo/evidence/phase2-release-validation-2026-10-21/`, excluding secrets. Separate observed/not-run by Linux/CUDA, WSL/ROCm, Docker and macOS.
- [x] Paired master plan/results updated after actual acceptance: **13 accepted/31 pending** within the recorded scope, with evidence and final APPROVE retained. Nine accepted plus four planned describes historical preparation, not the current result.
- [x] Verify protected worktrees/source and dirty changes remain; deliver reviewable local diffs with no automatic commit/push/install.

Historical preparation acceptance required verified entry points/boundaries/executable steps/independent criteria, valid links and no product-source edits during preparation. Subsequent implementation is recorded above. The full-platform rollout checkbox remains open: this host ran shared components, Docker CPU database checks and actual CLI/frozen Companion, without full Linux CUDA/WSL ROCm/business Compose GPU stacks.
