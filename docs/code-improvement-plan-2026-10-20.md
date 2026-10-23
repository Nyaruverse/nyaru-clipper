# Nyaru-Clipper Code and Architecture Improvement Plan

Date: 2026-10-20. Chinese counterpart: [代码与架构改进计划](/Users/drm/project/nyaru-clipper/docs/code-improvement-plan-2026-10-20.zh-CN.md).

This document organizes **44 confirmed findings** from six review rounds into improvements that can be assigned and accepted individually: **9 High, 29 Medium, and 6 Low**. Original IDs #1–44 are retained. Related findings may be addressed together, but their IDs and separate acceptance requirements must not be merged or omitted.

**Status at consolidation on 2026-10-20: all 44 findings awaited fixes and acceptance.** “Confirmed” refers to evidence from the six reviews; that consolidation did not rerun every reproduction or implement fixes. The acceptance requirements below retain the conditions for closing findings. The proposed order alone is not a schedule or staffing commitment.

**Implementation update, 2026-10-21: phase-one #1–7, #20 and #21 are implemented on `codex/code-improvement-2026-10-21`.** See the [phase-one record](/Users/drm/project/nyaru-clipper/docs/phase1-improvement-results-2026-10-21.md) for individual observations, historical status and limits. At that stage35 findings remained pending; subsequent progress follows below. This does not establish acceptance of all44 findings or a complete release.

**Phase two complete: #32 → #43 → #44 → #12 are implemented following the [release-validation plan](/Users/drm/project/nyaru-clipper/docs/superpowers/plans/2026-10-21-phase2-release-validation.md) and freshly accepted together with phase one; final gate APPROVE, no blockers.** The ledger is **13 accepted within recorded scope /31 pending**. See [phase-two and combined results](/Users/drm/project/nyaru-clipper/docs/phase2-improvement-results-2026-10-21.md) for scope, platform limits and new evidence. Host `uv + pnpm` remains primary; this is not an all-platform release acceptance.

**Phase three complete: #22 → #23 → #8 → #9 → #10 implemented, individually verified and accepted together with the previous 13 corrections; final gate APPROVE, no blockers. At the end of phase three the ledger was 18 accepted within recorded scope / 26 pending.** See [phase-three and cumulative results](/Users/drm/project/nyaru-clipper/docs/phase3-improvement-results-2026-10-21.md): 1042 backend, 232 frontend and 17 workstation browser cases pass, with additional real Companion, CPU Docker and current macOS build/frozen-backend evidence. All changes remain uncommitted on the current branch; platform and real-service limits still apply.

**Phase four complete: #39 → #11 → #28 → #38 → #42 implemented in order, individually verified and freshly accepted together with the previous 18 corrections; final gate APPROVE, no blockers, maintenance debt WATCH. The phase-four closing ledger was 23 accepted within recorded scope /21 pending.** See [phase-four and cumulative results](/Users/drm/project/nyaru-clipper/docs/phase4-improvement-results-2026-10-21.md): 1107 backend, 244 frontend and 17 workstation browser cases passed, alongside that phase's CPU Docker, macOS build/frozen-backend, real FFmpeg/API and Companion workflows. Existing uncommitted edits and original worktrees were preserved; no commit, push, merge or App installation. Actual GPU/providers and installed native quit remained unaccepted.

**Phase five complete: #37 → #24 → #19 → #30 → #27 implemented in order, individually verified and freshly accepted with the previous23 corrections; final gate APPROVE, no blockers, maintenance WATCH. The phase-five closing ledger was28 accepted within recorded scope /16 pending.** See [phase-five and cumulative results](/Users/drm/project/nyaru-clipper/docs/phase5-improvement-results-2026-10-21.md):1152 backend,285 frontend,17 workstation browser cases pass, with that phase's CPU Docker/macOS build/frozen backend and actual subtitle editing/legacy recovery/ASS/ZIP/libass burn. Proven legacy compatibility and one-time historical nonnull-project cache migration limits are documented. Existing dirty edits/original worktrees remain, no commit/merge, Docker restored stopped. GPU/real providers/installed native quit remain unaccepted.

**Phase six complete: #26 → #31 → #29 → #41 → #33 implemented in order, individually verified and freshly accepted with all previous28 corrections; final independent gate APPROVE, no blockers, maintenance WATCH. The phase-six closing ledger was33 accepted within recorded scope /11 pending.** See [phase-six and cumulative results](/Users/drm/project/nyaru-clipper/docs/phase6-improvement-results-2026-10-21.md) for that phase's1251backend/308frontend/17workstation/21platform results, highlight export, Unicode/eight-line captions,5000-cue preview and platform bounds. Subsequent native quit and latest cumulative evidence follow in phase seven.

**Phase seven complete: #17 → #25 → #14 → #18 → #34 implemented in order, individually verified and accepted with all previous33 corrections; final independent gate APPROVE, specCompliance PASS, no blockers, maintenance WATCH. The phase-seven closing ledger was38 accepted within recorded scope /6 pending.** See [phase-seven and cumulative results](/Users/drm/project/nyaru-clipper/docs/phase7-improvement-results-2026-10-21.md):1329backend/317frontend/17workstation and21final platform scenarios pass. Actual native App two-task save/quit/same-build reopen includes a deselected5000-cue document; owned upload transfer, batched capacity reconciliation and pure API/bounded log reads have actual-path proof.355sources frozen;492baseline files/236original status records/99original Companion hashes protected, existing dirty edits retained. No commit/push/merge/installed App replacement, Docker restored stopped. Remaining#13,#15,#16,#35,#36,#40; real GPU/providers/full Compose/all fonts remain unaccepted.

**Phase eight complete: #40 → #36 → #13 → #15 → #35 → #16 implemented in order, individually verified and accepted with the previous38 corrections; final independent gate APPROVE, specCompliance PASS, no blockers, codeQualityStatus WATCH. Latest ledger:44accepted within recorded scope/0pending.** See [phase-eight and cumulative44-item results](/Users/drm/project/nyaru-clipper/docs/phase8-improvement-results-2026-10-21.md): current1357backend/327frontend/17workstation cases and22platform scenarios pass; latest actual native two-task save/quit/same-build reopen preserves all5000cues.355-file candidate,497baseline/249original status/C99 and nine explicit tombstones pass source-chain protection. No commit/push/merge/installed-App replacement; Docker restored stopped. The preceding38/6and remaining-ID list describe phase-seven history; this paragraph and current44-row matrix supersede them. Actual GPU/providers, full Compose and global responsive/theme certification remain outside acceptance.

