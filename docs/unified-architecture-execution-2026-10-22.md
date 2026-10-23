# Unified architecture execution record

Date: 2026-10-22, Asia/Shanghai. See the [design](superpowers/specs/2026-10-22-unified-architecture-design.md), [plan](superpowers/plans/2026-10-22-unified-architecture.md) and [Chinese record](unified-architecture-execution-2026-10-22.zh-CN.md).

**The P0-P4 unified runtime candidate and P5 migration/independent-recovery implementation have passed local verification. P5 platform/production qualification remains pending, P6 has not run, and the complete architecture is not accepted.** Sections 1-7 retain checkpoint observations; section 8 and the [candidate guide](unified-runtime-guide.md) describe current state. No production takeover or replacement installation occurred.

## 1. Isolation and observed baseline

- Separate worktree: `unified-architecture/nyaru-clipper`; branch `codex/unified-architecture-2026-10-22`, based on `428ba833193db888c6b049ac2983abe1b2ecae17`. No commit, push or merge.
- Existing dirty documents, indexes, outputs and other worktrees remain in place. The four reviewed bilingual design/plan files were copied into the candidate worktree; execution evidence is tracked separately.
- macOS 27.0.1 / arm64; Python 3.11.16, pytest 8.4.2. An isolated `backend/.venv` was created from `uv.lock`; no model downloads.
- Default PATH pnpm is 11.25.0; cached **10.33.2** was verified. No global version change, frontend build, browser or native acceptance.
- The product subtitle selector actually uses FFmpeg **7.1.5** with libass. PATH FFmpeg 9.0.1 is not this fixture renderer.
- A process-name check found no running Nyaru/uvicorn/worker process. It is not a future takeover process-exit proof.
- Production roots received counts and a read-only SQLite query only: **0** twelve-character Companion task directories; **1 failed** registered Workstation task with one matching directory; **5 unregistered directories**. Their contents/ownership remain unknown and are retained for P5 inventory, not treated as disposable cache. Source-instance registration has not been verified.

## 2. Implemented batch

| File | Actual responsibility |
| --- | --- |
| `backend/app/services/task_import.py` | P0 **read-only discovery** extracted early from the future P5 importer: external instance UUID plus legacy ID, task-file generation, primary/secondary artifact verification, secondary-writer observations, individual rejection and fixed error codes; reports expose no paths, URLs, secrets or raw exceptions |
| `backend/tests/test_unified_import.py` | 31 discovery identity/protection checks: renames, same-generation replay, task-file changes, broken JSON, missing files, bad hashes, escapes, symlinks, active translation/export, mutation during reads, secret canaries and missing registered secondary files |
| `backend/tests/unification_fixtures.py` | Two instances, repeated legacy ID, failed/queued/missing/orphan cases, actual template/default/project formats, fake credentials and R0/R1/R2 samples; both frozen subtitle formats and original word data |
| `backend/tests/unification_media.py` | Regenerable speech media, exact-duration closed blocks, ASS/SRT/PNG/FFV1 reference, fixed RGB frames and a hash manifest written last |
| `backend/tests/test_unified_fixtures.py` | Five contract/fixture checks: 5000 cues, existing-output refusal, actual template bindings, both language directions and word provenance |
| `backend/tests/test_unified_media_fixture.py` | Actual media frame count/duration, exact eight-block durations, read-only R0/R1/R2 loading with the original reader and fixed-ROI reference visibility at cue boundaries |
| `backend/tests/test_unified_platform_preflight.py` | Actual temporary-root permission probe as an ordinary user: reject writes/create/delete/rename/old read-write lock opens; kill the lock holder and reacquire an exclusive lock through a read-only descriptor |

Discovery is not wired into startup, APIs or CLI. It creates no locks, writes no mappings, changes no ownership, starts no tasks and grants no takeover. `task_generation` covers task files only; it is not the global-package-bound `source_generation` that must be rechecked under a Supervisor. Repeated legacy IDs have distinct **discovery identities**; persistent mapping idempotency and post-activation conflicts remain P2/P5 work.

## 3. Compatibility and write boundaries

