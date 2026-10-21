# Phase-two implementation and combined acceptance

Date: 2026-10-21. Chinese counterpart: [第二阶段结果](/Users/drm/project/nyaru-clipper/docs/phase2-improvement-results-2026-10-21.zh-CN.md).

Status: **all four implemented; all 13 corrections across both phases pass this run's combined acceptance within the recorded scope, final gate APPROVE, no blockers; 31 findings remain pending.** Execution order is #32 → #43 → #44 → #12, retaining every ID from the [44-finding plan](/Users/drm/project/nyaru-clipper/docs/code-improvement-plan-2026-10-20.md). Phase one #1–7,#20,#21 and these four phase-two items were verified together again. Historical phase-one results do not replace this run's evidence.

## Source and data boundaries

Work continues in `/Users/drm/project/nyaru-clipper`, branch `codex/code-improvement-2026-10-21`, HEAD `e8ea71085cf5c6ff6f671499872f5c166d31f89b`. The initial 183 dirty entries and complete tracked patch were captured. No commit, push, merge or App installation occurred. Original Companion worktrees remain untouched; validation uses disposable data, databases, media and task-owned browser profiles.

Host `uv + pnpm` remains primary, Docker remains fallback, and macOS Companion has its own entry point. No real credentials, providers or business tasks were used.

Evidence: [phase2-release-validation-2026-10-21](/Users/drm/project/nyaru-clipper/.omo/evidence/phase2-release-validation-2026-10-21/). `ledger.md` and `combined-acceptance.md` track progress; red/green runs, JUnit, browser traces, source/artifact hashes and reviews are retained alongside them.

## Phase-two changes

| ID | Implementation and actual observation | Status |
| --- | --- | --- |
| #32 | Checks and normal generation constrain resolution from authoritative runtime pins; only `--upgrade` may change the pin set. Profile solving is isolated; changed base pins require regeneration of all profiles. Install helpers pass the current profile; interpreter-precedence tests use temporary checkouts. All 40 focused tests and real base/CUDA/ROCm checks pass; all three requirements hashes remain unchanged. A real unpinned addition is rejected. | Scoped review approved |
| #43 | An independent read-only SQLite connection queries the task table with a one-second lock timeout. Failure is 503; normal JSON and non-blocking GPU warnings are preserved. Development startup and smoke share HTTP/body checks; Compose probes `/api/health`. All 28 focused checks and shell syntax checks pass. Real host/container HTTP workflows observe 200 → exclusive-lock 503/tasks500 → restored200, with fault probes about 1.05/1.11 seconds. | Scoped review approved |
| #44 | Executable selection moves to `use.launchOptions.executablePath`. Actual selected Chrome and default Chromium pass; an invalid path fails without fallback. A temporary config inheriting the actual candidate explicitly enables `chromiumSandbox`; both browser runs pass again without `--no-sandbox` in launch records. | Scoped re-review approved |
| #12 | Shared entry uses the prepared Python and five current workstation specs; Companion has its own same-origin config/entry. Final nine behavior cases cover success, stage/startup/browser failures and TERM cleanup. Actual shared suite, CLI and frozen entries exit0; zero test selection exits1. | Scoped review approved |

The first #32 review reproduced a normal-generation path admitting unpinned additions; red/green and real uv evidence close it. The first #44 review identified Playwright's default `--no-sandbox`; supplementary sandbox-enabled validation closes that evidence gap without expanding product policy. Original failures and review reports remain available.

## Combined validation

A new isolated Python3.11.16 venv installs the actual base requirements plus only pinned test dependencies and Companion's declared yt-dlp. All 51 runtime pins match and `uv pip check` passes; a different development dependency set is not used as runtime acceptance.

| Scope | Current evidence and boundaries |
| --- | --- |
| Phase-one 290 focused checks | All 290 pass again against the current backend: secret redaction, process-group cleanup, cache identity, export protection, SRT publication recovery, dependencies, terminal state and retry cleanup. Counts overlap the full suite and are not added together. |
| Full backend/frontend/release smoke | Final full backend: **1030 passed** in 99.15s. Actual shared entry completes 2 backend smoke checks, **218 frontend tests/32 files**, project TypeScript/Vite build and **17 real browser scenarios**, exit0. CLI and newly frozen backend each pass one real same-origin Companion scenario; empty selection explicitly exits1. Suite counts overlap and are not added. |
| Actual cache/export workflows | Same-size/duration source replacement, real FFmpeg/ffprobe, SQLite, child publication and user-document preservation pass; WhisperX is a controlled fake. Actual API export/download/decode, failed reexport retaining the old SHA256 and successful retry pass. This does not claim an injected real DB commit failure. |
| Docker | A newly built current image migrates fresh/legacy disposable databases to `20260714_01`, starts HTTP and retains legacy task/stage diagnostics/queue rows. Independent readiness fault/recovery passes. Build context contains minimal source, without business data mounts. |
| macOS dependency/frozen backend | A new current App is built in the previously verified 32-package declared-build-dependency closure. Declared pins and `uv pip check` pass. Actual frozen root/empty-jobs endpoints return200 and deep strict signature verification passes. A separate frozen probe built in that environment imports the GUI and accepts/rejects synthetic RS256 signatures. This is not a real login. |
| Preservation | Complete initial tracked patch/status are retained; its read-only reverse-apply check passed before index edits. Final verification passes for source/other existing documents, excluding only the two README indexes intentionally updated with implementation status/links. All 99 original Companion C source hashes match. No original worktree was reset or deleted. |

## Platform and acceptance limits

The macOS host, Docker CPU containers and independent frozen backend have the observations above. Linux CUDA/WSL ROCm installers were dry-run only; dependency profiles received real solver checks, without GPU installation, doctor runs, actual download/ASR/provider tasks. macOS lacks `setsid`; supported components or Docker observations do not establish a complete Linux/WSL release stack.

Existing Starlette/httpx deprecation and browser/tool diagnostics are preserved. An extra isolated tsc command for Playwright config fails because `@types/node` is absent; it is outside the project tsconfig and no dependency was added. The declared-build environment intentionally has no pip: an attempted pip check failed, followed by successful `uv pip check`. LSP is unavailable and was not installed.

Actual entry invocations/statuses: [QA record](/Users/drm/project/nyaru-clipper/.omo/evidence/phase2-release-validation-2026-10-21/manual-qa-report.md) and [exit receipts](/Users/drm/project/nyaru-clipper/.omo/evidence/phase2-release-validation-2026-10-21/qa-exit-receipts.json). A [screenshot](/Users/drm/project/nyaru-clipper/.omo/evidence/phase2-release-validation-2026-10-21/companion-root.png) of the actual empty Companion workspace was saved and inspected; that capture service has stopped.

[Final gate](/Users/drm/project/nyaru-clipper/.omo/evidence/phase2-release-validation-2026-10-21/final-gate-review.md): **APPROVE, blockers=[], codeQualityStatus=WATCH**. It independently checked339 candidate source hashes,99 original Companion files and final JUnit. Frozen candidate digest: `4495d58d03df828b1e3aba8d532911305ce5c0c5ee5edd8feb2fc854e00142b7`. WATCH retains a static-typing maintenance note for cache identity dictionaries and existing tool warnings, without an established behavioral failure in the accepted scope.

Both #12 test-quality suggestions are resolved: redundant existence and exact command assertions were removed after all tests were green. The initial10 focused/1031 full-backend pass is retained; final nine behavior cases/1030 complete backend checks still pass. No preexisting failing test was removed. Product source is unchanged, so actual entry evidence remains applicable. Target-platform release acceptance remains outside these local observations.