The main direction is to repair data protection and recovery boundaries, consolidate duplicated business rules, narrow unnecessary reads and writes, and remove entry points verified to be obsolete. The evidence does not call for a rewrite or for Redis, Celery, Prefect, or a new frontend state management library.

## 1. Scope and baseline

The project is evaluated within its existing trusted local/LAN, single-user, single-GPU-worker scope. Public multi-tenancy and horizontal scaling are not goals of this plan.

| Code | Workspace and branch | Review baseline HEAD |
| --- | --- | --- |
| W | Main workstation: `/Users/drm/project/nyaru-clipper`, `feat/arctime-pro-plugin` | `e8ea71085cf5c6ff6f671499872f5c166d31f89b` |
| C | macOS Companion/Studio: `/Users/drm/.codex/worktrees/local-companion-macos/nyaru-clipper`, `codex/local-companion-macos` | `18ea3a0a7ee641cbb46d06d4348ebfa96dfc1dd2` |
| B | Web Companion comparison: `/Users/drm/.codex/worktrees/local-companion-web/nyaru-clipper`, `codex/local-companion-web` | `ccfb65176b3dd0451920694c5be17b19d856c0ff` |

The reviewed material includes uncommitted source, so **HEAD alone cannot reconstruct everything reviewed**. Before this consolidation, W/C/B had 47/56/53 existing Git dirty entries respectively. Before fixing an issue, preserve the actual diff and reconfirm the target checkout without overwriting existing manual edits.

W and C on each finding identify the primary evidence location. Whether shared C logic should also reach B requires a file-by-file comparison. macOS packaging, logging, and quit negotiation belong to the native application and must not be copied mechanically to Web. The highlight experiment worktree appeared only in early reviews and is not a separate implementation target in this list. An installed App is also not equivalent to current source.

## 2. Work packages, order, and dependencies

### 2.1 Proposed work packages

Each finding belongs to exactly one primary package. Package names organize responsibility; no owners have been assigned.

| Package | Responsible modules | Finding IDs | Package completion conditions |
| --- | --- | --- | --- |
| A: Data protection, recovery, and resource release | Pipeline, worker, Companion persistence, native shell | #1, #2, #3, #4, #5, #17, #20, #21, #22, #23, #25, #37 | Exceptions preserve published data; recovery can continue; resources and drafts have explicit ownership |
| B: Reproducible deployment and release validation | Build dependencies, Docker, installation/release scripts, health endpoint | #6, #7, #12, #32, #43, #44 | Build and start in the target clean environment, execute real tests, and provide trustworthy health signals |
| C: Editing, output, and state contracts | Both frontends; subtitles, highlights, exports, reports | #8, #9, #10, #11, #19, #24, #26, #27, #28, #29, #30, #38, #39, #41, #42 | Inputs, drafts, timelines, artifact ownership, and state agree through real entry points |
| D: Long-task overhead and read/write boundaries | Export records, uploads, live publishing, details, previews, SSE | #13, #14, #15, #18, #33, #34, #40 | Eliminate confirmed repeated full-data work while retaining required integrity checks |
| E: Consolidated rules and obsolete entry-point removal | Provider selection, ASR, shared export utilities, old pages | #16, #31, #35, #36 | Maintain each rule in one place, retain real entry points and valid tests, and justify deletion scope with reference evidence |

### 2.2 Implementation order

1. **Address the 9 High findings first: #1–7, #20, and #21.** A and B can proceed in parallel. Persisted credentials, orphan processes, stale caches, damaged finished videos, and side effects from rejected operations take precedence over general cleanup.
2. **Repair validation entry points in parallel.** #12, #32, #43, and #44 provide trustworthy paths for later releases. They cannot replace feature acceptance, and a passing script cannot justify skipping High findings.
3. **Then address visible errors and interrupted-operation recovery.** Prioritize the remaining A findings and Medium findings in C. #25 concerns unsaved drafts; #37 concerns access to saved revisions. Both must preserve data.
4. **Then reduce performance and maintenance costs.** Advance D and E through actual workflows. Low findings may accompany related module fixes, but deleted line counts cannot substitute for risk removal.

### 2.3 Coordinate implementation, but accept these findings separately

| Group | Shared boundary | Distinctions that must remain covered |
| --- | --- | --- |
| #11, #20, #21, #28, #39 | Task, stage, run, queue, report, and artifact projections | State synchronization, terminal-state recovery, side-effect-free rejection, report timing, and artifact kinds are five separate conditions |
| #4, #5, #23, #37 | Publishing, checkpoints, and identity | Protecting old videos, the SRT commit window, partial receipts, and old revision compatibility cannot be covered by one successful-retry test |
| #13, #15, #27 | Export identity and history | Smaller state records, incremental history processing, and format-specific dependencies require separate acceptance |
| #14, #22 | Upload ownership and failure cleanup | Avoiding full-media copies does not establish release of task admission state after failure |
| #8, #9, #10, #25, #38, #42 | Ownership of editing/request state | Settings, pagination, selection, native quit, task artifacts, and new-task drafts have different lifecycles |
| #29, #33, #41 | Subtitle layout and preview | Verify grapheme boundaries, small requests, and overflow rules separately; do not unify the entire UI state management system |
| #34, #40 | Detail reads and event refreshes | Both bounded individual reads and coalesced replay requests need changes |
| #2, #35, #36 | pipeline_support and execution entry points | Preserve exception cleanup first, then move shared utilities and delete dead entry points, avoiding removal of live execution paths |

## 3. Individual improvements and acceptance requirements