| Capability/data category | P0 evidence | Remaining phase/acceptance |
| --- | --- | --- |
| Companion ranges, highlights, Saozi and live | Existing static implementations; workflow regressions; prepared closed blocks | P1/P3/P5; A2/A5/A7/A9 |
| WhisperX/whisper.cpp; Chinese-to-Japanese/Japanese-to-Chinese | Both frozen formats, languages/word data; two actual local whisper.cpp audio recognitions | P1/P5; A2/A9; frozen records cannot certify GPUs |
| Missing models/unconfigured authorization | Existing recovery boundaries retained; fake credentials excluded from receipts | P3/P4/P5; A6/A11; no real provider calls |
| Referenced/copied sources, missing sources, orphans | Per-task missing-source rejection; orphan files affect task generation; production unregistered directories counted only | P1/P5; A1/A11; actual reference-mode integration remains |
| Old documents, source proof, local styles, 5000 cues | R2 revision 1 has 5000 cues; original reader loads without changing task hashes | P1/P2; A3; dual-client saves remain untested |
| PNG/ASS/burn/ArcTime | Fixed references and actual template/project binding; no product FFV1 option | P1/P5; A4/A9; product burn/download and RMSE remain untested |
| Failure/interruption/queue/cancellation | Discovery classification and existing queue regressions; no old eligibility withdrawal | P2/P3/P5; A1/A5/A6 |
| Main DB, events, queue and operations | Existing Workstation regressions pass; no schema changes | P2/P3/P4; A1/A5/A6/A8 |
| Defaults/templates/projects/tags/archive/history | Actual formats/field fixtures; tags/archive explicitly synthetic metadata | P4/P5; A1/A11; no global-package migration |
| Credentials, models and tools | Original locations/models retained; fake authorization in a separate 0600 root; only model/font hashes recorded | P4/P5; A9/A11; no revoked-token restoration |
| Normal/broken-candidate/multi-root/cross-batch recovery | Original-reader R0/R1/R2 samples and local permission probe; no recovery launcher | P2–P5; A1/A6/A10; M15/M16/M23–M27 have not passed |
| Native quit, browser, LAN, CLI, old-core retirement | Existing boundaries retained; no entry replacement | P4–P6; A8/A11/A12 |

Write locations are classified by role: Companion tasks hold job/gui, source/clips, ASR cache, capture blocks/closed.csv/live checkpoints, translation, subtitle documents/proofs and styled outputs/receipts/logs. The Workstation DB holds tasks/queue/runs/events, while raw/work/exports/reports/logs retain their existing roles. Settings hold templates/defaults/projects; authorization holds config/.chatgpt; models/tools and native ready files have separate roles. Registry/guard/global-package roots are fixtures only, not live runtime state. Whether actual credential/task roots share a protection domain still needs P4 preflight; a permission probe does not decide that question.

## 4. Frozen evidence and checks

Private bundle alias: `~/.cache/nyaru-clipper/unified-p0-20261022-bilingual-i6mmfdv5/fixture/`. Do not commit this bundle, fonts, voices, models, fake credential bodies or raw logs.

- Manifest: `0c4177d7a55825c6cc400ffe93ae5b7d732fceec13f39748fb592a8d032b86fd`.
- Contract: `9f86c6878fd5149464d8542c6f877df5755cd283c761e7f1110f67fe9ef31991`.
- All **150 file hashes** rechecked equal; fake credentials are excluded. Arial hash: `525979822591a3447cfc49d943d6f7683508e25543407871c0ed8fed05fd2bd9`.
- F-media is 4501 frames at 30fps, 1280×720. Measured F-live durations are 7×20s plus 7s. Initial AAC copying added about 16ms; the generator now re-encodes audio without weakening duration assertions.
- Reference frame 60 was visually inspected inside the fixed ROI. Automated checks find no cue on frames 29/90, a cue on 30/31/60/88/89 and no corresponding changes outside the ROI. Product MP4 RMSE/bounding boxes were not measured; M07/M28 remain unpassed.
- Existing whisper.cpp/GGML-small actually recognized both AIFF tracks; output matched script meaning, with Japanese punctuation/orthographic differences. Model hash: `1be3a9b2063867b937e64e2ec7483364a79917e157fa98c5d94b5c1fffea987b`. Both new-bundle audio hashes equal the recognized tracks. This proves recognizable fixture speech, not full-video/editor/export M17 acceptance.
- Final regression: **310 passed / 0 failed / 0 skipped in 16.29s**, comprising 272 original baseline cases and 38 new checks. JUnit is beside the bundle at `p0-regression-final.xml`.
- The no-excuse checker passed for all seven added Python files. basedpyright/ruff are absent; no complete type/lint pass is claimed, and previously declined LSPs were not installed.

Run the final regression from `backend/`:

```bash
.venv/bin/python -m pytest -q tests/test_unified_import.py tests/test_unified_fixtures.py tests/test_unified_media_fixture.py tests/test_unified_platform_preflight.py tests/test_arctime_workflow.py tests/test_subtitle_identity.py tests/test_subtitle_identity_proof.py tests/test_subtitle_document.py tests/test_subtitle_api.py tests/workstation
```

