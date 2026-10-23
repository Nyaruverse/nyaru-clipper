# Option B: Unified Architecture Implementation Plan

> **For agentic workers:** After implementation is authorized, use `executing-plans` task by task. Use `subagent-driven-development` only if the user separately chooses delegation. Check items only after matching evidence is saved. This document authorizes neither execution nor delegation.

**Goal:** Retain desktop authoring and Linux/WSL GPU workstation capabilities using one UI, task contract and business core.

**Architecture:** Use Companion as the product baseline. First connect Workstation output to the existing editor/export path, then unify scheduling/state. Retain engines and recording/live workflows; transfer historical ownership per task and eventually retire duplicate writers.

**Tech Stack:** Python `>=3.11,<3.12`, FastAPI, SQLModel/SQLite/Alembic, React/TypeScript/Vite, Node `>=20`, pnpm `10.33.2`, Swift/AppKit/WebKit, existing FFmpeg/libass and whisper.cpp/WhisperX.

Prepared: 2026-10-22 (Asia/Shanghai); latest execution observation: 2026-10-22. Status: **P0-P4 and P5 migration/recovery implementation locally verified; P5 platform/production qualification pending, P6 not run; cumulative acceptance pending**. See [design](../specs/2026-10-22-unified-architecture-design.md), [Chinese plan](2026-10-22-unified-architecture.zh-CN.md), [actual execution record](../../unified-architecture-execution-2026-10-22.md), and [candidate guide](../../unified-runtime-guide.md). “Documentation only” in the revision indexes describes the earlier design-revision rounds, not this execution state.

## Review revision index (2026-10-22)