The following retains all44 original findings, proposals and separate acceptance conditions verbatim. The phase-eight cumulative record and per-ID matrix determine current bounded acceptance of all44 findings, with0pending. Section6 maps original evidence to review rounds. Code locations are original review evidence; some obsolete entry points have since retired under explicit manifests. Each finding retains an original code entry point; the original reports retain full call chains and reproduction details.

### #1 Download credentials enter ordinary logs (High | W)

- **Problem and evidence:** After a Cookie enters BBDown argv, it is logged in full. Persistence was observed with a synthetic value; real credentials were not read, and external disclosure was not established. Entry points: [downloader.py](/Users/drm/project/nyaru-clipper/backend/app/services/downloader.py:40), [command logger](/Users/drm/project/nyaru-clipper/backend/app/services/pipeline_support.py:62).
- **Improvement:** Redact commands, stdout, and stderr consistently at logging boundaries. Do not retain credential copies as diagnostic material.
- **Acceptance requirements:** Send a synthetic secret through the real argument construction and logging path. None of the relevant outputs may contain it, while ordinary errors remain diagnosable.

### #2 Exceptional exits leave ASR process groups alive (High | W)

- **Problem and evidence:** After a progress callback raises, a real harmless child process remains alive, while the outer layer may clear execution tracking. Entry point: [structured executor](/Users/drm/project/nyaru-clipper/backend/app/services/pipeline_support.py:194).
- **Improvement:** Cover registration, callback, logging, and persistence failures from the moment Popen succeeds. Terminate and wait for the process group before removing tracking.
- **Acceptance requirements:** Inject each failure separately and verify that children and descendants are reaped. Preserve existing semantics for normal completion, cancellation, and force termination.

### #3 Media/ASR caches lack content and parameter identity (High | W)

- **Problem and evidence:** Reuse of old audio after replacing a source with one of equal length was reproduced. Call-chain inspection confirmed missing ASR model/language identity. Entry points: [media_prep.py](/Users/drm/project/nyaru-clipper/backend/app/services/media_prep.py:96), [asr_whisperx.py](/Users/drm/project/nyaru-clipper/backend/app/services/asr_whisperx.py:221).
- **Improvement:** Bind media caches to source content and ASR caches to audio plus effective recognition/alignment parameters. Identity changes must invalidate dependent downstream caches.
- **Acceptance requirements:** Equal-length source replacement and changes to model, language, or alignment parameters trigger the necessary recomputation. Unchanged identities remain resumable; chunks from different configurations must not be mixed.

### #4 Failed export damages an existing finished video (High | W)

- **Problem and evidence:** Encoding overwrites the final path directly. An injected partial-write failure damaged the old video while its record remained. Entry point: [clip_export.py](/Users/drm/project/nyaru-clipper/backend/app/services/clip_export.py:59).
- **Improvement:** Encode to a unique temporary file in the same directory, validate it, then publish atomically. Define publication rules for concurrent exports of the same interval.
- **Acceptance requirements:** Encoding failure preserves the old file hash and usable record. Replacement occurs only on success; concurrency must not produce partial files or contradictory records.

### #5 The translation SRT/checkpoint commit window cannot recover (High | C)

- **Problem and evidence:** An interruption after SRT replacement but before saving its hash causes retry to reject valid new output using the old hash. Entry point: [saozi_translation.py](/Users/drm/.codex/worktrees/local-companion-macos/nyaru-clipper/backend/app/arctime/saozi_translation.py:140).
- **Improvement:** Reconstruct expected subtitles deterministically from validated persisted batches. Accept disk output only when it matches that expectation exactly, while continuing to detect manual edits.
- **Acceptance requirements:** Recovery after interruption at the publication boundary loses no translated batches. Arbitrary user edits must neither be wrongly accepted nor silently overwritten.

### #6 Clean macOS builds lack runtime dependencies (High | C)

- **Problem and evidence:** The build dependency closure lacks httpx, PyJWT, and crypto support required by GUI imports and RS256 verification. The original review did not rebuild the App. Entry point: [requirements-build.txt](/Users/drm/.codex/worktrees/local-companion-macos/nyaru-clipper/desktop/macos/requirements-build.txt:1).
- **Improvement:** Declare httpx and PyJWT[crypto] in the dependencies actually used for building, and check the entry point's dependency closure.
- **Acceptance requirements:** Build and launch the frozen application from a clean environment using the documented procedure. Authentication modules must import and synthetic RS256 verification must execute. If real login is not exercised, record it separately as unaccepted.

### #7 The Docker image omits migration configuration and version directories (High | W)

- **Problem and evidence:** The image copies app but omits Alembic files. An isolated missing-configuration scenario reproduced failure; the original review did not build the image. Entry point: [api.Dockerfile](/Users/drm/project/nyaru-clipper/infra/docker/api.Dockerfile:42).
- **Improvement:** Include the required configuration and migration version directories in the image, retaining Docker as the fallback deployment path.
- **Acceptance requirements:** The actual image must migrate a fresh temporary database and start the API. Also verify an upgrade of an existing test database; inspecting COPY text alone is insufficient.

### #8 Saving settings clears edits made while the request is in flight (Medium | C)

- **Problem and evidence:** A delayed save response unconditionally clears the draft, losing a later language selection while displaying a saved state. Entry point: [StudioSettings.tsx](/Users/drm/.codex/worktrees/local-companion-macos/nyaru-clipper/web/src/companion/StudioSettings.tsx:14).
- **Improvement:** Clear only draft values matching the submitted snapshot, or disable conflicting inputs during saving.
- **Acceptance requirements:** Edits made during a delayed response remain intact, or a clear disabled-input rule prevents them. Failures remain retryable, and the saved indicator is accurate.

### #9 Pagination becomes out of range after switching tasks (Medium | C)

- **Problem and evidence:** Switching from page two of a long task to a short task leaves an empty list and no pagination controls. This was reproduced with the actual component. Entry point: [CueEditor.tsx](/Users/drm/.codex/worktrees/local-companion-macos/nyaru-clipper/web/src/companion/CueEditor.tsx:22).
- **Improvement:** Constrain the page number to the current result count and reset necessary local state by task identity.
- **Acceptance requirements:** Switching from page two of a 21-cue task to a 2-cue task, or shrinking results through filtering, must show valid entries. Ordinary text edits must not reset all state.