## 5. P0 phase state at its checkpoint

The local P0 preparation candidate is completed. M01/M02/M03/M14/M15/M16/M23/M24/M25/M27 have partial fixtures/preflight only; other M items remain planned, and no M item is fully accepted. Linux CUDA, WSL ROCm and Windows AMF were unavailable for actual testing in this run. Actual capture, real external AI, reboot, production migration, App replacement and old-core deletion were not performed.

P1 next: first demonstrate failure when a real Workstation layout enters the old editor input, implement explicit source context, then exercise loading/single-cue editing/save/reopen/PNG/ASS/actual burn download against the same isolated API under the frozen tolerances. Do not fabricate job.json, connect old software to new schema or label frozen formats as actual GPU acceptance.

This batch rolls back at R0: retain the original product entry. The new module has no product callers, so no database/business-file restoration is needed. Retain this worktree/fixtures for continued checks; do not remove unregistered directories or old evidence automatically. P5 production cutover and P6 deletion retain the plan's separate authorization conditions.

## 6. P1 observed interoperability

- Explicit registered Workstation artifacts enter the existing Companion editor without a fake job.json. Contexts verify hashes, symlink ancestry, configured reference-media roots, original words, both language directions, absent translation and short tails. Frozen layouts establish compatibility, not GPU inference.
- Actual isolated API and Chrome: load 5000 cues, edit/save/reopen one cue, retain the other 4999 including styles, use the correct zh-ja download, and reject an actual second-tab stale autosave with HTTP 409 while retaining its draft. The final browser scenario passed in 12.8 s; its full-page screenshot was inspected. Cached pnpm 10.33.2 installed existing locked dependencies; 82 focused frontend assertions and TypeScript/Vite build passed.
- The actual product API generated PNG, ASS and libx264 fast CRF20/AAC/+faststart MP4. Downloaded MP4 decoded successfully, lasted 5 s within one frame, had audio/video starting within one frame, and preserved source/old artifact hashes. The repeated request reused its artifact with one encoder invocation.
- Fixed frame comparisons at 29/30/31/60/88/89/90: maximum RGB RMSE **0.356518**, maximum glyph-box error **1 px**, against unchanged limits 8 and 2 px. Product SHA256 `15fb189078de3abdc05c7f2209fe01a7929c3206f5127876415016c9fcb058c1`; artifact `40133c762a8767e64f4b`. Retained private evidence: `~/.cache/nyaru-clipper/unified-p1-product-20261022-final/`, adjacent JUnit XML. The retained product run passed in 7.05 s.
- Local P1 exit covers the isolated parts of A2/A3/A4/A11 and the local product-export M28 path. Linux/WSL GPU, native-window lifecycle and cumulative P5 acceptance remain outstanding. Rollback stays R0 with separate new documents/outputs.

## 7. Continuing P2/P3/P4 implementation

These are observed component checks, not phase acceptance or complete host integration:

- Additive revision `20261022_01` adds bindings, paused runtime, operations/attempts/process groups/steps/publications and document indexes. Downgrade refuses to discard unified history. Existing schema/backfill regression checks passed on temporary databases.
- Whole-set receipts fsync before ready; immutable independent final files precede one set/event commit. Six crash boundaries, damaged/missing receipts, staging/output damage, cancellation, stale history, independent staging, disk-full injection and repeat registration checks passed. All **144 D/E/P/T/F combinations** map to exactly one of J00–J14. Recovery never promotes a still-running live parent merely because its first child committed.
- Immutable document bodies plus DB CAS pass save/reopen/conflict/orphan-body checks and are connected to the existing editor API for activated bindings. Legacy readers remain separate; GUI JSON cannot restore an operation token.
- Shared executor checks passed for two databases competing for one host slot, parent-owned child publication and cancellation of a real subprocess group before the next claim. Updated worker, desktop processing/export and CLI entry paths acquire the host slot; original GUI/translation/CLI/ASR/export/live/queue regressions passed in targeted groups. Four-kind engine/host dispatch and frontend queue integration remain in progress.
- Actual macOS Supervisor kill test passed: persistent immutable flags and read-only permissions reject old edits/new directories/root replacement after SIGKILL; restart reacquires the original lock inodes with read-only descriptors. A false dependency-release check refuses thaw, and explicit test thaw restores original modes without changing separate synthetic credential bytes. This does not establish reboot or actual old-application M24 acceptance. Linux/WSL require a verified read-only mount profile; ordinary directory permissions cannot qualify by themselves.
- `/api/v2/operations` has real temporary-DB HTTP coverage for paused admissions, revisioned ordering, stale conflict and cancellation; public views omit tokens/configuration snapshots. Generation of frontend contracts, complete configuration snapshots, host dispatch, migration transactions and independent recovery remain open work.

