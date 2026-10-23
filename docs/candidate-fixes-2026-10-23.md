# Candidate App02: historical-task fixes and revalidation

Date: 23 October 2026 (Asia/Shanghai). Both repairs are **completed and accepted within the local scope below**. This is not a production release, full-platform acceptance or formal-data cutover. [Chinese counterpart](candidate-fixes-2026-10-23.zh-CN.md).

## Repair scope and compatibility

| Defect | Changed location | Result |
| --- | --- | --- |
| F01 Partial translations reported complete | `backend/app/arctime/native_projection.py` | Both list and detail count nonempty translations in the saved document: zero is not_started, some is partial, all nonempty is completed. The message says “saved translations n/N”; clearing removes stale bilingual download references and does not claim provider completion. |
| F02 Lost historical highlight metadata | Same projection; new `backend/app/arctime/migrated_selection.py` | Recover mode, score, reasons and bounds from archived job.json registered by an activated member for the current binding group and generation. Verify candidate/job hashes and clip bounds; corruption uses the existing source-unavailable error. No historical writes. |
| Regression evidence | New `backend/tests/test_unified_projection_regressions.py` | List/detail, whitespace/partial/all/clear, manual/highlight, duplicate same-generation members across batches, archive tampering and document compatibility. |

No database, WorkstationArtifacts format/fingerprint, historical document format or dependency changes. Implementation resides in the separate worktree at HEAD `428ba833193db888c6b049ac2983abe1b2ecae17`, with extensive pre-existing uncommitted changes; HEAD alone cannot rebuild this package. The [build input inventory](/Users/drm/project/nyaru-clipper/.omo/evidence/historical-fixes-20261023/source-input.json) identifies exact bytes. This repair changes only the three product/test files above.

The valid old-baseline run yielded **6 failed / 2 passed**, followed by **8 passed** on the repair. Adjacent backend regressions: **82 passed**, including those eight; frontend: **332 passed / 40 files**. Packaging TypeScript/Vite build succeeded. See [logs and receipt](/Users/drm/project/nyaru-clipper/.omo/evidence/historical-fixes-20261023/receipt.md). Independent scoped review approved without blockers; its single nonblocking same-object fingerprint assertion was removed while retaining independent fingerprint and saved-document checks. No new full-backend or LSP run.

## Package identity

Display version remains 0.1.19/build 27: identify by path and hash. Apple Silicon macOS candidate, strict ad-hoc signature verified; not notarized.

| Delivery | SHA256 |
| --- | --- |
| [Candidate App ZIP](/Users/drm/.cache/nyaru-clipper/unified-native-build-20261023-02/Nyaru-Clipper-unified-candidate-20261023-02.zip), 633640976 bytes | `914e36a0b7cf97ad864cedf9d87abfcfcb1b0ae76248b5ec5da2eb7272eff14b` |
| [Independent recovery ZIP](/Users/drm/.cache/nyaru-clipper/unified-recovery-20261023-02.zip), 98611249 bytes | `31e364935d925993b6a849d8c1f7df21b325731c29a39e3e298774153a339c42` |
| Native executable | `c978b378058e073e2a58f1478bb3d184ab08256daa4e35e53593dbb02ef1ffd4` |
| Frozen backend | `e75a50f2e31f166e5a4661bb7016e287ffb46f290811ea15108d03bb0f294d5e` |
| App/standalone bundle.json | `52342c6a998c6241a5381db6a778bb792ae38a0e197989d166da79da73016b54` |

Verified 5407 App files and 3620 recovery resources, including 151 legacy Python modules; ZIP CRC, extracted contents/modes, original/extracted signing, standalone interpreter and reader entry passed. Retain the recovery directory at `/Users/drm/.cache/nyaru-clipper/unified-recovery-20261023-02`; never move or replace an epoch's pinned reader. See [package identity](/Users/drm/project/nyaru-clipper/.omo/evidence/historical-fixes-20261023/artifacts.json).

## Frozen-package acceptance matrix