### #10 Automatic selection overrides an intentional empty selection (Medium | C)

- **Problem and evidence:** Immediately after deselection, a parent effect selects the first cue again. Entry point: [Companion.tsx](/Users/drm/.codex/worktrees/local-companion-macos/nyaru-clipper/web/src/companion/Companion.tsx:108).
- **Improvement:** Separate initial selection on load from intentional user deselection. Only remove IDs that no longer exist.
- **Acceptance requirements:** Deselecting leaves zero selected cues, and bulk operations cannot accidentally change the first cue. Selection remains valid after switching documents or deleting cues.

### #11 Manual export leaves multiple state representations unsynchronized (Medium | W)

- **Problem and evidence:** After a failed export succeeds on retry, Task remains failed and v2 StageRun may retain its old state. Entry points: [state update](/Users/drm/project/nyaru-clipper/backend/app/services/pipeline_support.py:569), [v2 read model](/Users/drm/project/nyaru-clipper/backend/app/repositories/workstation.py:423).
- **Improvement:** Define the relationship between manual export and pipeline stages. Synchronize task, stage, run, and events through one transition entry point.
- **Acceptance requirements:** After failure followed by successful retry, every projection follows the chosen semantics. Errors in other stages must prevent blindly marking the entire task as success.

### #12 Release smoke selects a test that no longer exists (Medium | W)

- **Problem and evidence:** The current selection of `e2e/task-flow.spec.ts` returns No tests found. Entry point: [shared smoke script](/Users/drm/project/nyaru-clipper/scripts/_release_smoke_common.sh:161).
- **Improvement:** Align smoke coverage with real user entry points and existing tests, include the corresponding Companion delivery workflow, and check that tests are actually selected and executed.
- **Acceptance requirements:** Each supported release path runs valid user scenarios; a run that selects zero tests must fail. Nonempty `--list` output is a prerequisite, not complete acceptance.

### #13 Export history duplicates entire subtitles, amplifying progress and polling I/O (Medium | C)

- **Problem and evidence:** An isolated sample with 5,000 cues and 20 outputs produced an approximately 23.48 MB response and 38.30 MB persisted JSON. This is not a production benchmark. Entry point: [subtitle_exports.py](/Users/drm/.codex/worktrees/local-companion-macos/nyaru-clipper/backend/app/arctime/subtitle_exports.py:30).
- **Improvement:** Retain each immutable full snapshot once. Use summaries/references for lists and progress, stop useless polling in the completed idle state, and remain compatible with existing registries/receipts.
- **Acceptance requirements:** Lists do not embed full documents, and progress does not repeatedly rewrite every historical snapshot. Old outputs remain verifiable, downloadable, and reproducible; polling stops when complete.

### #14 Application-owned upload staging is copied in full again (Medium | C)

- **Problem and evidence:** The space check budgets one copy, but the uploaded file is then copied to source.mp4. Call-chain inspection confirmed double storage; the disk was not actually filled. Entry points: [saozi_api.py](/Users/drm/.codex/worktrees/local-companion-macos/nyaru-clipper/backend/app/arctime/saozi_api.py:28), [workflow.py](/Users/drm/.codex/worktrees/local-companion-macos/nyaru-clipper/backend/app/arctime/workflow.py:64).
- **Improvement:** Atomically move application-owned staging files on the same filesystem. Continue copying external user files, and budget derived artifacts separately.
- **Acceptance requirements:** Application-owned uploads no longer incur a second full-media copy. External originals remain unchanged, with explicit handling for insufficient space and cross-filesystem paths.

### #15 Live appends repeatedly scan and hash all old outputs (Medium | C)

- **Problem and evidence:** N segments cause approximately `2×Σ(1..N)` checks; 240 segments imply 57,840 checks. This is a calculation, not repeated encoding or a long-stream measurement. Entry point: [saozi_live.py](/Users/drm/.codex/worktrees/local-companion-macos/nyaru-clipper/backend/app/arctime/saozi_live.py:54).
- **Improvement:** Process only new segments or segments whose translation/template inputs have changed. Retain full validation at recovery, download, and other necessary boundaries.
- **Acceptance requirements:** Count real append calls and demonstrate that unchanged history no longer causes quadratic checking. Changed inputs update the right outputs, and damaged artifacts remain detectable.

### #16 Old pages and dedicated tests remain in the maintenance scope (Medium | W)

- **Problem and evidence:** TaskDetailPage and NewTaskPage have no production references. The 1,558 lines are an upper bound for candidate pages plus dedicated tests, not a promised net deletion. Entry points: [actual routes](/Users/drm/project/nyaru-clipper/web/src/router.tsx:11), [old smoke test](/Users/drm/project/nyaru-clipper/web/src/test/smoke.test.tsx:65).
- **Improvement:** Move valid assertions to real routes before deleting dead pages, obsolete supporting wrappers, and dedicated old tests.
- **Acceptance requirements:** Current workstation entry points retain valid behavior checks, and no dangling references remain. Preserve consumed legacy APIs/types and ExistingReviewWorkspace.

### #17 App startup truncates the previous log (Medium | C)

- **Problem and evidence:** A Foundation temporary-file experiment confirmed that createFile truncates the previous log. This was not an installed-App restart acceptance check. Entry point: [App.swift](/Users/drm/.codex/worktrees/local-companion-macos/nyaru-clipper/desktop/macos/App.swift:52).
- **Improvement:** Create only when absent and append, or use bounded rotation.
- **Acceptance requirements:** After prepopulating a failure log and restarting, old content or a rotated copy remains, and new logging continues. Logs must also follow #1's redaction principles.

### #18 Registering artifacts one by one repeatedly scans the entire directory (Low | W)

- **Problem and evidence:** N chunks trigger approximately N full-directory measurements. Static call-chain inspection confirmed this; actual latency was not measured. Entry point: [storage.py](/Users/drm/project/nyaru-clipper/backend/app/services/storage.py:85).
- **Improvement:** Refresh capacity once after each registration batch, reusing one measurement implementation.
- **Acceptance requirements:** Batch registration and recovery of old artifacts have scan counts bounded by batches, while final capacity is correct.