The preceding **in_progress** checkpoint is historical; current state follows. These checks do not establish external AI/capture, GPU/platform, or reboot acceptance.

## 8. Complete candidate implementation and current acceptance ledger

The user subsequently authorized complete Option B execution and provided a clean native Linux ROCm workstation with download authorization. Implementation retains desktop and GPU workstation capabilities. No production cutover, replacement installation, merge/push, or old-core deletion occurred.

### 8.1 Implemented runtime boundaries

| Scope | Implementation and inspection entry |
| --- | --- |
| SQLite authority | `models_unified.py`, `models_migration.py`, additive revision `20261022_01`; explicit initialization/reopen, no automatic recreation/repair for missing DB/tables or unknown schema |
| Four operations | `unified_cli.py`, `unified_host.py`, `unified_dispatch.py`; shared queue, priority/order, pause/cancel/retry, attempts/tokens/process groups; old entries share the host heavy-work lock |
| Engines and live | Actual local CPP inference; WhisperX frozen configuration/model hashes, 300-second chunks and tail; live parent owns the slot, raw/partial bilingual/styled results publish early, child failures persist, unknown billed outcomes need acknowledgement |
| Documents and artifacts | Immutable bodies plus DB CAS, history, no orphan adoption; set receipts, immutable individual publication, final transaction; actual ASS/PNG/burned MP4 and original hashes verified |
| Shared UI/configuration | Real paged/filterable/tagged/archived library with metadata CAS and retained drafts; queue/generated contracts; complete public settings, frozen template/project bodies; credentials referenced separately |
| Takeover | `migration_*`, `source_seal.py`: external UUIDs, complete roots/generation, prepare/verify/activate; one continuous Supervisor locks/protects/rechecks/commits; changed sources and transaction failures never partly activate |
| Whole-group rollback | Sticky R2 for task/global writes; cancelling B cannot thaw A; R0/R1 commit withdrawal/permission receipts before restoring old roots; re-registration after thaw opens a new group and retains history |
| Unstartable candidate | `build_unified_recovery.py` freezes independent Python/dependencies/formats/guard/helper/media tools; multi-root snapshot/read-only/thaw without candidate imports, network or models; old helper writes only an independent old-format working copy |

### 8.2 Reproducible evidence

