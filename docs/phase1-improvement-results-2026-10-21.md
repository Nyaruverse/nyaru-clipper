# Phase-one implementation record

Date: 2026-10-21. Chinese counterpart: [第一阶段实施记录](/Users/drm/project/nyaru-clipper/docs/phase1-improvement-results-2026-10-21.zh-CN.md).

This record preserves the historical phase-one result. See [phase-two and combined results](/Users/drm/project/nyaru-clipper/docs/phase2-improvement-results-2026-10-21.md) for the later #32 interpreter-test/exporter fixes and fresh acceptance across both phases. The 970/1 result below belongs to that earlier run.

Scope: nine findings #1–7, #20 and #21 from the [improvement plan](/Users/drm/project/nyaru-clipper/docs/code-improvement-plan-2026-10-20.md). Branch `codex/code-improvement-2026-10-21`; HEAD remains `e8ea71085cf5c6ff6f671499872f5c166d31f89b`. Changes are uncommitted.

Status: **all nine implemented and accepted within the observations recorded below; final review APPROVE, no blockers.** The [gate report](/Users/drm/project/nyaru-clipper/.omo/evidence/phase1-improvement-2026-10-21/final-gate-review.md) records individual judgments and limits. The other 35 findings remain pending; this is not full release acceptance.

| Item | Implemented and observed behavior | Evidence |
| --- | --- | --- |
| #1 Credentials | Opt-in sanitation covers download arguments, logs, failures and returned metadata; escaped JSON secrets are removed while numeric fields retain their values | [Logs/process report](/Users/drm/project/nyaru-clipper/.omo/evidence/phase1-improvement-2026-10-21/logs-processes-report.md) |
| #2 Processes | Registration, callbacks, logging, persistence and cancellation faults reap/wait the group before clearing tracking; failed cleanup retains tracking/GPU guard; recovery retries transient EPERM within a bound | [Process report](/Users/drm/project/nyaru-clipper/.omo/evidence/phase1-improvement-2026-10-21/logs-processes-report.md), [queue report](/Users/drm/project/nyaru-clipper/.omo/evidence/phase1-improvement-2026-10-21/queue-report.md) |
| #4 Finished video | Encode to a same-directory temporary file and publish atomically; encoder/empty-output/persistence failures preserve the prior video and concurrent writers are rejected | [Actual API/FFmpeg workflow](/Users/drm/project/nyaru-clipper/.omo/evidence/phase1-improvement-2026-10-21/clip-export-workflow.txt) |
| #20 Terminal queue | Task/job/run/queue terminal state commits together; a real child interruption permits the next claim; legacy repair handles missing/finished run history | [Queue report](/Users/drm/project/nyaru-clipper/.omo/evidence/phase1-improvement-2026-10-21/queue-report.md), [review](/Users/drm/project/nyaru-clipper/.omo/evidence/phase1-improvement-2026-10-21/queue-final-review.md) |
| #21 Rejection | Locked validation precedes mutations; rejected batch items/rollback preserve rows and bytes; durable accepted cleanup retries safely and delayed callbacks preserve newer outputs | [Transaction/filesystem evidence](/Users/drm/project/nyaru-clipper/.omo/evidence/phase1-improvement-2026-10-21/queue-report.md) |
| #3 Cache identity | Validate source/audio/conversion parameters/local model content; rebuild identityless legacy cache and rewind invalid resume dependencies; preserve user documents and exports | [Real replacement result](/Users/drm/project/nyaru-clipper/.omo/evidence/phase1-improvement-2026-10-21/cache-live/result.json), [report](/Users/drm/project/nyaru-clipper/.omo/evidence/phase1-improvement-2026-10-21/cache-report.md) |
| #5 Translation publication | Reconstruct exact expected bytes from verified inputs/batches after publication-before-checkpoint interruption; accept only matching output, reject corruption/identity mismatch/unknown files | [Recovery and legacy regressions](/Users/drm/project/nyaru-clipper/.omo/evidence/phase1-improvement-2026-10-21/translation-recovery-report.md), [review](/Users/drm/project/nyaru-clipper/.omo/evidence/phase1-improvement-2026-10-21/translation-final-review.md) |
| #6 macOS dependencies | Declare httpx and PyJWT crypto; a declared-build-dependencies-only environment builds the app, the actual frozen backend starts, and a separate frozen probe verifies valid/invalid RS256 | [Build report](/Users/drm/project/nyaru-clipper/.omo/evidence/phase1-improvement-2026-10-21/macos-build-report.md), [review](/Users/drm/project/nyaru-clipper/.omo/evidence/phase1-improvement-2026-10-21/macos-final-review.md) |
| #7 Docker migrations | Include Alembic configuration/version directories; actual image boots fresh and legacy DBs, serves HTTP, reaches migration head and retains old rows | [Actual image result](/Users/drm/project/nyaru-clipper/.omo/evidence/phase1-improvement-2026-10-21/docker-integrated-migrations.log), [review](/Users/drm/project/nyaru-clipper/.omo/evidence/phase1-improvement-2026-10-21/docker-review.md) |

## Validation and existing environment limitation

Final combined phase-one acceptance: **290 passed**. The [complete backend run](/Users/drm/project/nyaru-clipper/.omo/evidence/phase1-improvement-2026-10-21/backend-final.log): **970 passed / 1 failed**, with one existing Starlette deprecation warning. The Linux downloader/process suite passed 38 tests. Recovery permission fixes passed 60 checks and five repeated runs. Independent reviews also reran 67 cache, 31 translation and 36 legacy-stage repair cases. Counts describe overlapping suites and must not be added as a unique test total.

The full-backend requirements export test assumes `backend/.venv`, which was already absent before this work. Tests use an isolated evidence environment; that test and the exporter script are unchanged. A separate generated-file check passed with preserved version constraints and an explicit Linux target; lock validation passed. These facts do not mean the complete backend suite is green.

## Source reconciliation and preservation

To carry #5/#6 on one branch, synchronized 99 current macOS Companion baseline entries plus one ASS test helper. Review that baseline import separately from the fixes. The [SHA256 manifest](/Users/drm/project/nyaru-clipper/.omo/evidence/phase1-improvement-2026-10-21/companion-baseline-manifest.json) records original contents. Original C/B branches, HEADs and 56/53 dirty entries remain; all 99 original C hashes still match. Existing root documents/untracked work remain, and pre-update plans are backed up.

No commit, push, merge or app installation; no real credentials, business DB or provider used. Build outputs, disposable DB/media and logs are in the evidence directory. Docker Desktop was started for real-image validation; verification images/build caches remain.

## Acceptance limits and continuation

No real GPU, CUDA/ROCm/AMF, real download/login, native-window interaction or power-loss durability acceptance. Unresolved remote model refs cannot identify same-name repository updates offline; in-place FFmpeg replacement is not pinned by binary contents. Full hashes add disk reads. Fixed cache identity dictionaries still have a static-typing maintenance opportunity.

Keep the other 35 original IDs and acceptance criteria. Continue with validation entry points and remaining recovery/visible behavior work in the original plan. The candidate and evidence are reviewable; release requires separate target-platform acceptance.