### #19 Time formatting generates seconds that its own parser rejects (Low | C)

- **Problem and evidence:** 59.99 becomes 00:60.0 and 3599.99 becomes 59:60.0; the existing parser rejects both. Entry point: [companionApi.ts](/Users/drm/.codex/worktrees/local-companion-macos/nyaru-clipper/web/src/companion/companionApi.ts:74).
- **Improvement:** Round total duration to integer tenths of a second before splitting minutes and seconds.
- **Acceptance requirements:** Minute/hour carry boundaries never produce 60 seconds. Formatted output can be parsed again within the existing supported range, with error consistent with display precision.

### #20 Interruption between task termination and queue finalization permanently blocks the queue (High | W)

- **Problem and evidence:** An isolated database containing a success job and running queue entry causes the next claim to return None. Entry points: [task_runner.py](/Users/drm/project/nyaru-clipper/backend/app/services/task_runner.py:523), [worker.py](/Users/drm/project/nyaru-clipper/backend/app/worker.py:264).
- **Improvement:** Commit terminal state and queue completion in one locked transaction, with idempotent recovery for historical inconsistent combinations. Shorter timeouts cannot replace this fix.
- **Acceptance requirements:** Following interruption at the terminal-state boundary, a new worker session can claim the next item. The original task's terminal state, queue, and run history agree, and repeated recovery is safe.

### #21 Rejected requeue operations already delete files and commit state (High | W)

- **Problem and evidence:** A real batch operation returns rejected, but task/job are already pending, subtitles have been deleted, and a run record has been added. Entry points: [retry side effects](/Users/drm/project/nyaru-clipper/backend/app/repositories/tasks.py:452), [batch commit](/Users/drm/project/nyaru-clipper/backend/app/api/routes/workstation_tasks.py:172).
- **Improvement:** Check rejection conditions first under the queue lock. Roll back database changes per item and perform file cleanup in a recoverable step after acceptance. A savepoint cannot undo unlink.
- **Acceptance requirements:** Rejection leaves tasks, stages, jobs, runs, artifact records, and files unchanged. Valid items in mixed batches are accepted normally.

### #22 A second disk failure in error handling leaves task admission locked (Medium | C)

- **Problem and evidence:** Injecting ENOSPC into both upload and error recording produces an initial 500. After writes recover, the next task still returns 409. Entry point: [upload exception handling](/Users/drm/.codex/worktrees/local-companion-macos/nyaru-clipper/backend/app/arctime/saozi_api.py:52).
- **Improvement:** Unconditionally release active in finally. Neither error-log persistence nor staging deletion may prevent release; check equivalent cleanup in manager.run.
- **Acceptance requirements:** After the dual failure above and after deletion failure, restoring writes allows the next task without a restart. Preserve failure evidence where possible.

### #23 A partially written receipt permanently blocks the same export (Medium | C)

- **Problem and evidence:** Injecting ENOSPC after 10 receipt bytes leaves the finished output unpublished. Later retries still fail on malformed JSON. Entry point: [receipt recovery](/Users/drm/.codex/worktrees/local-companion-macos/nyaru-clipper/backend/app/arctime/subtitle_exports.py:230).
- **Improvement:** Write a complete temporary receipt in the same directory, then publish atomically and exclusively. Preserve corrupt evidence before recovering unpublished outputs.
- **Acceptance requirements:** Retry succeeds after a partial-write interruption, with source files unchanged. Existing finished outputs that cannot be verified must still be protected from overwrite; validation failures cannot simply be ignored.

### #24 Cue merging assumes chronological order that is not guaranteed (Medium | C)

- **Problem and evidence:** Merging `[1,5]` with the following cue edited to `[0,8]` produces `[1,8]`, losing the earlier display interval. Entry point: [mergeCues](/Users/drm/.codex/worktrees/local-companion-macos/nyaru-clipper/web/src/companion/subtitleDocument.ts:104).
- **Improvement:** Use the minimum selected start and maximum selected end, preserving the existing text and style order.
- **Acceptance requirements:** Editing chronological order before merging produces `[0,8]`, with subtitles still visible at 0.5 seconds. Saving and exporting use the same interval.

### #25 Native quit does not negotiate unsaved drafts (Medium | C)

- **Problem and evidence:** Quitting before the 650 ms autosave or after a save returns 409 can lose an in-memory draft. This was reproduced with the real hook plus an independent WKWebView host, not the complete installed-App workflow. Entry points: [useSubtitleDocument](/Users/drm/.codex/worktrees/local-companion-macos/nyaru-clipper/web/src/companion/useSubtitleDocument.ts:69), [native quit](/Users/drm/.codex/worktrees/local-companion-macos/nyaru-clipper/desktop/macos/App.swift:111).
- **Improvement:** Query dirty state before stopping the backend, and wait for a successful save or explicit discard. Save failure must allow cancelling quit.
- **Acceptance requirements:** Cover immediate quit, save failure, cancelled quit, and explicit discard. Editing, quitting, and reopening the installed App must retain revisions the user chose to save. Merely adding a delay is insufficient.

### #26 Default highlight ranges incorrectly use the subtitle endpoint (Medium | W)

- **Problem and evidence:** For 60-second media, a 10–30-second shot, and subtitles ending at 20 seconds, the default range is 8–20 instead of 8–32. Entry point: [highlights.py](/Users/drm/project/nyaru-clipper/backend/app/services/highlights.py:93).
- **Improvement:** Use trustworthy probed media duration as the upper bound, preserving explicit missing-duration semantics when unavailable.
- **Acceptance requirements:** The original scenario produces 8–32. Cover trailing silence, no subtitles, and missing duration. Frontend submitted ranges must match displayed ranges.

### #27 ASS/burn-in depends on an unrelated ArcTime template (Medium | C)