- Final backend full suite: **1512 passed, 17 existing JUnit record_property warnings, 231.20 seconds**; `~/.cache/nyaru-clipper/unified-backend-20261022-r5.xml`. Run from backend with `PATH="$PWD/.venv/bin:$PATH" TMPDIR=/tmp`. Earlier temp-path/interpreter failures without that environment are not clean results.
- After removing unused imports, unified regression: **153 passed, 77.31 seconds**, `unified-focused-20261022-final.xml`; the later language-asset check is included in the final full suite. New Python rule check: **115 files, zero violations**. LSP was unavailable; no clean LSP claim is made.
- Final frontend: **332 passed / 40 files, 12.40 seconds**; TypeScript/Vite build passed; re-exported OpenAPI is byte-identical. Seven transport checks and the complete frontend passed after SSE fallback was completed; actual browser evidence is separate.
- Chrome r5 passed keyboard/touch ordering, stale queue 409, two-client metadata CAS/draft retention, pause/reopen, two real ASS exports and clicked download. Eight desktop/phone light/dark screenshots were individually inspected; two independent UI reviewers passed that scope. r6 extension retained failures from a test acknowledgement race and an offline simulation that did not close an active stream. r7 waits for durable confirmation and closes the real SSE stream through the fixture: **2 passed in 54.3 seconds**, including library polling during five failed connections, restored SSE updates, cursor reconnection and subsequent updates. Evidence: `unified-queue-20261022-1_md6l57/browser-r7/`.
- Native candidate `unified-native-build-20261022-02/Nyaru Clipper.app` used the same SQLite state. Actual CPP processed 150.033333-second media into six cues, a 0-30-second clip and burned output; saved revision 1 survived. Normal quit ended App and helper. Explicit same-build reopen changed port 59313 to 59678 and retained the earlier selected task `8cb8f1980a815e9696728c36545ebfd6`, “原生候选验收：今日は、いい天気です。” and paused queue. A separate invalid-media test retained failure as expected; it is not inference evidence.
- The first native quit exposed Uvicorn waiting for SSE. The fix passed a real HTTP-stream SIGTERM check without CancelledError. Automation once relaunched the default compatible entry while observing the exited old candidate; it was stopped immediately. The observed interval showed only a new `startup-*.json`, with no business-file rewrite observed; that startup evidence is retained. The installed App was not replaced; this must not be described as absolutely zero writes to the formal root.
- **Seven independent thaw combinations** cover R0/R1/R2, before/after sealed snapshot, and partial old-permission restoration failure. Failure leaves `withdrawing`, zero activated bindings, and resealed new DB. Original `controls-resealed.json`, a fresh complete snapshot and a new output directory resume offline successfully. Exported operator recipes also completed all six roots/three locks and frozen-entry thaw.
- Final `unified-native-build-20261022-05` passed frozen CLI initialization, actual native startup and normal quit in a new independent root, plus signature/pinned-bundle verification; its bundle SHA is `ae41b563b591a0fa89072ea9d2b616eafd452ce4a64852bbf6166ff3038f4888`. The actual processed sample separately completed six-root snapshot/read-only export using build-04's pinned bundle: `complete=true`, revision 1/six cues/four registered publications. Never replace its pinned reader with a newer bundle. Build-04 bundle SHA `1fbeb3c8f87145d1c78e1d41b4ac5670d24fbc8f9b6f22038389eab69fbe7731`, snapshot SHA `8859a044a485b6dec4476c2809b96c1ffda7cc77af16459844aa8b5092ab18a7`, verification SHA `e74d5f452b633034f4c126228e6e9e65441f3372ecf108ecaa1ef0fe2ba54b2a`.
- Under actual immutable protection, changed source generation, interrupted activation transaction and wrong group all retained verified batch/prepared binding, exposed no document/global heads and rejected old writes. Explicit external-media registration works without the current host catalog; normalized media comes from the registered root and original database bytes remain unchanged.

### 8.3 M01-M28 state and limits

`local_passed` means the stated local evidence passed; `partial` covers implementation or bounded scenarios; `blocked` needs a target environment, real source, or separate authorization. None means complete cross-platform acceptance.

| Acceptance | State | Evidence or remaining gate |
| --- | --- | --- |
| M01 | local_passed | Source identity, duplicate/missing/corrupt import, zero duplicates and original hashes; no production takeover |
| M02 | local_passed | New candidates before activation, conflict/preserved edits after activation, new group with same UUID after thaw |
| M03 | local_passed | 23 October adds 8 real SIGKILL boundaries, saved r1→r2 revalidation and unique activation, actual guarded HTTP takeover/reopen; platform reboot protection remains under M24/§9 |
| M04 | local_passed | Both frozen ASR formats, translation directions and word hashes; actual GPU remains M18 |
| M05 | local_passed | Actual 5000-cue browser/CAS, retained 409 draft, other 4999 cues unchanged |
| M06 | local_passed | Body/CAS fault boundaries, orphan rejection and history |
| M07 | local_passed | Frozen lossless reference with preset ROI/thresholds; separate from product burn |
| M08 | local_passed | Six publication fault boundaries/reopen reconciliation; first clip never falsely completes parent |
| M09 | local_passed | File ENOSPC, DB pre/post-commit faults, old attempt, missing/corrupt members |
| M10 | local_passed | Two executors with real child groups, one slot/cancel, browser order/priority/pause |
| M11 | local_passed | Parent slot plus readable partial video/bilingual products; controlled model/AI substitutes |
| M12 | partial | Controlled 120+27-second chunks, stop/disconnect and preserved raw output after translation/style failure; real capture remains M19 |
| M13 | local_passed | Native quit/reopen, saved revision/selection; real browser fallback/cursor reconnection in r7 |
| M14 | local_passed | Complete public settings, templates/defaults/projects and unchanged independent credential canary |
| M15 | local_passed | Independent old helper with actual HTTP edit/reopen, separate working writes, online interfaces blocked |
| M16 | local_passed | Frozen -I -S -B reader/thaw with audited prohibition of candidate imports/network/children |
| M17 | local_passed | macOS actual small model, native edit/burn/reopen; not full semantic-quality acceptance |
| M18 | blocked | Linux CUDA/WSL ROCm unavailable; completed native Linux ROCm supplementary qualification cannot replace them |
| M19 | blocked | No controlled real live source/complete first-and-tail capture evidence |
| M20 | local_passed | Path/symlink/Origin/Host/body-limit and public projection credential-canary rejection |
| M21 | blocked | P6 prerequisites unmet; old entries/readers retained |
| M22 | partial | Actual CPU burn passed; windows-amf/hardware-failure qualification not run |
| M23 | local_passed | Same-root A edit/B cancel stays R2, old writes denied; whole-group R0/R1/resume passed |
| M24 | partial | 23 October adds old GUI/CLI/DB write denial, guarded host kill/reopen and independent thaw kill-boundary recovery; controlled OS reboot and other protection profiles remain unqualified; finite boundaries do not prove every crash timing |
| M25 | local_passed | Global-only writes, complete multi-root epoch/history/registry, missing-root rejection |
| M26 | local_passed | Exactly one J00-J14 rule for 144 valid combinations; illegal/missing/corrupt receipts and old attempts rejected |
| M27 | local_passed | Interrupted copy/seal, ENOSPC/generation changes never sign complete; original-permission journal resume |
| M28 | local_passed | Real API downloaded MP4, preset encoding, max RMSE 0.356518/bbox 1 px and unchanged originals |

