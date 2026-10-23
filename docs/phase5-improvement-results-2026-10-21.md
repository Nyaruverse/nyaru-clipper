# Phase-five implementation and cumulative acceptance

Date:2026-10-21. [Chinese counterpart](/Users/drm/project/nyaru-clipper/docs/phase5-improvement-results-2026-10-21.zh-CN.md).

**Phase five and cumulative acceptance complete: independent gate APPROVE, no blockers, maintenance WATCH.** The requested **#37 → #24 → #19 → #30 → #27** were implemented in order, individually approved and freshly accepted together with the previous23 corrections. Current ledger: **28 accepted within recorded scope /16 pending**. [Final gate](/Users/drm/project/nyaru-clipper/.omo/evidence/phase5-subtitle-identity-and-export-boundaries-2026-10-21/final-gate.md). This bounded record does not close all44 findings or establish a full platform release.

Branch `codex/code-improvement-2026-10-21`, unchanged HEAD `e8ea71085cf5c6ff6f671499872f5c166d31f89b`; all changes remain uncommitted. The478 captured files,218 original Git status entries and99 original Companion source hashes are preserved. Phase5 changes8 existing source/test files, adds6 tests and updates paired documents. No commit, push, merge or App installation.

The348-file candidate digest is `4547225959352daf71f62e6d934ab1a00dde2e79c2b464b75847d076275a4bb2`. [Evidence ledger](/Users/drm/project/nyaru-clipper/.omo/evidence/phase5-subtitle-identity-and-export-boundaries-2026-10-21/ledger.md), [source manifest](/Users/drm/project/nyaru-clipper/.omo/evidence/phase5-subtitle-identity-and-export-boundaries-2026-10-21/final-source-manifest.json), [preservation receipt](/Users/drm/project/nyaru-clipper/.omo/evidence/phase5-subtitle-identity-and-export-boundaries-2026-10-21/preservation-final.json). HEAD alone cannot reproduce these uncommitted changes.

## Five corrections

| Order | Behavior and compatibility | Focused verification |
| --- | --- | --- |
| #37 | Content identity includes verified media/subtitles/effective bilingual content, timeline/canvas and clip mapping, excluding diagnostics. Proven legacy v1 fingerprints normalize on read; explicit saves preserve backups and revision/CAS. A content-bound proof before controlled auto-export diagnostic mutation covers legacy GET-without-POST/reopen. |100 related cases; independent APPROVE/WATCH, no blockers, extra17 cases. Actual read-only legacy GET, failure/retry and independent-process access/save pass. |
| #24 | Merge uses minimum start/maximum end, retaining text/style/document order. |30 related cases/build/review pass. Real UI edit/merge yields[0,8], autosaves revision3 and survives reload; preview/ASS/burn show both lines at0.5s. |
| #19 | Round total duration to integer tenths before splitting; parser unchanged. |68 related cases/build/review pass. Real59.99/3599.99 show01:00.0/01:00:00.0;00:60.0 rejected; valid actualHTTP/Pydantic range parses60/3600. Ingestion is stubbed, no download claim. |
| #30 | Filename validation accepts at least three digits, retaining path/task/completion/hash checks. |70 related cases/review pass; actual999/1000 manual edited ASS and automatic ASS/libass burn pass; saved draft/backup retained. No thousand-segment recording. |
| #27 | Only ArcTime reads/verifies/includes ATPJ; HTTP and shared runner normalize irrelevant ASS/burn project fields; frontend sends applicable fields. |123 related backend/41 frontend/build pass; stale cumulative ASS assertion updated with explicit ASS omission/ArcTime inclusion,13 related pass. Independent APPROVE/CLEAR; actual template switch/delete/invalidID, cache reuse, ZIP and downloads pass. |

#37 does not guess an already-unprovable opaque legacy hash. Such drafts retain409 and the explicit source recovery/reapply/backup flow. Equal canvas/duration is not proof; real media/subtitle/timeline changes still reject. GET does not silently rewrite saved bytes.