- **Problem and evidence:** Deleting ATPJ makes an old task's ASS request return 409. Removing the unrelated project ID succeeds with identical content. Burn-in shares the precheck, but the original review did not encode video. Entry point: [subtitle_exports.py](/Users/drm/.codex/worktrees/local-companion-macos/nyaru-clipper/backend/app/arctime/subtitle_exports.py:173).
- **Improvement:** Read the project template and include it in output identity only for ArcTime ZIP. The frontend sends fields applicable to each format.
- **Acceptance requirements:** Deleting or switching ATPJ neither blocks nor regenerates identical ASS/burn-in outputs. ArcTime still validates template integrity; add a check of the actual burn-in path.

### #28 The final report still says running (Low | W)

- **Problem and evidence:** The actual runner reaches success, but the downloaded report still lists the task and report stage as running. Entry point: [reporting.py](/Users/drm/project/nyaru-clipper/backend/app/services/reporting.py:31).
- **Improvement:** Publish the final report after terminal state is determined. If retaining an in-progress snapshot, distinguish it clearly from the final report.
- **Acceptance requirements:** Use the actual runner to check reports against final state in success and failure scenarios. Testing the template function alone does not cover timing.

### #29 Automatic line wrapping splits combined characters (Low | C)

- **Problem and evidence:** ZWJ emoji and flags are split across ASS lines. The original review did not inspect final font pixels. Entry point: [subtitle_render.py](/Users/drm/.codex/worktrees/local-companion-macos/nyaru-clipper/backend/app/arctime/subtitle_render.py:18).
- **Improvement:** Wrap only at complete grapheme boundaries and align frontend line estimation. Continue using the agreed codepoint indices for emphasis ranges.
- **Acceptance requirements:** Narrow-region samples such as `👩‍💻` and `A🇨🇳` keep character combinations intact, preserve emphasis indices, and are checked with actual font rendering.

### #30 The export model rejects four-digit clip numbers (Low | C)

- **Problem and evidence:** The generator can produce clip-1000.mp4, but input accepts only three digits. The actual model was checked; a thousand segments were not recorded. Entry points: [live_state.py](/Users/drm/.codex/worktrees/local-companion-macos/nyaru-clipper/backend/app/arctime/live_state.py:149), [subtitle_inputs.py](/Users/drm/.codex/worktrees/local-companion-macos/nyaru-clipper/backend/app/arctime/subtitle_inputs.py:26).
- **Improvement:** Align filename validation with the generator's minimum-three-digit rule, retaining the restriction to completed clips belonging to the current task.
- **Acceptance requirements:** Both 999 and 1000 work through manual and automatic exports. Invalid paths, incomplete files, and files outside the task remain rejected.

### #31 CLI/GUI duplicate provider configuration interpretation and diverge (Medium | C)

- **Problem and evidence:** With ChatGPT selected in the GUI and old DeepSeek configuration retained, new CLI tasks choose the old provider and ChatGPT resume fails. Selection and CLI branches were checked; no real provider requests were made. Entry points: [cli.py](/Users/drm/.codex/worktrees/local-companion-macos/nyaru-clipper/backend/app/arctime/cli.py:17), [companion_llm.py](/Users/drm/.codex/worktrees/local-companion-macos/nyaru-clipper/backend/app/arctime/companion_llm.py:13).
- **Improvement:** Share the rule: honor the existing task's pinned provider/model first; otherwise read current configuration. Reject unsupported choices explicitly without silently switching providers.
- **Acceptance requirements:** Both entry points make the same selection from identical configuration. Resume respects task records; a valid old key cannot cause implicit fallback.

### #32 Locked-dependency validation includes latest-version resolution (Medium | W)

- **Problem and evidence:** With the real check script and controlled resolver output, changing only visible versions switches success to failure. This is not proof that today's online resolution fails. Entry point: [export_backend_requirements.sh](/Users/drm/project/nyaru-clipper/scripts/export_backend_requirements.sh:186).
- **Improvement:** Separate deterministic validation from explicit upgrades and define the authoritative lock source. Preserve CUDA/ROCm platform contracts and never hand-edit generated requirements.
- **Acceptance requirements:** With the repository fixed, newly visible versions do not affect validation, while actual declaration drift remains detectable. Installing on one platform is not blocked by re-resolving an unrelated platform.

### #33 Every scene preview sends and validates the entire subtitle document (Medium | C)

- **Problem and evidence:** Switching between two scenes in a 5,000-cue document sends approximately 1.53 MB each time. Approximately 7.67 GB for a complete viewing is an estimate, not a measurement or a per-frame request rate. Entry point: [DocumentOverlay.tsx](/Users/drm/.codex/worktrees/local-companion-macos/nyaru-clipper/web/src/companion/DocumentOverlay.tsx:35).
- **Improvement:** Send only active cues, global styles, time/dimensions, and source identity. Avoid reconstructing the whole document for source validation. Saving and exporting continue to use the full document.
- **Acceptance requirements:** Request size follows the active cue count rather than full document length. Overlapping cues and styles display correctly, source validation remains intact, and caching across scene changes still works.

### #34 Detail queries read entire logs and create directories (Medium | W)

- **Problem and evidence:** Producing an 11-character summary reads approximately 10 MB twice. Detail queries also recreate missing directories; read-only-disk failure was not simulated. Entry point: [summarize_stage_log](/Users/drm/project/nyaru-clipper/backend/app/services/storage.py:49).
- **Improvement:** Separate pure path resolution from mkdir. Use explicitly bounded tail reads or persisted summaries.
- **Acceptance requirements:** Reading bytes from a 10 MB log is bounded, with explicit handling of empty logs, trailing blank lines, and very long lines. No detail read creates directories.

### #35 Superseded ASR entry points, dedicated tests, and code maps remain (Medium | W)

- **Problem and evidence:** Whole-tree references confirm no product callers for old direct execution, manifest publishing entry points, or the unstructured runner. The 224 lines of relevant declarations are not a final net deletion count. Entry points: [asr_whisperx.py](/Users/drm/project/nyaru-clipper/backend/app/services/asr_whisperx.py:723), [old runner](/Users/drm/project/nyaru-clipper/backend/app/services/pipeline_support.py:86).
- **Improvement:** Move valid assertions to current chunk execution and publication paths. Remove obsolete entry points and dedicated helpers, and update AGENTS maps.
- **Acceptance requirements:** No dangling source, dynamic, test, or documentation references remain. Current inference, recovery, and publication retain effective test coverage. Preserve shared manifests and `_persist_asr_artifacts`. Section 5 covers associated cleanup without adding IDs.