### 8.4 Workstation downloads and qualification

The isolated qualification host runs Rocky 9.8/ROCm 7.2.4/RX 7900 GRE and uv/Python 3.11.16. CTranslate2 4.8.1, including exact gitlinks at `0d8bcd362ac75ef860ef161d6f0efad0ae439ff0`, passed actual compilation and float16 GPU capability checks. Rocky's lib64 issue is fixed with `-DCMAKE_INSTALL_LIBDIR=lib` and covered by the dry-run regression. Fixed AMD torch/triton wheels were downloaded directly, verified by full ZIP CRC and computed hashes, then installed locally. Other dependencies retain the original platform pins; `uv pip check` reports all 132 installed packages compatible.

The real API completed 150.033333-second fixed speech media through WhisperX small GPU recognition/Japanese alignment, saved revision 1, PNG preview, and a downloaded/fully decoded 30-second burned product. Model metadata records `device=cuda` and `compute_type=float16`, matching requested values without CPU fallback. The single recognized cue does not establish semantic quality. Task `8333059829bd563b9094d3065a87355c` has processing operation `5eb991661cc34db897bc16a2b49764e3` at attempt 2 and export `691950408978455d93c22d80ed727c61` at attempt 1. The initial missing-punkt_tab attempt remains preserved; the same task was retried after provisioning data.

The actual browser opened the shared editor, displayed saved revision 1/body, and clicked the burned download. Both browser and API downloads hash to `a88627da42b28bad83af40a2d2c1e16330d4fc8458e0e4f3cbb3d3f7777a5866`. Restart changed port 54107 to 56439 while preserving paused admissions, both operation IDs/attempts, saved document and product hashes, with no re-inference/re-encoding. Local evidence: `~/.cache/nyaru-clipper/unified-gpu-result-20261022-r4/`; the server retains failure logs/receipts and `gpu-reopen-receipt.json`. Temporary qualification services are stopped afterward; models/data remain.

Qualification pins a separate `FONTCONFIG_FILE`/Noto CJK font. The default template's recorded font substitution prevents treating this as macOS V's same-font/same-FFmpeg RMSE qualification. Only the offline qualification process cleared inherited proxy variables; system proxy settings were unchanged, and HTTPX compatibility with a retained SOCKS proxy is unqualified. `NLTK_DATA` points at explicitly provisioned punkt_tab; readiness now exposes its absence. `yt-dlp==2026.8.19` is declared in pyproject/uv.lock/generated base requirements for shared-entry installation. All previous GPU pins are unchanged; requirements `--check` and 40 related tests passed.

Downloads verified on both hosts: faster-whisper small revision `536b0662742c02347bc0e980a01041f333bce120`, model SHA `3e305921506d8872816023e4c273e75d2419fb89b24da97b4fe7bce14170d671`; Japanese alignment revision `cf031e020336460d15a417eba710bbc5bb43be9a`, model SHA `4f6821dcd79770fcd4c11487c4ee5c040b3a7e1863425224014ba5ea8fbc1b67`; FFmpeg archive SHA `70f6754495d22213ba26544810fc6bc3e4e4dfd8d5cd7a3489c810bb2a4364d8`, actual version `n8.1.3-23-g5c4f5744cd-20261022`, not V's fixed 7.1.5. Configurations and partial downloads are retained; partial files are never treated as usable models.