| Finding | Revised plan location | Normative design location |
| --- | --- | --- |
| U1 Final source revalidation | [P0/P5 supplement](#rev-u1) | [Design 6.1](../specs/2026-10-22-unified-architecture-design.md#rev-u1) |
| U2 Whole-set publication/receipts | [P2 supplement](#rev-u2) | [Design 5.1](../specs/2026-10-22-unified-architecture-design.md#rev-u2) |
| U3 Independent recovery entry | [P4/P5 supplement](#rev-u3) | [Design 7.1](../specs/2026-10-22-unified-architecture-design.md#rev-u3) |
| U4 Global-state migration | [P0/P4/P5 supplement](#rev-u4) | [Design 6.2](../specs/2026-10-22-unified-architecture-design.md#rev-u4) |
| U5 Live child steps | [P3 supplement](#rev-u5) | [Design 4.1](../specs/2026-10-22-unified-architecture-design.md#rev-u5) |
| U6 Instance identity/conflicts | [P0/P2/P5 supplement](#rev-u6) | [Design 6.3](../specs/2026-10-22-unified-architecture-design.md#rev-u6) |
| U7 Frozen acceptance matrix | [All-phase supplement](#rev-u7) | [Design 8.1](../specs/2026-10-22-unified-architecture-design.md#rev-u7) |

This index closes document gaps only; tools, protocols and all M cases remain unimplemented/unexecuted. Execute section 12 together with the original phases; completing only old checkboxes cannot pass a phase.

## Second review revision map (Rv1-Rv5)

| Residual | Revised plan | Normative design |
| --- | --- | --- |
| Rv1 Cross-batch rollback | [P2/P5 supplement](#rev-rv1) | [Design 7.2](../specs/2026-10-22-unified-architecture-design.md#rev-rv1) |
| Rv2 Locks/crash protection | [P0/P3/P4/P5 supplement](#rev-rv2) | [Design 6.4](../specs/2026-10-22-unified-architecture-design.md#rev-rv2) |
| Rv3 Multi-root recovery | [P4/P5 supplement](#rev-rv3) | [Design 7.3](../specs/2026-10-22-unified-architecture-design.md#rev-rv3) |
| Rv4 Exclusive recovery decisions | [P2 supplement](#rev-rv4) | [Design 5.1](../specs/2026-10-22-unified-architecture-design.md#rev-rv4) |
| Rv5 Product export acceptance | [P0/P1/P5 supplement](#rev-rv5) | [Design 8.2](../specs/2026-10-22-unified-architecture-design.md#rev-rv5) |

Documents only: section 13 joins original phases and section 12 as mandatory execution gates. Passing old M cases never skips M23-M28.

## Global Constraints

- The user authorized implementation on 2026-10-22. Unchecked items remain planned; the execution record owns observed outcomes. Implementation authorization does not replace production-cutover, installation or deletion authorization.
- Trusted single machine/LAN, one user and one GPU heavy-work executor; uv+pnpm primary, Docker fallback. No new scheduling framework or dependency.
- Preserve both ASR engines, translation directions/providers, confirmed-export policy, live stop/recovery, template snapshots and native save-before-quit.
- No production recording/monitoring startup, automatic live reconnect, running-task migration, real AI requests or model downloads unless later explicitly included.
- Preserve all dirty work. Refresh branch/HEAD/status before execution. Scoped commits require separate permission; no bulk staging, reset/clean, push or merge.
- Generate requirements/OpenAPI/TypeScript contracts with existing generators rather than editing generated files manually.
- Use isolated roots, DBs, ports and sanitized fixtures for migration, checks and rollback. Do not commit production data, models, credentials, media, backups or raw evidence.
- Each task has one writer. Old/new systems cannot run heavy work concurrently on the same host/GPU. New queues start paused. Old software must never open the new schema.
- Keep bilingual documents/acceptance IDs aligned. Do not count historical 44-finding acceptance as acceptance of this architecture.

## 1. Delivery ledger and dependencies

| Phase | Deliverable | Dependency | Acceptance IDs | State |
| --- | --- | --- | --- | --- |
| P0 | Baseline, compatibility matrix, isolated rollback fixtures | Implementation authorization | Preparation for A1/A10 | completed: local preparation candidate |
| P1 | Workstation result through existing editor/export | P0 passed | A2/A3/A4/A11 | completed: local interoperability candidate |
| P2 | Persistent tasks/operations and publication protocol | P1 passed | A1/A3/A6/A11 | Implemented/local candidate verified; cumulative qualification pending |
| P3 | Shared executor, queue, cancellation/recovery and workflows | P2 passed | A5/A6/A7 | Implemented/local candidate verified; actual live/GPU qualification pending |
| P4 | Shared API/UI/configuration and native/CLI hosts | P3 passed | A8/A11 | Implemented/local candidate verified; reboot protection qualification pending |
| P5 | Historical batches, actual platforms and rollback drills | P4 passed; separate production-cutover authorization | A1-A11 | Migration/recovery locally verified; platform qualification in progress |
| P6 | Retire duplicate entries/write cores | All mandatory P5 gates passed; reviewed deletion authorization | A12 plus cumulative checks | planned |

Each phase produces an independently reviewable candidate. Failure stops promotion and preserves evidence/the last usable entry. Unit tests never replace actual platform gates. Missing GPUs may permit authorized isolated development, but prevent production activation and old-core deletion.

## 2. Files and interfaces

Paths below are repository-relative phase targets; do not scaffold empty modules. P0 implemented the read-only discovery slice of `task_import.py` early to support identity/protection tests; P5 prepare/verify/activate remain unimplemented. Refresh callers and applicable AGENTS before other integration work.

| Responsibility | Existing integration points | Proposed minimum addition |
| --- | --- | --- |
| Artifact/editor input | `backend/app/arctime/subtitle_inputs.py`, `subtitle_document.py`, `subtitle_api.py`, `subtitle_exports.py`; `backend/app/repositories/tasks.py`, `services/subtitles.py` | P1: `backend/app/services/task_artifacts.py`, explicitly resolving both origins |
| Persistent state/publication | `backend/app/models.py`, `db_migrations.py`, `backend/alembic/versions/`, `arctime/companion_projection.py` | P2: `backend/app/services/task_operations.py`; generate Alembic revision against the then-current head |
| Execution | `backend/app/worker.py`, `services/workstation_queue.py`, `workstation_runs.py`, `task_runner.py`, `pipeline_support.py`, `task_control.py`; `arctime/companion_manager.py`, `workflow.py`, `saozi_live.py` | P3 shared claiming/terminal logic; proposed `backend/app/services/runtime_guard.py` owns one Supervisor/old-root locks/persistent seal; P4 host integration without another scheduler |
| API/frontend | `backend/app/main.py`, `api/routes/`, `arctime/gui.py`, `arctime/*_api.py`; `web/src/companion/`, `workstation/`, `router.tsx`, `vite.config.ts` | P4: `backend/app/api/routes/operations.py`, `api/schemas/operations.py`; operations at `/api/v2/operations`, legacy routes as adapters |
| Native/config/CLI | `desktop/macos/App.swift`, `arctime/macos.py`, `cli.py`, `companion_llm.py`, `chatgpt_credentials.py`, `subtitle_templates.py`, `backend/app/settings.py`, `scripts/build_macos_app.py` | P4 separates task/settings/credential roots; add `scripts/unified_recovery.py` and frozen recovery resources solely for local section 7.1 recovery, without remote connections/credential sync |
| Historical import | Artifact/operation services and existing root locks | P5: `backend/app/services/task_import.py`, prepare/verify/activate and read-only rollback records; no import-on-startup |

Design sections 4-6 define input fields, state and authority. P1 artifact resolution accepts trusted-root artifacts and produces source/translated cues, original word data, languages, duration, time origin, hashes and editor context; rendering does not parse legacy task manifests. P2-P3 operation services own snapshots, tokens and publication; engines accept explicit inputs/report progress. P5 maps sources explicitly rather than inferring ownership from directory names.

## 3. P0: Baseline and fixtures

**Files:** added `backend/tests/fixtures/unification/README*.md`, frozen contract, `test_unified_import.py`, fixture generation/checks and permission-preflight tests; extracted the read-only slice of `task_import.py` early. See the [execution record](../../unified-architecture-execution-2026-10-22.md) for the observed matrix and full evidence.

- [x] Refresh source/dirty state, interpreters, pnpm, processes and root counts; distinguish one registered failed Workstation task from five retained unregistered directories with unknown ownership.
- [x] Map all listed capabilities/data categories and write roots to subsequent phases/A IDs; distinguish static presence, actual runtime and accepted evidence.
- [x] Write and pass read-only identity/protection checks: distinct identities across instances, equal same-instance/same-generation discovery, generation changes on task-file changes, individual corrupt/missing rejection and no secret reports. **Persistent import mappings, repeated import and U6 post-activation conflicts retain their original P2/P5 gates; M01/M02 are not closed.**
- [x] Prepare R0/R1/R2 samples and pin media/document/reference hashes; actually observe read-only loading of original formats. New schema/Workstation formats must not be downgraded directly; the independent recovery launcher remains P4 work.
- [x] Save bilingual matrix/discovery boundaries/platform gaps/fixture results; 310 regression checks pass, covering local preparation/existing regressions rather than full M acceptance.

**Exit:** every supported capability/data category maps to a phase/A ID; no unclassified writer; unchanged source-fixture hashes. **Rollback: R0**, retain fixtures/evidence without touching production roots.

## 4. P1: First complete workflow

**Files:** add `backend/app/services/task_artifacts.py`, `backend/tests/test_unified_artifacts.py`; modify subtitle input/document/API/export modules and necessary Companion client/editor wiring; add `web/e2e/unified-edit-export.spec.ts`. Update callers without overwriting platform branches wholesale.

- [x] First demonstrate legacy-format coupling: a genuine Workstation artifact layout cannot load as a Companion manifest. Require explicit resolution into the editor; reject missing/bad hashes, path escapes and symlinks; create no fake job.json.
- [x] Implement minimum artifact context retaining absolute/local time, languages and original word data; cover both translation directions, no translation and short tails. Keep engine caches/model settings unchanged.
- [x] Separate document construction/source validation from manifest loading. Preserve old fingerprint proofs and revision conflicts with retained drafts.
- [x] Complete video load, one-cue edit, save, same-backend reopen, PNG preview, ASS and burned clip from a Workstation result. Compare actual or frozen results from both engines and record provenance; frozen results prove interoperability only.
- [x] Browser tests must use an actual isolated API, not frontend mocks. Fix A4 style/timing/encoding tolerances first; verify the other 4999 cues, source media and old exports are unchanged.

**Exit:** isolated interoperability parts of A2/A3/A4/A11 passed. **Rollback: R0**, use the old entry and preserve separate new documents/exports. GPU A9 remains for P5.

## 5. P2: Persistent state and publication

**Files:** models, Alembic upgrade/backfill, projections and artifact service; add `task_operations.py`, `backend/tests/test_unified_operations.py`, `backend/tests/test_unified_publication.py`; extend schema/document conflict tests.

- [ ] First test unique origin mappings, separate retry attempts, video success with translation failure, no restart-to-running from old gui.json, and preserved legacy data after upgrading a temporary DB copy.
- [ ] Implement minimal additive task/operation/token/artifact schema. Only unified DB controls migrated-task scheduling. Legacy TaskStage/StageRun remain for unmigrated tasks, without two writable authorities for new tasks.
- [ ] Persist complete per-attempt required sets/prepared receipts under design 5.1 before individual publication, then commit the complete set/event. Editing uses immutable bodies plus DB CAS. Identical exports reuse verified results; changes create new results without overwrite.
- [ ] Run every M06/M08/M09 fault point including each output publication, pre-ready and pre/post-terminal commits and ENOSPC. Recover using receipts, reject stale attempts and never call partial sets successful.
- [ ] Unknown external outcomes become interrupted with explicit retry implications. Reuse valid translation checkpoints without claiming exactly-once billing.
- [ ] Verify repeatable upgrade, preserved failed-upgrade source copies and initially paused queue. Save schema diff, fault outcomes and hashes.

**Exit:** relevant A1/A3/A6/A11 plus DB-copy upgrade passed. **Rollback: R0 or R2**; old software uses its independent pre-migration copy, while new schema is preserved without downgrade.

## 6. P3: One execution core

**Files:** worker, queue/runs/task_runner/pipeline_support/task_control, Companion manager, recording/live workflows; extend unified operation tests; add `backend/tests/test_unified_execution.py`; retain queue/process/live regressions.

- [ ] First test competing executors, stale-token writes and cancellation while processes still run. Require one valid claim and rejection of stale state/artifact publication.
- [ ] Share scheduling/ownership across desktop helper and independent worker. Migrated tasks lose the bypass ThreadPool path. Unmigrated tasks remain on old entries without shared ownership.
- [ ] Dispatch four top-level operations; live translation/export are sequential children sharing parent attempt/token and never claim another slot. Preserve recording order, confirmation, Saozi policy, partial failures and snapshots without fixed seven-stage conversion.
- [ ] Use three tasks to verify order, priority, pause/resume and no interruption on reordering. Live work reserves the slot; finish its tail/release processes before starting queued recordings.
- [ ] Interrupt capture/ASR and fail translation/export. Resume only recorded content and valid checkpoints. Preserve gaps without inventing continuous source time; no automatic reconnect.
- [ ] Restart desktop and worker hosts separately and observe shared recovery/state behavior. Commit events with state, use short SSE sessions and keep long work outside HTTP request lifetimes.

**Exit:** A5/A6/A7 passed. **Rollback:** classify R0/R1/R2 per task, stop new executor/check locks/processes before switching, and never return modified-task ownership to legacy writers blindly.

## 7. P4: Shared product entry

**Files:** API assembly/routes/schemas plus proposed operation route/schema; Companion UI and Workstation library/queue integration, React routes/client/Vite; native/CLI/config integration. Extend unified edit/export e2e, add `web/e2e/unified-task-queue.spec.ts`, retain native-quit/settings tests.

- [ ] First test shared task facts across clients, old-route compatibility, revision conflicts, isolated settings drafts, SSE loss and cursor recovery.
- [ ] Route four operation kinds through `/api/v2/operations`; retain v2 library/queue semantics and move editing/templates to shared services. Legacy `/companion-api` and `/api/tasks` adapt only; generate OpenAPI types.
- [ ] Integrate library/sortable queue into Companion authoring using existing components. Share query keys/event refresh with polling fallback instead of retaining duplicate business pages.
- [ ] Wire independent task_root/settings_root/credential_root and global package under design 6.2. Preserve precedence/templates/ArcTime bindings/tags/archive/history, referencing protected authorization without login or copying secrets. Pass all M14 before activation integration.
- [ ] Keep dynamic loopback ports, native saves, dirty-exit confirmation and helper cleanup. CLI acquires the same locks/ownership rather than creating a third scheduler. No remote-GPU connection UI.
- [ ] Observe creation, queue, editing/settings, save/quit/reopen in actual browser/native windows; retain narrow-window, keyboard-focus, error and long-subtitle behavior. Update build/smoke and bilingual guides without installing the production App.

**Exit:** A8/A11 passed. **Rollback:** independent roots/old entries according to R0-R2; compatibility HTTP adapters may remain, without downgrading new data.

## 8. P5: Migration and actual platforms

**Files:** add `backend/app/services/task_import.py`; complete unified import/rollback fixtures and private local migration receipts/bilingual acceptance summaries. No secrets in receipts or private paths/raw logs in shareable summaries.

- [ ] First exercise prepare/verify/activate on copied fixtures: repeatability, ID collisions, missing source, corrupt documents, orphan exports, legacy fingerprints, batch cancellation, insufficient space and no credential copy. Import defaults to discovery without scheduling.
- [ ] Discover roots read-only, classify running/queued/terminal tasks, and report media references/space. Exclude active tasks; explicitly pause/withdraw old queued eligibility before a separate takeover.
- [ ] The same Supervisor follows design 6.1/6.4: stop old entries, hold locks/install-probe persistent seal, recompute generation and reprepare on changes. Activation binds global package/root_group/ownership; unmigrated tasks stay read-only and cancelling one batch never thaws another batch's dependency root.
- [ ] Run actual whisper.cpp -> edit/export on macOS and actual WhisperX -> edit/export separately on Linux CUDA and WSL ROCm. Record hardware/engine/model/version/artifacts. Real AI/live checks require explicit scope; absence is not a pass.
- [ ] Run M15/M16/M23-M27 for group-wide graceful/broken-version rollback, including partial batch cancellation and global-only changes. Seal every new root under one epoch; old work uses a separate copy, never the old native App on the default root.
- [ ] Only after explicit production migration/install authorization, take a consistent backup, stop old writers/check tasks/processes, activate a small first batch with queue paused, review before expanding, and stop on any hash/version/ownership mismatch.

**Exit:** A1-A11 all passed with separate actual platform evidence. Missing CUDA/ROCm stays blocked/unknown and prevents P6. **Rollback:** design section 7; no bulk old-data restore or resurrection of previously deleted content.

## 9. P6: Retire duplicate cores

**Files:** caller-verified old routes/entries/scheduler branches/pages only; update Vite/build/smoke/generated contracts, bilingual guides, AGENTS and handoff. Do not pre-authorize deletion of entire arctime or workstation directories.

- [ ] Inventory each entry's callers, remaining legacy tasks, compatibility-reader needs, rollback version and minimum retained files. Review the precise deletion boundary before execution.
- [ ] Stop creating legacy-format tasks; all supported launches use shared services before old writers retire. Required old readers remain read-only, without new legacy write paths.
- [ ] Remove only confirmed unused source. Preserve useful behavior assertions, migration/failure evidence, tasks, models, credentials, backups and media. Never skip failing tests to retire an entry.
- [ ] Run cumulative targeted checks plus actual browser/native and mandatory platform workflows, including clean install and old-data upgrade; update bilingual status with observed results/limits.
- [ ] Deliver capability -> unique entry -> tests/artifacts -> rollback mapping. Mark accepted only when no mandatory item remains.

**Exit:** A12 and cumulative A1-A11 passed. After new-format writes, retirement rollback uses R2/separate snapshots only; old binaries never write the new DB. Backup/media deletion is outside this plan.

## 10. Verification commands and evidence

Commands below are **historical design-review examples**; current commands, exits and scope are in [execution section 8](../../unified-architecture-execution-2026-10-22.md#8-complete-candidate-implementation-and-current-acceptance-ledger). Use a verified Python 3.11 backend environment from repository root. If `.venv` is absent, prepare an authorized isolated environment; do not alter global tools or invent success.

```bash
PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests/test_subtitle_document.py backend/tests/test_subtitle_api.py backend/tests/test_subtitle_export_snapshots.py backend/tests/test_subtitle_renderer.py -q
PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests/workstation/test_queue_service.py backend/tests/workstation/test_terminal_process_boundaries.py backend/tests/test_pipeline_support.py backend/tests/test_saozi_live.py -q
cd web
./node_modules/.bin/vitest run src/companion
./node_modules/.bin/tsc -b
./node_modules/.bin/vite build
```

Proposed `test_unified_artifacts.py`, `test_unified_operations.py`, `test_unified_publication.py`, `test_unified_execution.py` and `test_unified_import.py` run only after their phase creates them. New e2e scenarios must use isolated real APIs with an explicit webServer/data root; do not reuse mocked Workstation tests as complete-flow evidence.

Each receipt records phase/A IDs, candidate source identity, actual commands/exit codes, fixture/platform/root aliases, before/after hashes/counts, observations, failures/uncovered cases, ownership and rollback category. Discovery is not migration, schema upgrade is not runtime acceptance, and tests do not imply GPU or production-release acceptance.

## 11. Historical design-review delivery checks

- [ ] Bilingual designs/plans cross-link, with matching A1-A12, P0-P6 and R0-R2.
- [ ] Existing source/test references exist; proposed files are clearly labeled rather than advertised as runnable tools.
- [ ] Every phase defines files, dependencies, failure scenarios, exit gates and rollback, with no implicit dual writer or automatic legacy scheduling.
- [ ] Application source, tests, build scripts and deployment configuration are unchanged; no migration/install/business verification ran.

This preserves the design-review checklist, not a current claim of unchanged source or missing implementation authorization. Complete implementation was subsequently authorized; current delivery belongs to the execution ledger/candidate guide, with phase qualification still requiring matching evidence.

## 12. Execution supplements for the seven findings

Fields/tools below are proposed contracts, not runnable new migration/recovery commands. Create tests in their later implementation phases. Each item specifies failure cases, minimum changes and exit evidence.

<a id="rev-u1"></a>
### U1: P0 snapshot definition and P5 post-freeze validation

- [ ] In `backend/tests/test_unified_import.py`, first implement M03: change old document r to r+1 after verified and reject unchanged activation; crash after comparison/before transaction and observe no partial activation on reopen.
- [ ] Implement design 6.1/stable locking in task_import.py, covering task/global-package source_generation. Failed activation rolls back transactionally with queue paused. Retain actual lock-holder/process-shutdown evidence, generation differences and unique mappings.
- [ ] Exit only after M03 and prevention of old-root write restart. Withdraw Workstation entries when locks cannot exclude old APIs; an owner column alone is not exclusion evidence.

<a id="rev-u2"></a>
### U2: P2 recoverable artifact sets

- [ ] In test_unified_publication.py, first test each M08 member boundary and M09 failure; use test_unified_operations.py for M06 durable-revision/CAS interruptions. Establish that old publication behavior cannot satisfy these assertions.
- [ ] Implement immutable prepared receipts, ready registration, per-file publication and whole-set result transaction in task_operations.py/artifact services, including publication_id/child-step/attempt/token/set hashes. Live clip publication completes only its child result, never the active parent. Register durable template/document bodies only; isolate orphans.
- [ ] Pass every M06/M08/M09 point and inspect complete files/DB on reopen, not merely exit codes. Do not hide faults by rerunning models/AI.

<a id="rev-u3"></a>
### U3: P4 independent entry and P5 broken-version drills

- [ ] Add proposed `scripts/unified_recovery.py`, `backend/tests/test_unified_recovery.py`, and macOS build tests verifying independent recovery resources. First prohibit candidate-package imports/candidate executable startup while requiring a working old UI and readable newly saved document.
- [ ] Proposed interface: `--manifest PATH --mode legacy-browser|read-only --output-root PATH`. The design 7.3 manifest restricts all roots/epoch/helper/runtime/schema; reject output into any source/snapshot root or hash mismatch. legacy-browser uses only its separate old working copy; read-only reads same-epoch multi-root snapshots and exports task/settings/template/registry indexes. This command does not exist yet.
- [ ] Keep Launcher as helper parent with dynamic loopback port/separate ready/log. Freeze reader/render dependencies/runtime without candidate imports. Exclude authorization/configuration secrets from the old working copy for local editing recovery, without reverting authorization. If the candidate cannot boot, take a consistent SQLite/WAL snapshot per design 7.1 without candidate flush/export.
- [ ] Pass M15/M16 with helper/tool hashes, root roles and last registered revision. Do not promise unsaved browser input after a crash. The verified recovery bundle is a hard prerequisite for P5 production activation.

<a id="rev-u4"></a>
### U4: P0 inventory, P4 root wiring, P5 generation binding

- [ ] P0 produces design 6.2's field-preservation table. P4 first tests task_root changes preserving authorization/defaults/project bindings in unified-import and existing configuration/template tests; use no real credentials.
- [ ] Decouple LLMConfig/CredentialStore/TemplateStore with explicit root roles. New settings contain public defaults/references only; read old private secrets without changing their bytes, retaining locks/permissions. Namespace template conflicts by instance and require resolvable bindings.
- [ ] Pass all M14 fields/count/hash/zero-network assertions; generation mismatch prevents dependent-task activation. Global writes put the entire rollback group into R2; never restore revoked/refreshed authorization from snapshots.

<a id="rev-u5"></a>
### U5: P3 parent owns the execution slot

- [ ] In test_unified_execution.py, first write M11: first bilingual/styled clip exists while the live parent runs, child claims=0 and another top-level claim waits for parent release.
- [ ] Call existing child functions sequentially inside live processing, recording parent_operation_id/chunk/clip/partial failure without top-level submission. Failed draining preserves failures/releases processes; the parent cannot wait for a child queued behind itself.
- [ ] Pass M11/M12 with first-clip-before-parent-terminal evidence, continued capture after translation failure and zero recovery reconnects. Actual live M19 remains a separate P5 gate.

<a id="rev-u6"></a>
### U6: P0 registration, P2 unique mapping, P5 conflict handling

- [ ] First test M01/M02 counts/conflicts in test_unified_import.py, plus renamed roots, clone-as-restore and clone-as-independent-branch registration.
- [ ] Keep source_instance_id in an isolated migration registry without writing old roots or using paths/types as identity. Unique DB key is `(source_instance_id, legacy_id)`; use source_generation separately for content changes.
- [ ] Both instances' equal IDs import; repeated same-instance content duplicates nothing; changes after activation explicitly conflict without modifying unified documents. Exit only with identical bilingual/M01/M02 behavior.

<a id="rev-u7"></a>
### U7: Evidence by matrix for every phase

- [ ] P0 freezes F-media/F-edit/F-live/F-state/V and confirms F-media contains recognizable fixed speech for M17/M18. Missing actual GPUs/live sources/supported encoders blocks; substitutes cannot pass those rows.
- [ ] P1 runs M04/M05/M07/M20/M28; P2 M02/M05/M06/M08/M09/M20/M26; P3 M10/M11/M12 plus core guard probes; P4 M13/M14/M15/M16/M20/M24/M25/M27; P5 all M cases except P6's M21; P6 M21 and every retained-capability gate.
- [ ] M07 is lossless reference only (bounds<=1px/RMSE<=3.0); actual-API M28 uses libx264 CRF20 product output (bounds<=2px/RMSE<=8.0). Pin ROI/0-255 scale; product time boundary<=one output frame and SRT/ASS quantization<=1ms/10ms. Retain raw metrics/HTTP artifact identity, not a visual-consistency verdict.
- [ ] A records reference M receipts and distinguish frozen logic, actual GPU/capture and providers. Any mandatory unknown/blocked M prevents retirement. Include proposed test_unified_recovery.py and isolated recovery-bundle execution in P4/P5 gates.

## 13. Execution supplements for five residual findings

This section retains design constraints for new modules/tests/entries. Current state belongs to the execution ledger; document edits alone establish neither execution nor acceptance. Rv and U tests apply together.

<a id="rev-rv1"></a>
### Rv1: P2 dependency registration, P5 whole-group rollback

- [ ] Extend test_unified_import.py with M23: activate/edit A, cancel B, reject root thaw; also test whole-group R0/R1 without new writes and unknown external references. Assert unchanged A document/mapping/seal field by field.
- [ ] task_import.py/task_operations.py persist root_group_id and batch/task/global/media edges. Classify the strictest R level under group lock/transaction. Batch cancellation withdraws only preparation eligibility; the thaw receipt lists every withdrawn eligibility/zero remaining dependency before notifying guard to restore permissions.
- [ ] Require M23 and group R0/R1/R2 drills before expanding production batches. Any R2 member allows only independent old snapshots, never original-root thaw.

<a id="rev-rv2"></a>
### Rv2: P0 protection profile, P3/P4 one Supervisor

- [ ] P0 verifies old-root/lock/DB write protection and credential_root exceptions together on each platform; freeze original ACL/permissions/probe steps. Missing permission/filesystem capability/compatible layout blocks; marker files never substitute.
- [ ] Propose `backend/app/services/runtime_guard.py`, `backend/tests/test_unified_runtime_guard.py`; wire macOS helper/worker/start scripts so one Supervisor holds locks from before final validation to group closure, without starting a different lock-owning host after activation.
- [ ] Implement design 6.4 preparing/sealed records, persistent OS seal, read-only lock reacquisition and actual startup probes. Child death retains Supervisor locks; Supervisor death never automatically removes protection. Changed old entries/inodes/permissions block restart.
- [ ] M24 probes actual old GUI/CLI/DB rejection at every interruption and, on an authorized isolated platform, reboots to verify protection precedes old entries. Missing authorization blocks, never reboot the user's host implicitly. Keep credential fixtures accessible/outside bundles. Failed sealing leaves zero activation; restore permissions only after section 7.2 receipt.

<a id="rev-rv3"></a>
### Rv3: P4 multi-root reader, P5 disabled-candidate drills

- [ ] Add M25/M27 to test_unified_recovery.py: change only templates/defaults/project bindings without task edits, disable candidate boot and read latest fields offline. Missing roots/changed generation/mid-copy exit/ENOSPC reject complete and preserve originals.
- [ ] Launcher/reader enumerate DB/tasks/settings/global packages/registry/guard/media under design 7.3. Acquire group locks at one write barrier, create recovery_epoch, take consistent DB copy and compare every root before/after. Credential roots are protected references only, without secret copies.
- [ ] Export task documents, native template/default JSON, ArcTime projects/readable bindings, global generations and redacted source registrations without old-version writeback. Full private guard records stay local. Require M25/M27 and unbootable-candidate M16 before activation.

<a id="rev-rv4"></a>
### Rv4: P2 unique J decisions

- [ ] Parameterize test_unified_publication.py over 144 logical D/E/P/T/F combinations, requiring exactly one J00-J14 match; unsupported schema separately blocks. For every reachable J action also inject real temporary DB/file faults; logical enumeration cannot replace execution.
- [ ] Recovery exclusively stops original processes and validates current/historical execution proof before legacy stale-job revocation. Original-attempt file reconciliation is allowed, engine/AI calls prohibited; effective cancellation/new attempts prevent old-set adoption.
- [ ] M08/M09/M26 record J ID, DB snapshot, receipt_digest, attempt/token and published set, with unique outcomes for expired heartbeats/cancellation/historical C sets/partial files. Never collapse every not-ready state into isolation.

<a id="rev-rv5"></a>
### Rv5: P0 expected outputs, P1/P5 actual export entry

- [ ] P0 pins shared M07/M28 document/input frames/fonts/tools/color conversion/sample frame IDs/fixed ROI. Product settings remain existing libx264 fast CRF20/AAC/MP4 without a new FFV1 option.
- [ ] unified-edit-export.spec.ts saves through actual isolated API, submits kind=burn and downloads its returned artifact. Measure actual MP4 M28 timing/bounds/ROI; retain operation/artifact IDs/HTTP/real FFmpeg argv. Reference commands/stubs cannot replace product calls.
- [ ] Judge reference M07/product M28 separately with raw metrics. Product exceeding one frame/2px/RMSE8.0 fails without post-result threshold/ROI changes. Repeat M28 on actual P5 platforms; M22 encoder fallback cannot replace subtitle-burning evidence.