### #36 Generic file export depends back on legacy workstation ORM/scheduling (Medium | C)

- **Problem and evidence:** Reusing ordinary logging/process functions imports SQLModel, database, and event layers. Module loading was measured; this does not establish database access or package size. Entry point: [export_encoding.py](/Users/drm/.codex/worktrees/local-companion-macos/nyaru-clipper/backend/app/services/export_encoding.py:7).
- **Improvement:** Move shared utilities into a module without scheduling/DB dependencies. Give encoding a narrow configuration; remove no-longer-needed Companion dependencies only after full validation.
- **Acceptance requirements:** Importing generic export in a clean process does not load legacy ORM/DB/event modules. Preserve Windows AMF fallback, path replacement, and error handling; the frozen package must actually work.

### #37 Subtitle source identity incorrectly includes runtime diagnostics (Medium | C)

- **Problem and evidence:** Successful automatic export clears error fields. Source and edited document bytes remain unchanged, but revision GET/POST returns 409. Entry point: [base_document](/Users/drm/.codex/worktrees/local-companion-macos/nyaru-clipper/backend/app/arctime/subtitle_document.py:86).
- **Improvement:** Fingerprint only media, subtitles, and necessary timeline/canvas information, excluding diagnostics and export state. Design compatibility or migration for revisions saved under old fingerprints.
- **Acceptance requirements:** After export failure, saving a revision, and successful export retry, that revision remains readable and writable. Real source changes still cause rejection, and the fix must not invalidate existing revisions. This finding concerns lost access, not file deletion.

### #38 New export results lose task ownership (Medium | W)

- **Problem and evidence:** After exporting A and returning to cached B, A's download link remains beneath B's title. This was reproduced with the actual component. Entry point: [ExistingReviewWorkspace.tsx](/Users/drm/project/nyaru-clipper/web/src/workstation/features/task-overview/ExistingReviewWorkspace.tsx:338).
- **Improvement:** Define workspace lifecycle by taskId, or write results into the corresponding task query cache. Reduce duplicated local state without task ownership.
- **Acceptance requirements:** Switching A → cached B never shows A's artifacts. An asynchronous export finishing after a task switch still writes back to A, whose normal results remain visible.

### #39 Artifact producers and both readiness mappings disagree (Medium | W)

- **Problem and evidence:** Neither read model recognizes the actually registered clip_export kind; readiness stays missing even when every task status is success. Entry points: [producer registration](/Users/drm/project/nyaru-clipper/backend/app/services/clip_export.py:251), [v2 mapping](/Users/drm/project/nyaru-clipper/backend/app/repositories/workstation.py:63).
- **Improvement:** Share the mapping between stored kinds and public semantics across both detail versions and list SQL. Merging the entire repository layer is unnecessary.
- **Acceptance requirements:** Produce fixtures through the real registration function. Existing files show ready, match the ready filter, and do not match missing. After removing a file, every read model consistently reports it unavailable.

### #40 Historical event replay triggers duplicate snapshot queries per event (Medium | W)

- **Problem and evidence:** With a cached query and delayed responses, 100 events start 100 summary fetches. Whole-system load was not measured. Entry point: [useWorkstationEvents.ts](/Users/drm/project/nyaru-clipper/web/src/workstation/api/useWorkstationEvents.ts:52).
- **Improvement:** Coalesce invalidations by queryKey/taskId within short replay windows, and propagate AbortSignal through HTTP. Preserve durable events and disconnection cursors.
- **Acceptance requirements:** Replaying the same 100 events produces requests bounded by coalescing windows, and stale requests receive cancellation. The final snapshot is correct, and reconnection preserves event semantics.

### #41 Two automatic subtitle layouts have diverging overflow protection (Medium | C)

- **Problem and evidence:** The same 8-line, large-font subtitle changes from rejected to accepted after enabling bold, while its first line is completely invisible. Actual libass/PNG output confirmed this; a final video was not burned in. Entry points: [style dispatch](/Users/drm/.codex/worktrees/local-companion-macos/nyaru-clipper/backend/app/arctime/subtitle_style.py:134), [document layout](/Users/drm/.codex/worktrees/local-companion-macos/nyaru-clipper/backend/app/arctime/subtitle_render.py:90).
- **Improvement:** Share automatic layout and overflow rules across basic styles, advanced styles, and edited documents. Preserve input adapters and the separate semantics of free positioning.
- **Acceptance requirements:** Every entry point consistently rejects or explicitly handles the original overflow sample. Preview, ASS, and actual burn-in agree, with no silent text clipping; free positioning still follows its contract.

### #42 An old source-check response overwrites a newer task draft (Medium | W)

- **Problem and evidence:** Switching to local input while checking Bilibili source A lets A's late response switch the page back to the old source. This was reproduced with the actual component; no real task was created. Entry point: [NewTaskDrawer.tsx](/Users/drm/project/nyaru-clipper/web/src/workstation/features/task-create/NewTaskDrawer.tsx:150).
- **Improvement:** Attach source, URL, and draft generation to each check. The reducer accepts only results valid for the current draft; cancelling requests cannot replace identity guards.
- **Acceptance requirements:** After switching to local input, changing URL, or discarding and reopening, late old responses cannot alter the new draft. Current valid checks still take effect normally.

### #43 The health endpoint claims database health without probing it (Medium | W)

- **Problem and evidence:** When a temporary database becomes unreachable at runtime, tasks returns 500 while health returns 200/database=ok. Entry point: [health.py](/Users/drm/project/nyaru-clipper/backend/app/api/routes/health.py:12).
- **Improvement:** Perform a bounded real DB probe for readiness. If adding separate liveness, define its meaning and update startup, smoke, and documentation together.
- **Acceptance requirements:** Across normal operation → failure → recovery, health signals match actual dependencies and never report success on failure. Callers honor the contract. Original evidence does not cover storage writability, which is not counted as another finding.