Additional computed hashes: torch wheel `0c361dda89b2a31f287bf816fe9007e28e7aa7765d1e87ab66bb5679772157e8`; triton wheel `5d6c9cd253f311de473570450840f901460a87a3aec26cbdcb22dd8b06e1e94c`; Noto font `68a3fc98800b2a27b371f2fb79991daf3633bd89309d4ffaa6946fd587f375b5`; punkt_tab archive `e57f64187974277726a3417ca6f181ec5403676c717672eef6a748a7b20e0106`. These torch/triton/font/language-data hashes were computed after download, not publisher signatures.

### 8.5 Handoff and protected state

Work remains isolated in the candidate worktree. Existing dirty primary changes, formal task database/artifacts, five unknown directories, authorization, and installed App must not be overwritten. QA roots, native builds, GPU caches, independent bundles and failure receipts remain in the user's cache. P5 cannot be promoted from 1512 regressions alone; P6 cannot be made complete by prematurely deleting compatible entries. Operational rollback commands are in the [bilingual guide](unified-runtime-guide.md).

## 9. 2026-10-23: additional M03/M24 takeover and crash-recovery qualification

All drills used new independent copies, placeholder credential directories and loopback ports. No formal-data cutover, installed-App replacement, GPU-host connection, commit/push or host reboot occurred. §8 receipts and pinned bundles remain unchanged. The matrix now has **22 local_passed/3 partial/3 blocked**; M03 closes within its local scope, while M24 retains platform gates.

### 9.1 Takeover and old entry points

- Ten new takeover cases plus five existing activation/guard regressions: **15 passed**. Eight real SIGKILL boundaries: before locks, before sealing, after OS sealing but before the sealed record, after sealing, before the transaction, after final generation recheck, before commit, and after commit before worker startup. Handshakes locate source boundaries; exceptions do not substitute for process death.
- Every case verifies source hashes/inodes, reacquisition of original locks, paused queue and no claimable work. DocumentHead/eight GlobalHead rows are absent before commit and complete afterwards; repeated recovery retains one document version and one `task.created`. A real r1→r2 old-draft save changes text, rejects the stale generation, and migrates r2 once after fresh prepare/verify. Replaced old lock inodes are rejected both while held and on reopen.
- After sealing, five actual old entry paths reject writes: GUI `create_app`/TestClient lifespan, subtitle save service, CLI `resume`, original task lock and SQLite INSERT. The installed native App was not launched.
- An additional real `initialize/pin-recovery/takeover` → six HTTP routes → SIGKILL of the same Supervisor/API PID → old write denial → `serve-guarded` using the same runtime/guard → identical HTTP contents, pause state, original lock inodes and DB counts passed. SIGTERM closed the port and released locks; Uvicorn signal replay returned **-15**, not exit 0.

Evidence: [actual host receipt](/Users/drm/project/nyaru-clipper/.omo/evidence/guarded-startup-20261023/receipt.md), [takeover recheck](/Users/drm/.codex/worktrees/unified-architecture/nyaru-clipper/.omo/evidence/takeover-crash-20261023/recheck/receipt.md). Full host artifacts: `/Users/drm/.cache/nyaru-clipper/guarded-startup-20261023-03`. Takeover teardown unseals only its generated old roots; receipts certify protection at observation time.

### 9.2 Independent recovery kill gaps and fixes

The initial nine R1 boundaries produced **2 passed/7 failed**: SQLite journals, partial old-permission restoration and a `thawed` group missing its final receipt prevented direct retry against the old snapshot. RED remains at `~/.cache/nyaru-clipper/m24-sigkill-nzuuarzr/{junit.xml,pytest.log}`.

The fix is confined to independent recovery and frozen resources: fsync `thaw-intent.json` before unsealing; explicitly pin it with `interrupted_thaw={path,sha256}` to the original recipe/snapshot/bundle/permission journal; verify original inodes inside the lock barrier. Changed non-control roots or old originals are rejected. Control differences are limited to DB/SQLite auxiliary files and two expected guard thaw proofs. The current DB rechecks pause, released execution, no R2 and complete group withdrawal. Terminal receipt completion requires matching DB/guard receipts, original bytes and original permissions; mappings are never reactivated. Validation failures consistently return recovery refusal.

There are **21 new scenarios**: nine R1 kill boundaries, one R0 interruption, five changed-evidence refusals, early R2 refusal and five missing/damaged terminal-proof refusals, rerun with the seven existing cases. Frozen Python `-I -S -B` audit prohibits candidate/model imports, network and children. Receipts retain handshakes, -9 exits, locks, permissions, inodes, original hashes, DB states and retry/refusal outcomes. Terminal negatives cover absent/damaged `thawed.json`, a null DB withdrawal receipt and binding/member rows changed back to activated. They produce no success receipt and do not silently repair injected damage.