| Criterion | Result and limits | Evidence |
| --- | --- | --- |
| Five historical task copies | **25/25 scenario groups PASS**. Three manual and two highlight jobs share one 20.4-second Tingting/FFmpeg synthetic source; this is not real-recording acceptance. | [Matrix](/Users/drm/project/nyaru-clipper/.omo/evidence/historical-fixes-20261023/packaged/manualQa.json), [independent audit of 311 references](/Users/drm/project/nyaru-clipper/.omo/evidence/historical-fixes-20261023/packaged/independent-artifact-audit.json) |
| F01 | List/detail: initial zero, spaces zero, 1/2 partial, 2/2 completed, clear to zero. Cleared bilingual files return404; stale CAS409 preserves state; reopen persists. | [Historical-copy report](/Users/drm/project/nyaru-clipper/.omo/evidence/historical-fixes-20261023/packaged/historical-fixes-manual-qa.md) |
| F02 | All five tasks preserve mode/bounds/score/reasons at initial, edited, exported and reopened checkpoints. | Same report |
| Adjacent features | Library search/tags/archive/pagination, subtitle history/CAS/SRT/VTT, template CAS, serialized settings save/readback, queue, preview, ASS, ArcTime ZIP and CPU burn passed. Studio settings have no public CAS field; no such claim is made. | Same report |
| Crash/retry | SIGKILL during export becomes interrupted, reopen does not retry automatically, explicit attempt2 succeeds and fully decodes. Video is6 seconds; AAC container is6.037 seconds. | Same report |
| Real150-second source | New task `ad3ad70afddf5287b5d1b4f797665a2a`: actual bundled whisper.cpp generated21 cues. First/last are explicitly manual QA translations; list/detail show partial2/21. Full source/clip decode and PNG/ASS passed. | [Real-source report](/Users/drm/project/nyaru-clipper/.omo/evidence/historical-fixes-20261023/real/historical-fixed-real-manual-qa.md) |
| Native App | WKWebView elapsed playback advanced0→3→10 seconds. Saved revision2 persisted through CmdQ and exact guarded reopen. UI submitted the real15-second burn and NSSavePanel saved it; saved bytes match the registered product, full decode passed. | [Native receipt](/Users/drm/project/nyaru-clipper/.omo/evidence/historical-fixes-20261023/real/native-verification.json), [product](/Users/drm/project/nyaru-clipper/.omo/evidence/historical-fixes-20261023/real/native-saved-burn.mp4) |
| Independent recovery | Paused queue and stopped App/helpers, sealed all six runtime roots immutable. New recovery bundle exported all3 documents without errors; real revision2,21 cues/two translations match. | [R2](/Users/drm/.cache/nyaru-clipper/historical-fixed-native-20261023-01/R2/complete.json), [final audit](/Users/drm/project/nyaru-clipper/.omo/evidence/historical-fixes-20261023/final-audit.json) |

Failed harness attempts remain preserved: initial tab/newline input was rejected by existing validation, invalidating its dependent version count; valid spaces and actual immutable-version counts were rerun. Native Save-panel navigation did not take effect, so the absolute Save As became a colon filename in the older fixture directory. Only this newly created output was moved to evidence; no existing file was replaced. These were QA-operation corrections; product validation was never relaxed.

## Protection and handoff

Formal App content/metadata and formal data metadata match the pre-build baseline; this does not claim complete formal-data body hashing. Five original historical tasks match the current and four earlier protection baselines; selected original tasks and the real media retain hashes/metadata. No formal App replacement/data cutover, remote connection, commit, push or merge.

Fresh `historical-fixed-api-20261023-01` and `historical-fixed-native-20261023-01` domains use new source UUIDs and App02 reader pins. Old App01/recovery/protected domains/epochs remain retained. All created servers, native App/helpers are stopped and queues paused. The real runtime's six roots and new R2 are sealed: **do not directly reopen, unseal or thaw this R2**. Exact read-only recovery argv is retained in receipts. Any new writable run needs an independent new domain through the recovery procedure; do not rebind old reader pins.

Every candidate launch requires absolute `--unified-runtime` and matching `--migration-guard`. Do not double-click the candidate into the default formal path. Runtime paths here identify sealed evidence, not writable startup instructions. The formal App needs no rollback: stop the candidate and preserve its data/packages; never overwrite newer documents or formal data with an older package.

The [App01 failure report](/Users/drm/.codex/worktrees/unified-architecture/nyaru-clipper/docs/historical-task-acceptance-2026-10-23.md) remains a valid historical record. This run did not repeat App02 R0/R1 thaw or complete M03/M24 platform qualification; earlier results do not automatically qualify a new package. M24 OS-restart/boot protection, CUDA/WSL ROCm/Windows AMF, real live capture and external translation remain pending. P6 and formal cutover have not started. Semantic accuracy, ArcTime GUI and notarization remain unqualified.

![Candidate App02 reopened with saved translations2/21](/Users/drm/project/nyaru-clipper/.omo/evidence/historical-fixes-20261023/real/native-reopen.png)
