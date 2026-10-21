# Phase-four and cumulative acceptance results

Date: 2026-10-21. Chinese counterpart: [第四阶段与累计验收结果](/Users/drm/project/nyaru-clipper/docs/phase4-improvement-results-2026-10-21.zh-CN.md). Original findings and separate closure requirements: [44-finding improvement plan](/Users/drm/project/nyaru-clipper/docs/code-improvement-plan-2026-10-20.md).

Status: #39 → #11 → #28 → #38 → #42 implemented in order, individually verified and cumulatively accepted together with the previous 18 corrections. **Final gate APPROVE, no blockers, codeQualityStatus WATCH; the current ledger is 23 accepted within recorded scope / 21 pending.** See the [final review](/Users/drm/project/nyaru-clipper/.omo/evidence/phase4-workstation-output-consistency-2026-10-21/final-gate.md). This is not an all-platform release acceptance.

## Corrections and individual checks

| ID | Current behavior | Verification |
| --- | --- | --- |
| #39 | Producer registration, legacy and v2 readiness share the stage/kind mapping and recognize actual `clip_export` outputs. Deleted files become missing in both projections. | 26 regressions / 74 related cases, real SQLite/HTTP; independent APPROVE. |
| #11 | Manual exports record a separate run and actual export stage without rewriting canonical history. Pending scheduling survives. Terminal failure/recovery requires persisted ownership; task changes during encoding reject publication. | 82 related cases; real FFmpeg/API 201→400→201 with old MP4 preserved on failure; fresh APPROVE after R1 correction. |
| #28 | Success reports publish after execution/cancellation validation and terminal state assignment. Failed diagnostics retain the primary exception. Write/registration/commit faults restore old output; error-log disk failure cannot prevent failure finalization. | 84 related cases, real runner/report downloads; fresh APPROVE after R28-1 correction. |
| #38 | The shared review component resets local state by taskId; late export callbacks invalidate only their owning task cache. | 21 related cases; real cached A/B navigation, delayed export, return/download and MP4 decode; independent APPROVE. |
| #42 | Inspection success, failure and busy state belong to source kind, raw URL and monotonic draft generation, including reopening an identical URL after discard. | 32 related cases; real browser late response preserves local selection and creates the correct local task; discard/reset/focus pass; independent APPROVE. |

Related suites overlap and are not added to full-suite totals. Individual red/green logs, diffs and reviews are in the [phase evidence directory](/Users/drm/project/nyaru-clipper/.omo/evidence/phase4-workstation-output-consistency-2026-10-21).

## Current cumulative evidence

- Final full backend: **1107 passed**, zero failures/errors/skips; one existing Starlette deprecation warning retained. The actual shared downstream entry passed **2 backend smoke cases, 244 frontend tests, TypeScript/Vite build and 17 workstation browser tests**, exit 0. The two smoke cases overlap full backend coverage.
- Base/CUDA/ROCm locked exports match; 51 base dependency pins match the prepared environment, with no dependency installation. Default Chromium and selected Chrome each pass one real case with explicit sandbox retained; invalid executable and zero-test selection fail as expected without browser fallback.
- All 89 application Python files in the current CPU Docker image match host hashes. Fresh/legacy migrations pass. Actual host/container SQLite contention produces health 200→503, task500→recovered200; real cache replacement/preservation checks pass.
- The current declared-environment macOS App build, strict deep codesign, frozen root/jobs HTTP200 and synthetic RS256 positive/negative checks pass. Eight bundled frontend files match current web/dist; 32 build dependencies match. CLI/frozen Companion wrappers each select and pass one smoke case. Five real Companion page workflows pass with zero page errors and 18 screenshots. Platform records contain 17 successful final commands and 22 scenarios. Strong #22 double-disk-fault/#23 malformed-receipt conditions are covered by current backend automation; manual scenarios supplement normal admission recovery/export downloads without claiming fault injection.
- Complete evidence: [platform QA](/Users/drm/project/nyaru-clipper/.omo/evidence/phase4-workstation-output-consistency-2026-10-21/platform-qa/phase4-platform-manual-qa.md), [23-item matrix](/Users/drm/project/nyaru-clipper/.omo/evidence/phase4-workstation-output-consistency-2026-10-21/combined-acceptance.md), [root manual QA](/Users/drm/project/nyaru-clipper/.omo/evidence/phase4-workstation-output-consistency-2026-10-21/manual-qa-report.md). Earlier environment/fixture failures and both review-blocker red reproductions remain preserved, excluded from final passing receipts. Test servers are stopped, caller markers preserved and Docker Desktop restored to its initially stopped state.

## Preserved state and limits

Branch `codex/code-improvement-2026-10-21`, HEAD `e8ea71085cf5c6ff6f671499872f5c166d31f89b`. All corrections remain uncommitted; no push, merge or App installation. All 473 existing files were backed up; only authorized source/tests and paired documentation changed, with no missing/unexpected file. The original Companion's 99 hashes match and the index is empty. Unknown outputs, runtime data and original worktrees remain preserved.

The accepted-source candidate has 342 files and SHA256 `ab7192754f3a9be450ff214668b3ff13f9b9d5564843952ac5a6b5d8aec66b0f`; see the [frozen manifest](/Users/drm/project/nyaru-clipper/.omo/evidence/phase4-workstation-output-consistency-2026-10-21/final-source-manifest.json). HEAD alone cannot reproduce uncommitted corrections.

This is not acceptance of CUDA/ROCm/GPU pipelines, actual Bilibili/translation/ASR providers, installed native quit, complete business Compose deployment or power-loss atomicity. Python LSP/full static checks were unavailable and not installed; actual TypeScript project compilation passed. Large test-module maintenance debt for #11/#39 remains WATCH. Synchronous file compensation assumes rollback filesystem operations remain available.

The remaining 21 IDs are #13, #14, #15, #16, #17, #18, #19, #24, #25, #26, #27, #29, #30, #31, #33, #34, #35, #36, #37, #40 and #41. This phase did not implement them.