**Permission restoration is not atomic:** the old root can become creatable while children/locks remain sealed; killing after full restoration releases old locks. Group mapping withdrawal commits before restoring old permissions. This does not establish write denial throughout restoration. If an old entry subsequently creates new data, retry must stop on changed originals and preserve it. Finite boundaries do not qualify every instruction point or an actual reboot.

Final report, JUnit, source checks and bundle identity: [recovery evidence](/Users/drm/project/nyaru-clipper/.omo/evidence/recovery-crash-20261023-hook-verification.txt), [detailed report](../.omo/evidence/recovery-crash-20261023/report.md); commands: [rollback guide](unified-runtime-guide.md). New drill bundle SHA `4f86fc35cfbd1d6fd88adff49f975b37f4752d46badc5724a0a92abe39165fec`, full scene `/Users/drm/.cache/nyaru-clipper/m24-sigkill-rvee2gfr`; 304 nonempty receipt hashes were verified. The fix enters only newly frozen bundles/new drill epochs. The 22 October build-04 sample reader and build-05 App were not replaced; their qualification cannot inherit these fixes.

### 9.3 Remaining gates

M24 controlled OS reboot, boot-time protection preceding old entry points and Linux/WSL read-only mount profiles remain unqualified. Rebooting the current host or existing remote processes was not authorized; process kills cannot substitute for reboot. CUDA/WSL ROCm, real live capture and Windows AMF keep their previous states; P6 stays planned. Preserve formal tasks, the old source checkout, pinned bundles, originals, credentials, unknown directories and failed evidence.

### 9.4 Final verification and source identity

The main session actually ran from backend cwd with `PATH="$PWD/.venv/bin:$PATH" TMPDIR=/tmp`:

- Full `python -m pytest -q`: **1538 passed, 17 existing JUnit warnings, 362.86 seconds**; [JUnit](/Users/drm/project/nyaru-clipper/.omo/evidence/m03-m24-20261023-full-backend.xml). The last five terminal negatives were added after that collection; this is not a full rerun of the current 1543 cases.
- Final stable-source focused run: guard, activation_failures, independent_thaw, migration_groups, recovery_recipes, takeover_crash_drills and recovery_crash_drills: **46 passed, 149.82 seconds**, including those five terminal negatives; [JUnit](/Users/drm/project/nyaru-clipper/.omo/evidence/m03-m24-20261023-focused.xml). Counts from different runs are not added.
- Eight changed Python files passed AST parsing/no trailing whitespace; paired document links/gate IDs/hashes and the 22/3/3 matrix were checked. Independent code review: **APPROVE/CLEAR/blockers=[]**, [report](../.omo/evidence/m03-m24-code-review.md). No frontend changes; frontend/GPU/native-media/LSP acceptance was not repeated.

The candidate content manifest and test receipt associations are in the [source seal](/Users/drm/project/nyaru-clipper/.omo/evidence/m03-m24-20261023-source.json) and [main-session receipt](/Users/drm/project/nyaru-clipper/.omo/evidence/m03-m24-20261023-receipt.md). No commit/push/merge; the older 197-file seal retains its historical identity.

## 10. 2026-10-23: new App and independent recovery packages

With the user's subsequent authorization, these fixes were built into a new candidate and passed isolated startup, frozen takeover, R0/R1 rollback, independent-reader kill/resume, old-helper reopen, R2 thaw refusal, and actual native r3 save/quit/reopen matching independent recovery in full. Start with [new package delivery and acceptance](candidate-package-2026-10-23.md).

New App: `unified-native-build-20261023-01/Nyaru Clipper.app`; bundled/standalone bundle SHA `1ce64b4effcc38a592d90b12e879dcc02a990a62316af8fbdc8e23e16b31ff12`. App ZIP extraction matches 5406 files/modes and passes strict signing; recovery matches 3619 resource hashes. Before/after installed-App 1496 content hashes and formal-data 6815 metadata entries match; data bodies were not read, so this is not a full data-content hash claim. No additional application-source changes, formal replacement/cutover or commit/push occurred.

All owned processes ended, new R2 domains stay sealed and older build-04/05/epoch pins remain unchanged. Matrix stays 22 local_passed/3 partial/3 blocked. Full-suite/GPU/ASR/provider/OS reboot qualification was not repeated; this does not promote M24 or start P6.