#27 keeps renderer_revision=2 and existing canonical no-project caches. Historical ASS/burn keys that incorrectly included a nonnull project may regenerate once on the first normalized request; old receipts and outputs remain SHA-verified/downloadable. Unknown historical inputs are never blindly aliased to new source. Current normalized requests preserve identity/SHA/mtime/registry count across project switch/deletion. ArcTime still rejects corrupt/deleted/invalid templates; its original optional-null semantics remain.

## Current cumulative verification

| Lane | Actual result this phase |
| --- | --- |
| Full backend |**1152 passed**,0 failures/errors/skips; JUnit retained. |
| Actual shared downstream helper |**2 backend smoke+285 frontend+TypeScript/Vite build+17 workstation browser cases**, exit0. The2 backend cases overlap the full suite. |
| Dependencies/browser entry |Base/CUDA/ROCm exports match;51 installed base pins match. Default Chromium/selected Chrome each1 pass with explicit sandbox. Invalid executable and zero-test selection intentionally exit1. |
| Real workstation |Actual FFmpeg/runner/SQLite/HTTP export201→failure400→retry201 preserves oldMP4; legacy/v2 ready→missing agrees; success/failure terminal reports download. Upstream prepared stages/fake ML are explicit. |
| Root Companion |Real browser editing/save/reload, boundary times, legacy reopen,999/1000, ASS/ZIP and real libass burn; both lines visible at0.5s. |
| Supplemental platform |20 final commands exit0;25 surface/9 adversarial scenarios pass: CPU image89 backend hashes, migrations/lock readiness/real cache; macOS build/strict signature/frozenHTTP,8 frontend files/32 dependencies, RS256 positive/negative; CLI/frozen smoke each1, Companion five flows18 screenshots/0page errors/2 actual active polls. |

The [28-row matrix](/Users/drm/project/nyaru-clipper/.omo/evidence/phase5-subtitle-identity-and-export-boundaries-2026-10-21/combined-acceptance.md), [root manual QA](/Users/drm/project/nyaru-clipper/.omo/evidence/phase5-subtitle-identity-and-export-boundaries-2026-10-21/manual-qa-report.md) and [exit receipts](/Users/drm/project/nyaru-clipper/.omo/evidence/phase5-subtitle-identity-and-export-boundaries-2026-10-21/qa-exit-receipts.json) record current evidence. Earlier stages are historical context. Current automated regressions prove #22 double disk fault/#23 malformed receipts; normal browser flows are not manual fault injection. #38/#42 rerun current frontend/workstation regressions; phase4 manual actions remain explicitly historical.

![Actual merged subtitles burned at0.5s](/Users/drm/project/nyaru-clipper/.omo/evidence/phase5-subtitle-identity-and-export-boundaries-2026-10-21/browser-captures/27-merged-burn-at-half-second.png)

## Retained failures and limits

Retained failures include the stale ASS-project assertion, missing mandatory selection diagnostics in an early fixture, an incorrect single-Dialogue assumption, `.5` frame-extraction CLI time, duplicate template creation and platform fixture busy/refetch assumptions. Fixtures/contract assertions were corrected and rerun; tests were not deleted or product validation weakened. Platform freeze records exactly one authorized test change, with product/backend/bundled-dist stability separately verified.

Host uv+pnpm remains primary; Docker evidence is CPU fallback only. No actual GPU/CUDA/ROCm pipeline, external provider/real login, installed native window/quit, full Compose deployment, power-loss atomicity or full font/grapheme QA. LSP is unavailable and was not installed; it is not reported as a static-analysis pass. Actual tsc/build evidence is separate. #37 and previous module-size/error-style maintenance remain WATCH; deferred performance/layout work is untouched.

Root/platform owned listeners, containers and browser tabs are closed; caller parent markers survive. Docker Desktop was restored to its initially stopped state; images/cache retained. [Platform report](/Users/drm/project/nyaru-clipper/.omo/evidence/phase5-subtitle-identity-and-export-boundaries-2026-10-21/platform-qa/platform-report.json), [cleanup receipt](/Users/drm/project/nyaru-clipper/.omo/evidence/phase5-subtitle-identity-and-export-boundaries-2026-10-21/cleanup-final.json).

Remaining16: **#13,#14,#15,#16,#17,#18,#25,#26,#29,#31,#33,#34,#35,#36,#40,#41**. Disjoint from the28 accepted findings, total44. A later phase must select its own scope.