### #44 The specified Chrome path does not reach launch options (Low | W)

- **Problem and evidence:** The environment variable is assigned to use.executablePath, but the real runner's effective launchOptions omit it. No browser was launched. Entry point: [playwright.config.ts](/Users/drm/project/nyaru-clipper/web/playwright.config.ts:8).
- **Improvement:** Set `use.launchOptions.executablePath`, preserving default behavior when unset.
- **Acceptance requirements:** The runner resolves the specified path and actually launches the selected available browser. The default path still works without the environment variable.

## 4. Evidence and records required to close findings

Before a fix, confirm that the current code still has the issue, then implement the selected scope in an isolated branch/workspace. For #3, #5, #13, #20, #23, and #37, which involve old data formats, handle existing state; success for new tasks alone is insufficient.

Retain the following records before closing each finding. Where no owner or commit exists, write “unassigned/none” rather than inferred values.

| Field | Required content |
| --- | --- |
| Finding | Original ID, target checkout, actual HEAD, and scope of workspace differences |
| Ownership and status | Owner; awaiting fix → in progress → awaiting acceptance → accepted; state the actual condition when blocked |
| Change | Implementation commit/patch, compatibility and migration strategy, other IDs affected |
| Regression | Evidence of the original defect before fixing; expected results for each post-fix condition; necessary adjacent-function checks |
| Actual workflow | Observations from the corresponding UI/API/native/packaging path, explicitly identifying simulated external boundaries |
| Data protection | Whether source media, subtitle revisions, published videos, and credentials are preserved as required; never write secrets into evidence |
| Conclusion | Acceptance date, evidence location, uncovered environments, and rollback method |

Editing a function, passing tests, building successfully, or creating a new installer does not automatically mean “accepted.” In particular, a passing defect-reproduction test usually means **the defect still exists**; post-fix assertions must verify expected behavior. Limit acceptance to platforms actually exercised. Do not extend local results to all CUDA/ROCm/Docker/macOS environments.

## 5. Cleanup scope and capabilities to preserve

The following notes may be handled with the main findings but do not increase the count of 44:

- **Old wrappers associated with #16:** After moving real-route behavior and valid assertions, check references before removing old AppShell/WorkspacePage wrappers.
- **The cleanup entry point associated with #35:** The approximately 39-line entry point has only test callers. Explicitly retain it for a stated purpose or remove it; do not wire automatic deletion of recovery material into successful flows just to connect it.
- **The direct orjson declaration associated with #35:** Current source/configuration has no consumer. Remove the direct declaration only after rechecking dependencies, and update generated artifacts with the generator; do not hand-edit locked requirements.
- **Unused translation_fallback_model_name:** This was only a single-line cleanup note in the previous round. The ineffective option may be removed; do not add unrequested automatic provider fallback.
- **SQLModel/pydantic-settings associated with #36:** Remove Companion dependencies only after decoupling, whole-tree dependency checks, and package acceptance establish they are no longer needed.

Preserve consumed legacy APIs and types, ExistingReviewWorkspace, both workstation and Companion entry points, distinct VOD/live lifecycles, StageRun's historical role, shared ASR inference and publication utilities, CSS fallback preview during recording, libass preview after completion, and boundary validation for paths, sources, and model output.

Both rendering entry points in #41 have production consumers. Consolidate their rules first; similar code alone is not grounds for deletion. Unsupported circular-import claims, runtime cache claims, migration speculation, and already disclosed installation-path limitations are not additional confirmed findings. Existing isolated size measurements, call counts, and static complexity do not establish real latency, package size, or production failure rates.

## 6. Review sources and evidence limits

| Round | Original IDs | High/Medium/Low | Original report |
| --- | --- | --- | --- |
| R1 | #1–19 | 7/10/2 | [Full-project review](/Users/drm/project/nyaru-clipper/.omo/evidence/full-project-code-audit-2026-10-20.zh-CN.md) |
| R2 | #20–24 | 2/3/0 | [Second round](/Users/drm/project/nyaru-clipper/.omo/evidence/second-pass-code-audit-2026-10-20.zh-CN.md) |
| R3 | #25–30 | 0/3/3 | [Third round](/Users/drm/project/nyaru-clipper/.omo/evidence/third-pass-code-audit-2026-10-20.zh-CN.md) |
| R4 | #31–36 | 0/6/0 | [Fourth-round architecture review](/Users/drm/project/nyaru-clipper/.omo/evidence/fourth-pass-architecture-audit-2026-10-20.zh-CN.md) |
| R5 | #37–40 | 0/4/0 | [Fifth-round architecture review](/Users/drm/project/nyaru-clipper/.omo/evidence/fifth-pass-architecture-audit-2026-10-20.zh-CN.md) |
| R6 | #41–44 | 0/3/1 | [Sixth-round architecture review](/Users/drm/project/nyaru-clipper/.omo/evidence/sixth-pass-architecture-audit-2026-10-20.zh-CN.md) |
| Total | #1–44 | **9/29/6** | Original IDs retained; unnumbered cleanup notes excluded |

This document gives each finding's impact, improvement direction, and acceptance requirements and can serve as a standalone implementation checklist. Original reports and reproduction material reside locally under Git-ignored `.omo/evidence/`; links use absolute local paths. When sharing with collaborators, map source paths to the target checkout and separately archive necessary redacted reproduction material for the selected fixes. Do not assume collaborators have these local worktrees, temporary directories, or virtual environments, and do not publish runtime data wholesale.

Evidence across the six rounds includes call-chain inspection, isolated reproductions using real components/routes, fault injection, partial rendering, and data-volume measurements. It **does not cover every real GPU/model, external provider, long live stream, clean installation matrix, or complete installed-App workflow**. Some Python checks used pytest 9.1.1, outside the main backend's declared `<9` bound; they are not acceptance of its clean dependency environment. The individual findings state the limits of native evidence for #25, pixel evidence for #41, and other scoped observations.

This task only consolidates documentation and indexes; it changes no implementation, real tasks, recording/monitoring state, dependencies, or Git branches. These 44 findings are the confirmed list from six rounds, not a guarantee that every possible issue has been exhausted.
