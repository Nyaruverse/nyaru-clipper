# Current handoff — 27 October 2026 (Asia/Shanghai)

Document updated on 27 October; the live-state snapshot was taken at **23:57 on 26 October (Asia/Shanghai)**.

**The formal App is 0.1.21 build 33, started into Watch Workbench; the queue is paused.** This section supersedes current/installed/candidate-only wording in older sections. Historical versions and Git tables apply only to their original observation dates.

## Current state and entry points

- Installed App: `/Users/drm/Applications/Nyaru Clipper.app`.
- Registered runtime: `/Users/drm/Library/Application Support/Nyaru Clipper/unified/runtime.json`. Reuse the existing model, credentials and settings; do not initialize a replacement data domain.
- Read-only live checks confirmed the App version, running backend and API: four real test tasks remain, the final task and all four operations succeeded, and the queue is paused. The API port changes on launch; do not hardcode a previous test port.
- The user selected **Watch Workbench with highlight review as the core workflow**. Translation readiness, detected language persistence, the unrelated default 30-second preclip, separate/combined output playback, compact layouts, title refresh and null-revision copy were fixed.
- See [the fixes and real-video receipt](watch-workbench-real-fixes-2026-10-26.md). The [earlier 0.1.20 installation receipt](watch-workbench-install-2026-10-26.md) remains historical.

## Confirmed real-video validation

Final task: `7a69c98888d15620b3aa11e9fba5dbc9`, titled `真实高光完整复测 · build30 · 自动日语`. The title's build30 is the original test label; **the installed build is 33**.

The same 328.300-second real recording completed native import, automatic Japanese recognition with 50 cues, native-button admission of actual DeepSeek translation for 50/50 cues, four highlight candidates covering 40.15%, reversed `[2,0]` reviewed ranges and bilingual export. The two clips are 42.100 and 63.300 seconds; the combined output is **105.421333 seconds**. All three downloaded files fully decoded. Web playback naturally reached the end. The user directly confirmed native visible playback; native capture limitations are not presented as an automatic pixel pass.

The full processing run used build30. Builds31–33 changed CSS/build metadata only, with identical backend Python and frontend JS content hashes; final build33 layout and Web playback were checked separately. Earlier receipts record 365 frontend tests, 139 related backend tests and 32 native/translation integration checks, plus 62 focused boundary checks after calibration. This handoff refresh did not repeat those tests, recognition, translation or export.

Primary evidence directory: `/Users/drm/.codex/worktrees/highlight-subtitle-macos/nyaru-clipper/.omo/evidence/watch-workbench-fixes-20261026/`. Start with `final-install-runtime.json`, `final-media-validation.json`, `final-web-playback-later.json`, `native-human-acceptance.json`, `data-preservation.json` and `review.md`. The current startup/API snapshot is `/Users/drm/project/nyaru-clipper/.omo/evidence/handoff-refresh-20261026-workbench/before.json`.

## Source checkouts and version control

On 27 October the user authorized the complete commit and push. Source, regression tests, generated contracts, packaging and bilingual handoffs are grouped into commits; the primary checkout publishes documentation only. Shared frontend/contracts are synchronized, with existing Windows-specific Web backend differences preserved.

| Checkout | Local branch | Publication target | Implementation milestone (before documentation commit) |
|---|---|---|---|
| Primary | `codex/code-improvement-2026-10-21` | `origin/codex/code-improvement-2026-10-21` | Documentation only; prior HEAD `da11831cdf976560f642370790847bba647f7ff9` |
| macOS | `codex/highlight-subtitle-macos-2026-10-25` | `origin/codex/local-companion-macos` | `5ffd9a826261e9fb0b405486cde6aae843fcdc79` |
| Web | `codex/highlight-subtitle-web-2026-10-25` | `origin/codex/local-companion-web` | `59688e2b45014c02f79b04c1f36213899824dfc0` |

Publication uses explicit refs and an atomic fast-forward push to these three existing remote branches. No merge, force push or update to master/collaborator branches is included. Exact final documentation heads and remote comparison are recorded in `/Users/drm/project/nyaru-clipper/.omo/evidence/git-publication-20261027/receipt.json`; milestone IDs above deliberately exclude the later documentation commits.

Fresh publication checks: each frontend passed **365 tests in 45 files**, TypeScript and production build; macOS backend/native checks passed **171**, with one actual-desktop case deselected, and Web backend checks passed **139**. Initial concurrent backend runs conflicted on the shared execution lock; sequential full reruns passed. The Web review test now clears persisted localStorage between cases and includes the same reload/null-revision regressions. Real recognition, provider calls, export and native UI were not repeated for publication; their acceptance remains the dated evidence above.

Untracked media/template outputs, `.DS_Store`, temporary pnpm workspace configuration, test caches, runtime state and private evidence stay outside Git and are preserved. Continue from the appropriate platform checkout; do not reset, clean or overwrite the original worktrees.

## Protection, rollback and remaining work

- The installation receipt verified preservation of 21 original active files, two prior task contexts, source media and original settings. Continue protecting original media, sealed roots, reader/epoch pins, tasks and failed records. This Git publication does not replace the installed App or mutate production data.
- Backup: `/Users/drm/Library/Application Support/Nyaru Clipper Backups/workbench-fixes-20261026-1723/`. It retains the original 0.1.20 App, real-tested build30 and pre-update unified snapshot. Quit normally and preserve the current runtime before switching Apps; never overwrite newer data with the older snapshot.
- Review drafts survive same-origin reload, **not a native App restart**. Exported videos and frozen ranges remain durable. Historical auto-language jobs without actual language metadata must be re-recognized, not guessed or rewritten.
- One interim analysis failure on `f98b6a7d...` remains as evidence; do not confuse it with the successful final run or delete it to hide the failure. All four final-task operations succeeded.
- Remaining work is bounded to known gaps: restart-persistent drafts if needed, human caption/candidate review, and separate long-VOD/live, Windows/GPU, dark-system, recovery and notarization validation. The short-video result grants no acceptance for those scenarios.

## Historical handoff text

The body below is unchanged; its uses of “current” refer only to the associated historical date.

# 2026-10-26: Watch Workbench installed

Formal App is now **0.1.20 build 28**. Original active data/configuration were backed up and verified unchanged; normal reopen selects the registered formal runtime. [Installation, preservation and rollback](watch-workbench-install-2026-10-26.md). Older candidate-only statements below are historical.

---

# Nyaru-Clipper project handoff

## Current handoff: 25 October 2026 (Asia/Shanghai)

The unified architecture has been merged and pushed to the Web and macOS development branches. Remote and local commit identities have subsequently been rewritten. This section supersedes older publication state and commit IDs below; those dated records remain historical evidence. This refresh only changes the two handoff files. It does not commit, push, merge, install, launch an App, resume monitoring or switch data domains.

### Current remote branches and original worktrees

Read-only `git ls-remote --heads --tags origin` on 25 October returned:

| Remote branch | Current HEAD |
| --- | --- |
| `codex/code-improvement-2026-10-21` | `da11831cdf976560f642370790847bba647f7ff9` |
| `codex/unified-architecture-2026-10-22` | `0468740a717a7fdcf66e74b7295e4e0501625515` |
| `codex/local-companion-web` | `3e0582b47577b1fa7f26466fef7b78f7088c1fd7` |
| `codex/local-companion-macos` | `73aa14b6def9e7e9b970a42621844e7c62f702f2` |
| `feat/arctime-pro-plugin` | `ef9ea33d3d08f2ee1472b660179a52d8f40d7813` |
| `feat/companion-topic-subtitle-updates` | `69d3fa0dea30a73ef0f0ef27591bc1abda9080f1` |
| `master` | `0bcd8d503ac33f89c8e1cd526de5d7a44f6668b6` |

Master and the four tag object IDs still match the previous baseline. The topic/subtitle branch has advanced since the 24 October cleanup receipt (`39911f1a24775d2e8fd4cb3a98a8165fa70880e4`); its new commits were not audited or changed in this refresh. Do not extend the earlier clean-history result to every current remote commit.

All five original worktrees retain their original code versions after identity rewriting:

| Worktree | Local HEAD | Dirty paths before this refresh |
| --- | --- | --- |
| `/Users/drm/project/nyaru-clipper` | `da11831cdf976560f642370790847bba647f7ff9` | 13 |
| `/Users/drm/.codex/worktrees/local-companion-web/nyaru-clipper` | `8f495b8073f64a257da2bc5e68fa74b1e0db1a94` | 53 |
| `/Users/drm/.codex/worktrees/local-companion-macos/nyaru-clipper` | `f47e868aeab61b272597810cff21ef2e83220578` | 56 |
| `/Users/drm/.codex/worktrees/streamer-highlight-framework/nyaru-clipper` | `ee441022f8f41613c5e48e6fdd5ead2b69361b0c` | 12 |
| `/Users/drm/.codex/worktrees/unified-architecture/nyaru-clipper` | `0468740a717a7fdcf66e74b7295e4e0501625515` | 0 |

The original Web/macOS local branches are respectively **19/17 commits behind** their matching remote-tracking branches. The published integration is therefore not the current code baseline of those dirty worktrees. Local helper branches `codex/merge-unified-web-2026-10-23` and `codex/merge-unified-macos-2026-10-23` point to the published merge heads. The streamer branch is not currently advertised on the remote. This refresh leaves the primary checkout with these two modified handoffs in addition to its 13 existing untracked paths; nothing is staged.

### Merge result and historical validation

The rewritten unified implementation commit is `fc1e0405faafe9858569cfbb81acb3b179a69ca5`. The 23 October Web merge retains the Windows PowerShell launcher, CUDA whisper.cpp path, Windows locking/JSON retry/executable discovery and credential-availability boundaries. The macOS merge retains the native window/save/quit bridge, frozen backend, tools/models, build requirements, licenses and platform docs.

The [merge receipt](/Users/drm/project/nyaru-clipper/.omo/evidence/unified-merge-20261023/receipt.json) records Web backend **1558 passed / 3 skipped**, macOS focused backend **10 passed**, both frontends **332 passed / 40 files**, both TypeScript/Vite builds, Swift typecheck and all three requirements profiles passing. These are 23 October observations: three Windows-native cases were skipped on macOS, and no new Windows hardware qualification, formal App installation or data cutover followed. Identity rewriting preserved commit trees; this documentation refresh does not rerun those tests.

### Commit identity and future submissions

- Remote cleanup on 24 October used `git-filter-repo 2.47.0 --sensitive-data-removal`: 57 author and 57 committer fields replaced, 62 commit IDs changed across 214 commits, six branches pushed atomically with exact leases. The fresh mirror then had no matching old identity in reachable objects; trees, topology, dates, messages and other contributors were preserved. [Remote cleanup receipt](/Users/drm/project/nyaru-clipper/.omo/evidence/identity-cleanup-20261024/receipt.json).
- Local cleanup verified 211 commits, changed 59 commit IDs and updated 15 refs. All five worktrees' files/modes, indexes and staged/unstaged changes were preserved; reachable commit metadata had zero old-identity matches and strict `git fsck` passed. [Local cleanup receipt](/Users/drm/project/nyaru-clipper/.omo/evidence/local-identity-cleanup-20261024/receipt.json).
- Repository and global defaults are `user.name=damin93381`, `user.email=damin7512476@gmail.com`, `user.useConfigOnly=true`. Both scopes and effective author/committer identities in all five worktrees were rechecked on 25 October. This is the chosen public identity; the email is public commit metadata.
- The 24 October machine audit checked 7,144 candidate locations / 7,141 valid Git locations, found zero matching old-name/email configuration entries and changed no repository configurations. Other identities remain in 298 locations, including `blogging`, `bot`, `qwen` and test repositories. Global settings can still be overridden by repository/worktree config, conditional includes, environment variables, explicit authors and author-preserving operations. Three invalid temporary Git markers and excluded backups remain outside that audit's verified coverage. [Private configuration audit](/Users/drm/.cache/git-identity-audit-20261024-UVTrVn/audit.json).

Private rollback copies and local reflogs/unreachable objects still contain the old history intentionally. Do not upload them, blindly restore old refs, merge an old clone's history, or mirror-push it back into the cleaned remote. This was an identity rewrite, not a purge of every local recovery copy.

### GitHub cache and Support boundary

On 25 October the previously identified old commit was still accessible through the GitHub API. Current branch/tag cleanup does not establish server-side cache erasure. The private [Support draft](/Users/drm/project/nyaru-clipper/.omo/evidence/identity-cleanup-20261024/github-support-request.md) and virtual-assistant guidance were prepared; no ticket number, submitted-ticket receipt or successful cache-removal response is available in this handoff. Whether the user completed submission is **unknown**. No Support message was sent by this refresh.

If the user chooses to continue, the remaining request is removal of cached/unreachable commits, with the repository and current branches/tags retained. GitHub determines policy eligibility; personal-name exposure is not a password/token leak. Use the [official removal guide](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository). Keep identifying old commit links and original identities in private Support evidence rather than adding them to public documentation.

### Continuation and protected state

1. Before any source integration, recheck remote HEADs and all relevant worktrees. Preserve dirty files and indexes; start from the desired current cleaned remote in isolation. Do not run a blind pull/reset/clean, bulk-stage changes or advance the dirty Web/macOS branches just to make local HEADs match the table.
2. The next product-validation gates remain fresh-domain App02 R0/R1 takeover/rollback/reopen, then authorized M24 OS-restart/boot protection. CUDA, WSL ROCm, Windows AMF, external-provider and real-live-capture gaps remain; P6/formal installation/cutover have not been performed by this work.
3. Preserve installed App/data, original media, sealed test roots, unknown task directories, reader/epoch pins and private evidence. Their runtime/content state was not re-audited on 25 October. Earlier package hashes and acceptance results below retain their own dates.

Read-only checks from `/Users/drm/project/nyaru-clipper`:

```bash
git worktree list --porcelain
git status --short
git ls-remote --heads --tags origin
git config --global --get-regexp '^user\.'
git config --local --get-regexp '^user\.'
git var GIT_AUTHOR_IDENT
git var GIT_COMMITTER_IDENT
```

`git ls-remote` does not update local `origin/*` refs. Check effective identities separately in the worktree used for a new commit. [This refresh's protection receipt](/Users/drm/project/nyaru-clipper/.omo/evidence/handoff-refresh-20261025-git-identity.json). No commit/push is implied by this handoff update.

## Historical version-control update: 23 October 2026 (Asia/Shanghai)

Unified implementation, recovery tools, direct tests and App02 fixes are committed as `f8484d5560e971fb4a736e6296d876333cb5b7c6` (`feat: unify task execution, migration and recovery`) on `codex/unified-architecture-2026-10-22`. Primary-checkout documentation belongs to `codex/code-improvement-2026-10-21`; these are the two explicit push targets for this publication. Master and other development branches remain unchanged. Statements below about uncommitted or unpushed work retain their original observation dates; use the [Git publication receipt](/Users/drm/project/nyaru-clipper/.omo/evidence/git-publication-20261023.json) and remote branch IDs for the publication result.

Fresh checks in the unified candidate before committing: backend **1551 passed**, frontend **332 passed across 40 files**, TypeScript/Vite build and all three requirements export checks passed. Program sources match the App02 build-input manifest; only indexes/handoffs changed after packaging. Four existing end-of-file blank-line notices remain. This publication only changes version-control state: no repackaging, installation, formal-data cutover or additional platform qualification. Retain sealed domains, old epoch/reader pins, original media and private evidence.

## Historical candidate entry point: 23 October 2026 (Asia/Shanghai)

### Handoff refresh: 23 October 2026,13:36 Asia/Shanghai

This refresh only updates handoffs and performs read-only checks. Both App02 ZIPs, the native/frozen executables and fixed recovery bundle retain their recorded SHA256 hashes; all six real-test roots remain immutable and no matching candidate App/backend process was found. [Refresh receipt](/Users/drm/project/nyaru-clipper/.omo/evidence/handoff-refresh-20261023-app02.json). Functional results below come from the previous actual runs. No App launch, rebuild, functional rerun, remote connection or fresh full formal-data audit occurred.

| Handoff item | Current location and boundary |
| --- | --- |
| Latest candidate App02 | [App ZIP](/Users/drm/.cache/nyaru-clipper/unified-native-build-20261023-02/Nyaru-Clipper-unified-candidate-20261023-02.zip); extracted App at `/Users/drm/.cache/nyaru-clipper/unified-native-build-20261023-02/Nyaru Clipper.app`. Display0.1.19/build27: use recorded hashes, do not double-click. |
| Pinned independent recovery | [Recovery ZIP](/Users/drm/.cache/nyaru-clipper/unified-recovery-20261023-02.zip); fixed reader directory `/Users/drm/.cache/nyaru-clipper/unified-recovery-20261023-02`. Do not move it or rebind an existing epoch. |
| Latest real task/recovery evidence | Task `ad3ad70afddf5287b5d1b4f797665a2a`:21 cues,two manual translations,revision2. [R2 manifest](/Users/drm/.cache/nyaru-clipper/historical-fixed-native-20261023-01/R2/complete.json) / [independent recovery verification](/Users/drm/.cache/nyaru-clipper/historical-fixed-native-20261023-01/recovered-readonly/verification.json):3 documents,no errors. The saved receipts were checked; recovery was not rerun. |
| Test entry points to retain | Six roots under `historical-fixed-native-20261023-01/runtime` are sealed; do not reuse the old launch argv. Retain API domain `historical-fixed-api-20261023-01`, all old R2 snapshots and reader pins. The old App01 empty root is not an App02 default. |
| Formal environment | Candidate has not replaced the formal App or switched formal data. Previous formal App content/metadata, formal-data metadata and selected original task/media protection checks are in the [final audit](/Users/drm/project/nyaru-clipper/.omo/evidence/historical-fixes-20261023/final-audit.json). This refresh did not repeat formal-data body verification. |

**Next sequence**: first use fresh independent data domains and the pinned App02 reader to repeat R0/R1 takeover, rollback and reopen, checking document versions/full contents and explicit-retry boundaries. Then qualify M24 OS restart/boot protection on an authorized isolated platform. Missing CUDA/WSL ROCm/Windows AMF hardware, external translation and real live capture remain pending; old-package or local results cannot substitute. Historical Workstation preparation failure on old Linux absolute paths was not repaired this round; protect the five unknown directories. P6,formal installation and data cutover have not started; a handoff update does not authorize them.

### Historical-task repair candidate App02 (latest)

F01/F02 are repaired and revalidated against the **new frozen package**:25/25 historical-copy scenario groups passed. A real150-second replay yielded21 cues with manual translations correctly partial2/21. Native playback, revision2 save, CmdQ/reopen, real15-second burn and system saving passed. Adjacent backend regressions82 passed (including8 focused cases); frontend332 passed. Both new archives verified. Display remains0.1.19/build27: use hashes for identity.

[App02 packages and bilingual report](candidate-fixes-2026-10-23.md) · [authoritative receipt](/Users/drm/project/nyaru-clipper/.omo/evidence/historical-fixes-20261023/receipt.md). App ZIP SHA256 `914e36a0b7cf97ad864cedf9d87abfcfcb1b0ae76248b5ec5da2eb7272eff14b`; recovery ZIP `31e364935d925993b6a849d8c1f7df21b325731c29a39e3e298774153a339c42`; new epoch bundle `52342c6a998c6241a5381db6a778bb792ae38a0e197989d166da79da73016b54`. Old pins are unchanged.

Formal App content/metadata, formal data metadata and selected original tasks/media match baselines; no replacement, cutover or commit. All created App/helpers/servers stopped; queues paused. Real-test domain `historical-fixed-native-20261023-01` has six immutable roots and a sealed new R2; independent recovery exported all3 documents, preserving real revision2. Do not double-click, directly reopen/unseal R2, or replace old epoch pins. New-package R0/R1, M24 OS-restart/boot protection and missing-hardware/provider gates remain pending; P6/formal cutover have not started.

### Historical task functional acceptance (App01 failure snapshot; closed by the new package above)

Isolated historical-task copies were tested at the user's request: **19 passing / 2 failing groups** in the21-group frozen API matrix. A retained150-second real recording was processed as a new replay:21 cues,15-second clip/burn passed; browser editing reached revision5 and persisted on reload. Two unfixed defects are **partial translation reported complete** and **lost migrated highlight mode/score/reasons**, so overall acceptance failed. Historical workstation preparation rejected old Linux absolute artifact paths with zero activation; five unknown directories remain preserved.

macOS lock screen blocked native UI, CmdQ, system save panel and continuous playback; browser results do not qualify WKWebView. Remote ROCm checks only read the historical1-cue task,4 publication groups,30-second product, models and device visibility; inference was not rerun. Formal data metadata, five original historical tasks and14 archived sources remain unchanged, and all created candidate/helper processes are stopped. No product edit, rebuild, install or formal cutover occurred. See the [bilingual acceptance report](/Users/drm/.codex/worktrees/unified-architecture/nyaru-clipper/docs/historical-task-acceptance-2026-10-23.md) and [authoritative evidence](/Users/drm/project/nyaru-clipper/.omo/evidence/historical-task-acceptance-20261023/receipt.md) for defects and next gates.

### Post-packaging handoff checks (earlier snapshot)

The earlier handoff refresh only edited docs and performed read-only checks: archives existed, both bundle hashes matched, both R2 databases remained immutable, and no matching candidate process was found. That refresh did not rerun application tests, start the App, rebuild or connect remotely. Packaging results below come from the retained [packaging receipt](/Users/drm/project/nyaru-clipper/.omo/evidence/candidate-package-20261023-receipt.md); subsequent functional checks are recorded in the latest section above.

| Handoff item | Latest record |
| --- | --- |
| [Candidate App ZIP](/Users/drm/.cache/nyaru-clipper/unified-native-build-20261023-01/Nyaru-Clipper-unified-candidate-20261023-01.zip) | SHA256 `7a5c3cad144c57dc74bda2391e157452b69418d1476fdd40e2895f3b310ad6a9`; 5406 extracted files/modes identical, strict signing passed |
| [Independent recovery ZIP](/Users/drm/.cache/nyaru-clipper/unified-recovery-20261023-01.zip) | SHA256 `47f34e5b0d577b20be6d4990bdfd6e093c946159581b4cd1a6035b548b969082`; do not move pinned directory `/Users/drm/.cache/nyaru-clipper/unified-recovery-20261023-01` |
| Bundle rechecked now | Both App/standalone manifests hash to `1ce64b4effcc38a592d90b12e879dcc02a990a62316af8fbdc8e23e16b31ff12`; the complete 3619-resource check belongs to packaging acceptance |
| Qualified local workflow | Frozen takeover, R0/R1 thaw, R1 kill/resume, old-helper reopen, native r3 save/quit/reopen identical to independent export; R2 thaw correctly refused |
| Review and formal environment | [Independent review](/Users/drm/project/nyaru-clipper/.omo/evidence/candidate-package-20261023-review.md) CLEAR/APPROVE/no blockers; packaging before/after records match 1496 installed-App file hashes and 6815 data metadata entries, without claiming full data-body hashing |
| Remaining gates | M03 local_passed within local scope, M24 partial; matrix 22 local_passed/3 partial/3 blocked, P6 planned; not full-platform accepted |
| Historical regression limits | 23 October full backend 1538 passed, final focused run 46 passed; the final five terminal negatives are covered by the focused run, counts are not added; neither packaging nor this refresh reran the full suite |

These are historical App01 entry points: the [earlier startup/acceptance document](/Users/drm/.codex/worktrees/unified-architecture/nyaru-clipper/docs/candidate-package-2026-10-23.md) and empty root `/Users/drm/.cache/nyaru-clipper/packaged-native-empty-20261023-01/runtime.json` are retained records, not App02 startup instructions. Any new trial requires a fresh independent domain within the App02 boundaries above, explicit absolute `--unified-runtime` and matching `--migration-guard`. Do not double-click, reuse old ports/PIDs, or rebind reader pins.

The new sealed domains `/Users/drm/.cache/nyaru-clipper/candidate-package-20261023-recovery-03/R2` and `/Users/drm/.cache/nyaru-clipper/candidate-package-20261023-native-guarded-01/R2` are recovery evidence: do not start against or unseal them. Retain the old build-04 sample seal too. Next work remains M24 OS reboot/boot-time protection on an authorized isolated platform, plus missing-environment CUDA/WSL ROCm, Windows AMF and real live qualification; this does not authorize formal cutover or P6.


**Earlier App01 package:** the [23 October App and independent recovery packages](/Users/drm/.codex/worktrees/unified-architecture/nyaru-clipper/docs/candidate-package-2026-10-23.md) passed isolated startup, frozen takeover, R0/R1 rollback, kill/resume, native r3 save/reopen and identical read-only recovery. Those results belong to App01; the repaired App02 and its limits are recorded above. The installed App/formal data remain unchanged.

**The Option B implementation and qualification progress are in the isolated candidate worktree.** Start with the [latest Chinese handoff](/Users/drm/.codex/worktrees/unified-architecture/nyaru-clipper/docs/project-handoff.zh-CN.md) or [English handoff](/Users/drm/.codex/worktrees/unified-architecture/nyaru-clipper/docs/project-handoff.md), then use its execution record and runtime/rollback guide. Candidate branch `codex/unified-architecture-2026-10-22` is based on `428ba833193db888c6b049ac2983abe1b2ecae17`; implementation remains uncommitted and cannot be reconstructed from HEAD alone.

Earlier evidence covers 1512 local backend tests, 332 frontend tests, 2 real-browser scenarios and scoped macOS/native Linux ROCm workflows. On 23 October, local M03 takeover/kill/HTTP reopen passed and independent interrupted thaw was fixed; a new full backend run passed 1538 tests, with added terminal negatives covered by a final focused rerun. The matrix now has 22 `local_passed`, 3 `partial`, 3 `blocked`; M24 controlled OS reboot/boot-time protection/other profiles, CUDA, WSL ROCm, real live capture, Windows AMF and P6 remain open. See [execution record §9](/Users/drm/.codex/worktrees/unified-architecture/nyaru-clipper/docs/unified-architecture-execution-2026-10-22.md#9-2026-10-23-additional-m03m24-takeover-and-crash-recovery-qualification). The unified candidate has not replaced the installed App, migrated formal tasks or been committed/pushed/merged.

This checkout remains on `codex/code-improvement-2026-10-21`, at the same HEAD, preserving existing dirty changes. **Do not copy candidate code over it or clean the worktree.** Code and drills ran in the isolated candidate/new copies; only handoff updates and `.omo` evidence were added here. No host reboot, remote connection or formal-data cutover occurred. The 21 October section records the earlier formal installation, not production delivery of the unified candidate; runtime states and data counts retain their observation dates. The build-04 sample reader/build-05 App were not replaced and lack this recovery fix; do not silently rebind an existing epoch's bundle.

---

## Historical handoff: 21 October 2026 (Asia/Shanghai)

**All44findings are cumulatively accepted within recorded scope across eight phases, committed on the improvement branch, installed into the official App and reopened. No merge or push.** This section supersedes older “current” statements below; historical records retain their dates. This handoff refresh only edits docs and performs read-only checks: no reinstall, settings change, external AI call or full-suite rerun.

### Current source and commits

Primary checkout `/Users/drm/project/nyaru-clipper`, branch `codex/code-improvement-2026-10-21`, HEAD `428ba833193db888c6b049ac2983abe1b2ecae17`.

| Commit | Scope |
| --- | --- |
| `2d6091ee5af1a82310c0d372c6ea02ac7d1b2d15` | `fix: complete workstation and companion improvement plan`: implementation, required Companion baseline, direct tests/platform configuration;210explicit paths, with one test migration detected as a rename by Git. |
| `428ba833193db888c6b049ac2983abe1b2ecae17` | `docs: consolidate eight-phase improvement acceptance`: paired phase records, rollup, acceptance summary and docs;29paths. |

Start with the [eight-phase rollup/scope](/Users/drm/project/nyaru-clipper/docs/code-improvement-rollup-2026-10-21.md), [original44-item plan](/Users/drm/project/nyaru-clipper/docs/code-improvement-plan-2026-10-20.md), [final cumulative result](/Users/drm/project/nyaru-clipper/docs/phase8-improvement-results-2026-10-21.md) and [portable acceptance summary](/Users/drm/project/nyaru-clipper/docs/validation/code-improvement-acceptance-2026-10-21.json).355-file candidate digest `7702e7f6e0c23172326dc62ddd604729b09062c27a299d94404808c77410fae4`; post-commit files match it exactly, with88original bilingual finding blocks,115frozen gate artifacts and99original Companion hashes preserved. Original feature checkouts/dirty work remain. The current installation now comes from the primary improvement checkout; the historical branch table below no longer identifies its source.

Commits exclude runtime data, raw .omo evidence, App bundles, media, test reports/screenshots, credentials and unrelated docs.59local dirty paths remain: older handoff/feature docs, pre-existing index hunks, outputs,.DS_Store and placeholder-valued web/pnpm-workspace.yaml. Index empty. **This paired handoff refresh is also left uncommitted; no additional commit.** Do not reset, clean or stage everything.

### Official App and preservation

| Area | Installation outcome/current read-only check |
| --- | --- |
| Location | [Official App](</Users/drm/Applications/Nyaru Clipper.app>);1496files match the accepted candidate, deep/strict local signing passes. |
| Displayed version | Still **0.1.19 build27**; the version string cannot identify this update. Current native SHA256 `b7e5e0306fe9e44d413d6d9c916d46e5d2b60437187d3763cb46246e7f2d819f`. |
| Installation source | Primary checkout's [phase8candidate App](</Users/drm/project/nyaru-clipper/.omo/evidence/phase8-final-six-performance-and-retirement-2026-10-21/platform-qa/macos-clean-build/Nyaru Clipper.app>), superseding historical package-build27-final. |
| Real data | `/Users/drm/Library/Application Support/Nyaru Clipper/` remains in place.5793files fully backed up; after reopen5792non-log originals are byte-identical, app.log retains its prefix, with only one new startup ready file. Configuration, authorization, models and existing task-related files retained; isolated preview fixtures not imported. |
| Runtime | Read-only check at **22:21 Asia/Shanghai,21October2026**: official native/helper running, config/jobs HTTP200, runtime ready. Task list **0**, same as before installation; this is not installation data loss. |
| Configuration/auth | Local API reports translation/LLM configured and ChatGPT connected. Authorization files retained byte-for-byte; no secret plaintext read/output, re-login, token refresh or external AI request. Local status does not certify remote-provider usability. |
| Monitoring | No recording/recurring monitor started, resumed or modified. Prior nyaru PAUSED is historical; scheduler state was not freshly confirmed. Missing matching local config is not evidence that monitoring is absent or resumed. |

The old real-data build and isolated preview exited normally before backup/replacement/reopen. Only the official App is left for the user. Ports/PIDs are volatile: discover the current helper's `--ready` file after each launch rather than reusing an old QA endpoint.

### Backup and installation evidence

Private backup: [20261021-221748-eight-phase-install](</Users/drm/Library/Application Support/Nyaru Clipper Backups/20261021-221748-eight-phase-install>).

- `Nyaru Clipper-before.app`: exact pre-update official App, verified against its file manifest.
- `data/`: consistent full Application Support snapshot after shutdown, including configuration/authorization. Keep private, outside Git/sharing.
- For an authorized rollback, quit every Nyaru native/helper process first and restore only the approved App scope. **Do not overwrite newer configuration/tasks with the whole old data directory or restore historically permanently deleted data.**

[Installation receipt](/Users/drm/project/nyaru-clipper/.omo/evidence/formal-app-install-2026-10-21/installation.json), [post-install verification](/Users/drm/project/nyaru-clipper/.omo/evidence/formal-app-install-2026-10-21/post-install.json), [current runtime snapshot](/Users/drm/project/nyaru-clipper/.omo/evidence/formal-app-install-2026-10-21/handoff-runtime-check.json), [reopened official window](/Users/drm/project/nyaru-clipper/.omo/evidence/formal-app-install-2026-10-21/installed-reopened.png), [commit preservation receipt](/Users/drm/project/nyaru-clipper/.omo/evidence/commit-eight-phases-2026-10-21/commit-final.json) remain local-only. Older build26/build27backups and original-media archive records below are historical; their entire contents were not reverified in this refresh.

### Acceptance boundaries and next actions

Eight-phase ledger **44accepted/0pending**, final independent gate **APPROVE,specCompliance PASS,blockers=[],codeQualityStatus WATCH**. Final results for the same frozen candidate:1357backend,327frontend,TypeScript/Vite,17workstation browser and22/22platform commands pass, with actual HTTP/FFmpeg,CPU Docker,current Mac build and native two-document save/quit/same-build reopen. All5000cues retained, remaining4999exactly equal. Historical and overlapping suite counts are not additive. Commit/installation checks verify candidate identity/data and actual runtime entry; they do not claim another complete regression run.

Real GPU/CUDA/ROCm/AMF,model inference,external providers/login,full Compose,power loss,every font,long-duration capture and global responsive/dark/HIG remain uncertified. Existing maintenance/tool warnings and EOF blank lines at `db_migrations.py:107`/`test_subtitle_identity.py:216` remain WATCH. Overall user aesthetic feedback is still pending.

Collect feedback on the official App before bounded changes. No merge/push, automatic recording/room reconnection/monitor resumption/data cleanup; define separate scope for publication or actual external-AI acceptance. Future builds use the primary committed implementation, host uv+pnpm primary/Docker fallback. Inspect Git status first, handle explicit paths only, and preserve unrelated dirty work/private backups.

---

## Historical handoff: 20 October 2026 (Asia/Shanghai)

This turn updates documentation and performs read-only checks only. It did not launch the App/backend, record, enable monitoring, rerun tests/models/external AI, commit or push. Dated records below describe their own observation times.

### Current state

| Area | Verified this turn |
| --- | --- |
| Installed App | `/Users/drm/Applications/Nyaru Clipper.app` is **0.1.19 build27**; deep/strict local signature verification passed. |
| Runtime | No running backend belonging to that installation was found, so no current task API was queried. Task directories under `runs/`: **0**. The 17 October launch observation is not a current running-state claim. |
| Monitoring | `nyaru` remains **PAUSED**. |
| Source | Studio and prior capture/ASR repairs remain uncommitted in the feature worktrees. All 42 compared shared frontend/backend/test files match byte-for-byte. Remote HEADs were not queried. |
| Data/rollback | The build26 App backup, corresponding data backup and original-media archive index still exist. Full data/media hashes were not recalculated this turn. |
| Acceptance | Implementation and installation are complete; user aesthetic acceptance, actual broadcast-end/long-term reliability and new AI semantic-quality acceptance remain pending. |

### Delivered features and existing evidence

- Daily mode provides video, timeline, transcript, compact cue editing and exports. Completed status is compact; task input and playback position survive mode/Settings navigation.
- Template Design has an isolated draft, real libass sample preview, streamer/work-series metadata and workflow defaults. Updating a custom template retains its ID and advances its revision; stale drafts report conflicts.
- Settings centralizes six categories and supports the native Settings menu/Command-comma. Defaults apply software → template → task overrides.
- Task template snapshots, cue documents and task ArcTime bindings are preserved. Settings/Design drafts are independent, and credentials remain outside response/log/document output.

**These results were observed on 17 October 2026 and were not rerun today:** 86 frontend tests plus typecheck/build, 145 macOS backend tests, 141 Web backend tests; six real UI/API scenarios and 156 final screenshots; three native surfaces, packaged libass preview and restart persistence. At installation 1519 App files matched the candidate and 5793 prior data files passed preservation checks. These are neither a fresh full-data audit nor live/model-quality acceptance.

See [Studio usage](companion-studio.md), [build27 delivery/rollback](companion-studio-acceptance-2026-10-17.md), and the authoritative [local evidence directory](/Users/drm/.codex/worktrees/local-companion-macos/nyaru-clipper/.omo/evidence/studio-app-2026-10-17/): final-receipt.md, test logs, browser-qa.json, both UI reviews, frozen-check.json, installation.json, post-install.json and native screenshots. Installation used `package-build27-final/Nyaru Clipper.app`.

### Checkouts and reproduction

| Role | Branch / local HEAD verified this turn |
| --- | --- |
| macOS: `/Users/drm/.codex/worktrees/local-companion-macos/nyaru-clipper` | `codex/local-companion-macos` / `18ea3a0a7ee641cbb46d06d4348ebfa96dfc1dd2` |
| Web: `/Users/drm/.codex/worktrees/local-companion-web/nyaru-clipper` | `codex/local-companion-web` / `ccfb65176b3dd0451920694c5be17b19d856c0ff` |
| Primary: `/Users/drm/project/nyaru-clipper`, retain older workstation/other changes | `feat/arctime-pro-plugin` / `e8ea71085cf5c6ff6f671499872f5c166d31f89b` |

Inspect feature-worktree status and explicit diffs first. HEAD alone cannot reconstruct the installed App: modified and untracked source files must be preserved. Primary checkout is not the installed Companion implementation.

To rerun the recorded scoped checks, use the existing macOS environment below; none ran this turn:

```bash
cd /Users/drm/.codex/worktrees/local-companion-macos/nyaru-clipper
PYTHONPATH=backend /Users/drm/.cache/nyaru-clipper/companion-venv/bin/python -m pytest -q backend/tests/test_studio_settings.py backend/tests/test_subtitle_templates.py backend/tests/test_subtitle_api.py backend/tests/test_subtitle_document.py backend/tests/test_companion_gui.py backend/tests/test_saozi_live.py backend/tests/test_macos_companion.py
cd web
./node_modules/.bin/vitest run src/companion
./node_modules/.bin/tsc -b
./node_modules/.bin/vite build
```

### Next actions and protected state

1. Obtain user feedback on Daily, Template Design and Settings appearance, then make bounded changes. Small phone typography and semantic token naming remain nonblocking cleanup.
2. Define a bounded real-live/AI acceptance scenario only after separate authorization. Do not start recording, reconnect a room or resume recurring monitoring now.
3. Publish only if separately authorized: stage explicit shared/native feature paths and paired docs, then verify remote heads. Do not automatically commit, merge or change master.

Private rollback: `/Users/drm/Library/Application Support/Nyaru Clipper Backups/20261017-033319-before-build27/`, containing `Nyaru Clipper-build26.app` and `data/`. Quit the App before an approved App rollback. Do not overwrite current config/templates with an entire older data directory or restore permanently deleted tasks. The archive remains `/Users/drm/Movies/Nyaru Clipper/原始录播/20261017-014802/`. Keep credentials, private backups, logs, models and media out of Git; do not read/output secret values in runs/config.json or runs/.chatgpt/.

---


## 17 October 2026 build26 verification and cleanup (historical)

The following was verified on **17 October 2026, 02:08 Asia/Shanghai**. Retain it for cleanup provenance and repair evidence. Its current/this-turn/installed wording applies only to that observation; the 20 October handoff above owns current state. Older task paths and complete-data-backup claims are superseded by this cleanup.

### State and scope at build26

- Installed and running: **0.1.18 build26**, `/Users/drm/Applications/Nyaru Clipper.app`. This check discovered the loopback endpoint from the running backend's `--ready` file; `/companion-api/jobs` returned an empty list. There are no task directories in the App's `runs/` and no capture/Whisper processes.
- Heartbeat `nyaru` remains **PAUSED**. The user explicitly requested no new recording or recurring monitoring. This turn updates documentation and performs one read-only verification.
- Historical tasks, recognition/translation, clips, styled exports and task backups were removed with explicit authorization. Only the archived original media below remain. **Do not automatically resume tasks, reconnect the room or regenerate derived outputs from historical instructions.**
- build26 is installed locally; subsequent repair source changes remain uncommitted/unpushed. Build, installation, actual tail completion and public release are separate states. This turn performs no commit, push, merge or notarization.

### Original-media archive and permanent cleanup

Archive: [original recordings](</Users/drm/Movies/Nyaru Clipper/原始录播/20261017-014802>); [provenance and SHA256 index](</Users/drm/Movies/Nyaru Clipper/原始录播/20261017-014802/原片清单.json>).

There are **14 media files / 3,026,261,061 bytes**: 13 whole source files under `完整原片/` and one original block under `未列入封口清单的原始块/`. Identical sources were deduplicated by SHA256 with provenance retained. The 15 closed blocks from `4be6301526e0` were merged by stream copy without transcoding; every encoded video/audio packet hash sequence was verified against the inputs at cleanup. The extra block from `64a7f4accfed` was absent from its original `closed.csv`; it is retained exactly, without a completeness or clean-decode claim.

The targeted Trash container containing **27 tasks** and **226 task copies** across ten old data-backup batches were permanently removed. Other Trash contents, non-task backup configuration/templates/authorization, and App/installer backups were preserved. Logical deletion was 109,335,161,117 bytes; observed free-space gain was approximately 9.31 GB. APFS shared data explains why these figures differ.

This turn rechecked all 14 archived media sizes/SHA256 values and the index hash: unchanged. The targeted Trash container and all 226 backup task paths are absent. Authoritative receipt: [permanent-cleanup.json](/Users/drm/.codex/worktrees/local-companion-macos/nyaru-clipper/.omo/evidence/task-cleanup-2026-10-17/permanent-cleanup.json). Earlier installation/recovery receipts describe preservation at their own observation time; their `runs/<task-id>` links no longer resolve. Evidence directories are not complete task backups and do not establish recoverability.

### Installed repairs and limits

| Area | Implementation, observations and limits |
| --- | --- |
| Clip 8 subtitles/styles | Select clip membership using raw-precision cues, avoiding the 18/19 count mismatch caused by SRT millisecond rounding. Repair only hash-matching deterministic legacy output, with a backup; user-edit conflicts still fail closed. One clip's styled-export failure no longer prevents later clips; errors remain reported. |
| Corruption and decode detection | Old HEVC source recordings already lacked reference pictures; FFmpeg may emit decode errors while returning zero. New capture strictly selects `best[vcodec=avc][protocol=https][ext=flv]`, without silent HEVC/HLS fallback. A 150.095-second/eight-block AVC/FLV comparison fully decoded successfully. New `video_integrity.py` fully decodes closed blocks, checks both status and error output, and records `video_decode_error`/`capture_warning`. Detection reports damage; it cannot repair old sources. Archived old HEVC corruption may remain. Upstream omission versus HLS demux skipping is not conclusively separated. |
| Normal broadcast end | After reader exit/resolution failure, query room metadata within existing bounded connection attempts. Only explicit integer `live_status=0/2` establishes `live_ended`; unknown/error/still-live responses do not. Explicit user stop wins. Persist `capture_end_reason` and historical warnings; independent ASR/export errors remain failed. Real FFmpeg EOF fixtures and the room's then-offline status passed, but no new real broadcast-ending event was observed after this fix; current offline status cannot establish an older failure's cause. |
| ASR tail timestamps | Keep timestamp guards. Only an otherwise rejected result triggers one VAD retry on the same WAV with the same Whisper small model, language and threads. Require newly generated valid subtitles; a validated no-speech result may be empty. Missing output, process failure, repeated invalid timing or invalid VAD model still fails without caching false success. On macOS, use bundled OpenMP libraries for the child process to prevent mixed-library VAD crashes. |
| Models/package | Whisper small and DeepSeek Flash identities remain unchanged. Auxiliary `ggml-silero-v6.2.0.bin`: 885,098 bytes, SHA256 `2aa269b785eeb53a82983a20501ddf7c1d9c48e33ab63a41391ac6c9f7fb6987`, pinned official model revision and MIT license. Packaging consumes a verified local asset without downloading it; arbitrary input filenames are packaged under the canonical model name. |

### Tail completion (historical tasks subsequently deleted)

| Source → recovery copy | Verified before cleanup |
| --- | --- |
| `34c7512544cd` → `7dcf0cb825d2` | completed: 270 blocks, 5390.152233 seconds, 63 clips, translation 1417/1417; retained 1369 translated rows and added 48. Old style configuration was removed only in the recovery copy to avoid reburning every old clip. Source corruption was not repaired. |
| `4be6301526e0` | Failed on ASR timing and was not fully reprocessed. Its 15 closed recording blocks were merged without transcoding into the archive; recognition/translation must not be reported as completed. |
| `bc4572ea33da` → `934c984a3d33` | completed: 140 blocks, 2788.007993 seconds, 31 clips, translation 772/772. Preserved the first 138 recognition records, 29 clips and 761 translated rows; also completed ten already-recognized rows awaiting translation publication. The penultimate block had no speech under VAD; the final block's music cue was translated normally. |

At the latest recovery, all bilingual counts/registered hashes and all 62 style-output hashes passed. The two new raw clips and two corresponding subtitle videos fully decoded; the music subtitle frame was visually inspected. **Those task directories, subtitles and derived videos were subsequently permanently deleted as requested. Only source media and sanitized verification records remain.** These are pre-cleanup completion results, not tasks still available in the App. Translation was not exhaustively proofread.

### Source, verification and continuation

| Checkout | Branch / local HEAD verified this turn |
| --- | --- |
| `/Users/drm/.codex/worktrees/local-companion-macos/nyaru-clipper` | `codex/local-companion-macos` / `18ea3a0a7ee641cbb46d06d4348ebfa96dfc1dd2` |
| `/Users/drm/.codex/worktrees/local-companion-web/nyaru-clipper` | `codex/local-companion-web` / `ccfb65176b3dd0451920694c5be17b19d856c0ff` |
| `/Users/drm/project/nyaru-clipper` | `feat/arctime-pro-plugin` / `e8ea71085cf5c6ff6f671499872f5c166d31f89b`; handoff synchronization only, preserving other dirty work |

Repairs are in both feature worktrees' `backend/app/arctime/`, related tests and `web/src/companion/companionApi.ts`; macOS additionally changes `scripts/build_macos_app.py` and adds `desktop/macos/silero-vad-LICENSE.txt`. Shared ASR source/tests match. The primary checkout's legacy workstation is not the installed Companion source entry. The HEADs above exclude these uncommitted repairs. Remote HEADs were not queried this turn; old publication receipts do not establish their current state.

The latest ASR suite passed **31 tests in each feature checkout**. The related seven-file suite passed **124 tests** before three additional error-path tests; overlapping totals are not additive. Final frozen code matched verified source, deep/strict signature validation passed, and real packaged CLI checks produced zero cues for music and four for speech. Only `package-build26-final` was installed; earlier candidates are not the delivered package. The existing Starlette/httpx deprecation warning remains; LSP tools were not installed per the user's choice. This documentation turn does not rerun models/full regressions or create tasks.

Local evidence (read historical runtime paths together with the cleanup state above):

- [HEVC diagnosis/AVC comparison](/Users/drm/.codex/worktrees/local-companion-macos/nyaru-clipper/.omo/evidence/hevc-root-cause-2026-10-16/README.md), [subtitle boundary repair](/Users/drm/.codex/worktrees/local-companion-macos/nyaru-clipper/.omo/evidence/subtitle8-decode-fix-2026-10-16/README.md), [older tail recovery](/Users/drm/.codex/worktrees/local-companion-macos/nyaru-clipper/.omo/evidence/old-tail-recovery-2026-10-16/README.md).
- [Live-end implementation/acceptance](/Users/drm/.codex/worktrees/local-companion-macos/nyaru-clipper/.omo/evidence/live-end-recognition-2026-10-17/README.md), [ASR/VAD implementation/acceptance](/Users/drm/.codex/worktrees/local-companion-macos/nyaru-clipper/.omo/evidence/asr-tail-recovery-2026-10-17/README.md), [final package verification](/Users/drm/.codex/worktrees/local-companion-macos/nyaru-clipper/.omo/evidence/asr-tail-recovery-2026-10-17/package-verification.json), [recovery receipt](/Users/drm/.codex/worktrees/local-companion-macos/nyaru-clipper/.omo/evidence/asr-tail-recovery-2026-10-17/recovery-completion.json), [media verification](/Users/drm/.codex/worktrees/local-companion-macos/nyaru-clipper/.omo/evidence/asr-tail-recovery-2026-10-17/media-verification.json).

Read this section and the permanent-cleanup receipt first, then inspect uncommitted feature-worktree diffs. Any separately authorized publication should stage explicit paths and publish only named development branches while preserving other primary-checkout changes. Do not automatically install/roll back earlier candidates or restore deleted tasks from old backup instructions. Discover the current App endpoint through the backend's `--ready` file; do not launch a second service. Provider configuration/authorization remain secret: never read or expose their values. Real live-end and long-duration acceptance require separate authorization. **There is currently no recording or recurring monitor.**

## Delivery records from 16 October and earlier (historical)

The following publication, installation and acceptance text is preserved as history. “Current”, “this delivery” and “preserved” below refer only to their original observation time, not the 17 October state above. Old data backups now retain non-task contents only and are no longer complete task backups.

## ASS templates and build18 development-branch publication (historical)

This delivery covers ASS style import, frozen live templates, incremental styled exports and the Nyaru builtin/default. Only `codex/local-companion-web` and `codex/local-companion-macos` are published; the primary checkout's other dirty work is preserved. Local and remote master baseline: `0bcd8d503ac33f89c8e1cd526de5d7a44f6668b6`.

| Branch | Implementation commit | Packaging commit |
| --- | --- | --- |
| `codex/local-companion-web` | `09acdc420ed7f0b8ecd10a84672d3613770281ed` | Not applicable |
| `codex/local-companion-macos` | `6040ca9415e07357993eba3f5b3ee21c5ec47182` | `fbd7d5b2df40cba1619a99c6cdac1c56727494ee` |

Paired handoff, usage, plans and acceptance records follow in documentation commits, so the table does not list final branch heads. Push uses explicit refspecs and `--atomic`; the final remote comparison is retained locally in the macOS worktree at `.omo/evidence/nyaru-default-build18-2026-10-16/publish-receipt.json`. Recheck with `git ls-remote origin refs/heads/codex/local-companion-web refs/heads/codex/local-companion-macos refs/heads/master`.

Publication verification: 231 relevant macOS backend tests, 77 Web frontend tests and the Web production build passed. Both worktrees' 27 shared implementation/test files are byte-identical; earlier macOS frontend/frozen/native acceptance and data preservation are detailed below. Task data, media, models, credentials, backups and binary packages are excluded from Git. Real Bilibili/external AI were not rerun; no notarization or branch merge is included.

## Previous local version: 0.1.10 build18 (historical)

Nyaru Mint Signal is built in and selected as the installed default; new live tasks select it automatically with an opt-out. The new package was installed and launched, including ASS style import and incremental styled outputs. All 20 historical tasks and provider/authorization state were retained; only the requested default subtitle file changed after startup. Previous build17 and full data backups are under timestamp 20261016-174807. See [build18 acceptance and backup](/Users/drm/.codex/worktrees/local-companion-macos/nyaru-clipper/docs/nyaru-default-build18-acceptance-2026-10-16.md).

Implementation commits and publication verification are listed above; master is unchanged. The build17 publication/installation records below are historical.

## Previous build17 development-branch publication (historical)

This release is limited to the two development branches below, with separate implementation/tests and documentation commits. The primary checkout's `feat/arctime-pro-plugin` is not committed, pushed or merged. Local and remote `master` remain at `0bcd8d503ac33f89c8e1cd526de5d7a44f6668b6`.

| Development branch | Feature commit, before the following handoff commit | Worktree |
| --- | --- | --- |
| `codex/local-companion-web` | `edf3777636e0b9f231eb1734ee78dc2f55ec4eb4` | `/Users/drm/.codex/worktrees/local-companion-web/nyaru-clipper` |
| `codex/local-companion-macos` | `069061bddc0ded8936932dbe6c12d0b786069a22` | `/Users/drm/.codex/worktrees/local-companion-macos/nyaru-clipper` |

Publication uses an atomic push with explicit refspecs. Final HEADs include subsequent documentation commits and differ from the feature SHAs above; the exact remote receipt stays local at `.omo/evidence/task-sources-build17-2026-10-16/publish-receipt.json` in the macOS worktree. Recheck when continuing:

```bash
git ls-remote origin refs/heads/codex/local-companion-web refs/heads/codex/local-companion-macos refs/heads/master
git -C /Users/drm/.codex/worktrees/local-companion-web/nyaru-clipper status --short
git -C /Users/drm/.codex/worktrees/local-companion-macos/nyaru-clipper status --short
```

Both frontends passed 72 tests and production builds. Pre-publication backend verification passed 115 tests, including three macOS packaging checks, with one Starlette/httpx dependency deprecation warning. Frozen-runtime, native input and data-preservation results are recorded in [task sources and build17 acceptance](task-sources-acceptance-2026-10-16.md). Next is feedback using the user's real room/BV identifiers; further platform acceptance, public distribution, notarization and branch merges are outside this release.

## Previous local installation: 0.1.9 build17 (historical)

On 16 October 2026, the user-authorized rebuilt App replaced `~/Applications/Nyaru Clipper.app` and passed startup checks. New Task exposes live capture, download and local video: enter a numeric Bilibili room ID, a BV ID, or choose a file. Downloads and local files share slicing choices. The build16 publication/installation sections below are historical and do not describe the current installed version.

The old App is at `~/Applications/Nyaru Clipper Backups/20261016-132441/Nyaru Clipper-build16.app`; the complete data backup is at `~/Library/Application Support/Nyaru Clipper Backups/20261016-132441/Nyaru Clipper/`. Its parent is mode 0700; it contains authorization configuration and must remain local.

Across replacement, all 6,561 files / 9,935,483,555 bytes, permissions and symlinks matched. After startup and native UI checks, all 20 historical task IDs and provider/authorization status matched; every existing data file was unchanged, with only one new startup-information file. Strict signing, frozen-backend identifier validation, real local import/ASR/three-second clip export and ZIP integrity passed. All three sources were observed in the installed native window without creating or reprocessing historical tasks. Real Bilibili download/capture and external AI were not revalidated. This remains locally signed, unnotarized, arm64 and macOS 27.0 minimum.

The package is in the macOS worktree at `.omo/evidence/task-sources-build17-2026-10-16/Nyaru-Clipper-0.1.9-build17-macOS-arm64.zip`, 520,730,841 bytes, SHA256 `be1154477eada169d384f61b8f4960bb507095dd48821dd574be38207e89ac11`. Local receipts are `installation-receipt.json`, `frozen-smoke-receipt.json`, `package-receipt.json` and `installed-{bv,live,local}.jpg` in the same directory. Do not commit the App, backups, models or private manifests.

## build16 publication and branch boundaries (historical)

This delivery adds per-cue subtitle editing on Web/macOS with shared preview, ASS and burned-video rendering. The user subsequently authorized installing build16 and committing/pushing this work and handoffs to the two development branches below, **leaving master untouched**. Implementation/tests are feature commits; usage, acceptance and this handoff follow in documentation commits.

| Development branch | Feature commit, before the handoff commit | Worktree |
| --- | --- | --- |
| `codex/local-companion-web` | `576b538d336cbeaf9c869f049f3b7d063ad9f792` | `/Users/drm/.codex/worktrees/local-companion-web/nyaru-clipper` |
| `codex/local-companion-macos` | `a132fcc6125380a5451e5cfe2dd335ec55260e81` | `/Users/drm/.codex/worktrees/local-companion-macos/nyaru-clipper` |

Publication uses an atomic push with explicit refspecs for those branches. The primary checkout's `feat/arctime-pro-plugin` and other branches are not pushed or merged. Local/remote master baseline is `0bcd8d503ac33f89c8e1cd526de5d7a44f6668b6`. Unrelated dirty work in the primary checkout is preserved.

Repository: [Nyaruverse/nyaru-clipper](https://github.com/Nyaruverse/nyaru-clipper), origin `https://github.com/Nyaruverse/nyaru-clipper.git`. Final HEADs include the following handoff commits, so the feature SHAs above are not final remote heads. Recheck when continuing:

```bash
git ls-remote origin refs/heads/codex/local-companion-web refs/heads/codex/local-companion-macos refs/heads/master
git -C /Users/drm/.codex/worktrees/local-companion-web/nyaru-clipper status --short
git -C /Users/drm/.codex/worktrees/local-companion-macos/nyaru-clipper status --short
```

The exact private publication receipt is in the macOS worktree's `.omo/evidence/subtitle-editor-2026-10-16/publish-receipt.json`, outside Git. Source publication and local installation do not establish notarization, public distribution or all-platform acceptance.

## Current features and entry points

The six-entry toolbar and independently scrolling right drawer remain. Open a completed task, click a cue, then choose Position. X/Y are output-video image pixels excluding player letterboxing. Drag the red + handle or focus it and press arrows for 1 pixel, Shift for 10. Anchor grid, snapping, safe area, centering, automatic positioning and original/translation linkage are supported. Batch moves use each cue's own previous position.

The Content/Position/Style/Timing tabs support independent original/translation text, partial emphasis, fonts/advanced layout, split/merge, frame adjustment, batch shifts, looping, style clipboard, undo/redo and serialized autosave. A per-language style is a complete override until inheritance is restored. Conflicts retain drafts; changed sources require explicit reset with a backup of the old editing document.

Edits live in task-local `subtitle-document.json`; source subtitles/media, recognition/translation results and prior exports remain immutable. Precise preview is a transparent image rendered by the same libass path as ASS/burning. Clip export intersects absolute source times and rebases them to clip zero; ASS precision is centiseconds. Burning remains completed-clips-only. Original SRT downloads remain original; edited SRT and JSON are included in ArcTime ZIP. See [per-cue editing](subtitle-editor.md).

## build16 installation, rollback and preservation (historical)

The installed app at that time was **0.1.8 build16** at `~/Applications/Nyaru Clipper.app`. That build rebuilt the frontend, froze backend/tools/model, compiled the Swift shell and reapplied local signing. Strict signature verification and Swift typechecking passed. With no active task, build15 was quit normally, replaced, and build16 opened successfully.

- Old app: `~/Applications/Nyaru Clipper Backups/20261016-114616/Nyaru Clipper-build15.app`.
- Full data backup: `~/Library/Application Support/Nyaru Clipper Backups/20261016-114616/Nyaru Clipper/`, under a 0700 directory. It includes authorization configuration: keep it local; never commit or share it.
- All **6,560 files / 9,935,471,576 bytes** had identical hashes across replacement. After restart all **20 historical task IDs** remained; all existing files were checked again and unchanged.
- The unsaved custom style was retained as “升级前自定义样式 2026-10-16”. Native demonstration changed X640 to641 then undid it, restoring X640/Y656, saved revision2 and inherited styles. Only that task's editing document and startup file were added by the demonstration/restart.
- Local ZIP `Nyaru-Clipper-0.1.8-build16-accepted.zip` is in the evidence directory above:514,619,440bytes,3,914entries,SHA256 `2badc99dc66bb1cfa44888d3a976ce87a693710e02c9fc6e534d00d89a15ff17`. App/ZIP/model are excluded from Git.

## Verification and boundaries

| Scope | Result and evidence |
| --- | --- |
| Both frontends | Each10files/65tests passed; TypeScript/Vite production builds passed; overlapping coverage is not additive |
| Backend | 160 regressions covering subtitles/templates/APIs/rendering/GUI/translation/macOS passed; Web separately ran50 overlapping document/font tests |
| Actual Web UI | 1440/1920/390widths, both system appearance preferences, four tabs,48top/end captures; no horizontal overflow; existing light palette retained |
| Final frozen backend/native WKWebView | Bottom/center/top multiline bilingual placement, separate language nudges and linked numeric positioning passed; selected bounds move+1X/0Y, sibling stays fixed |
| Preview/ASS/burn | Actual ASS coordinates versus PNG; burned-frame/composited-preview RMSE1.355/1.507/1.422of255, including lossy encoding |
| Data/failure paths | Sample neighbour/source/old-export hashes retained; changed sources/stale revisions/invalid timing rejected while drafts retained; missing-font warning passed |
| Review | Earlier G1 automatic multiline-anchor jump repaired; fresh position code review APPROVE/no blockers, independently14frontend/41backend tests and actual ASS transitions |

See the [sanitized acceptance summary](subtitle-editor-acceptance-2026-10-16.md). Private raw evidence remains under the above `.omo/evidence/`: `acceptance.md`, `integration-receipt.json`, `native-candidate-*-verification.json`, `native-report.md`, `position-delta-review.md`, `installation-receipt.json`. Earlier rejecting reports and failing tests are retained as history, not current failures.

Not reaccepted here: real downloads, ASR, provider authorization/expiry/revocation, all font/glyph/style combinations, native save/confirmation panels, new machines or Intel/older macOS. The authorized replacement upgrade on this machine completed. Target remains arm64/macOS27.0+, ad-hoc signed and not notarized. Animations, karaoke, motion keyframes, perspective, vector masks and full-video burns remain outside scope.

## Preserved real-task observations

The 15 October handoff recorded these processing/translation states as completed. Media processing was not repeated. build16 installation verified full current data-directory file hashes; historical quality conclusions retain their original limits:

| Scenario | Task | Historical result |
| --- | --- | --- |
| Original full replay Saozi | `1bd089ad75b3` | 3275.299 seconds / 35 clips; Flash 658/658, original retained |
| User-requested OpenAI rerun | `3a01f1263649` | 34 clips; GPT-6-Luna 658/658; new cuts/translation, no Flash cache reuse |
| Local recording | `73fbcd311737` | 150.033333 seconds / 2 clips; ChatGPT 21/21 |
| Bilibili live recording | `68faca68e130` | 181.105 seconds / 2 clips; ChatGPT 40/40; first bilingual clip before stop |
| Web-created local task | `472c1adbd0d1` | 150.033333 seconds / 2 clips; ChatGPT 21/21; short tail retained |

Network interruption/recovery evidence is retained; successful recovery does not establish continuous provider availability. Translation/cut quality was sampled, not exhaustively proofread. Native build14 playback and NSSavePanel saving previously passed; the user did not grant WKWebView Downloads permission and explicitly accepted that boundary. Do not describe it as permission granted or technical acceptance. See [Web acceptance](web-app-acceptance-2026-10-15.md), [subscription acceptance](openai-subscription-acceptance-2026-10-15.md), [Saozi acceptance](saozi-acceptance-2026-10-15.md) and [bilingual completion](saozi-bilingual-acceptance-2026-10-15.md).

## Runtime, source and preservation rules

App data is under `~/Library/Application Support/Nyaru Clipper/`: `runs/`, `models/` and `app.log`. Provider settings are in `runs/config.json`; ChatGPT authorization is in `runs/.chatgpt/` (0700 directory / 0600 files). Never read, copy, commit or expose secret values. Templates live under `runs/templates/`. Preserve task manifests, source media, prior exports, failure and recovery evidence. CLI `data/local-runs/` history is not automatically imported.

The App's loopback port changes on restart; use current startup state, not a hardcoded old port. Never start a second service writing the same task root. No public exposure, multiple workers, paid/cloud ArcTime calls or **DeepSeek Pro**. Providers are DeepSeek Flash and ChatGPT subscription; new defaults affect new tasks only, retries retain the task's recorded provider/model, without automatic fallback.

Shared implementation lives in the feature worktrees under `backend/app/arctime/` and `web/src/companion/`. macOS-specific paths are `desktop/macos/`, `backend/app/arctime/macos.py` and `scripts/build_macos_app.py`. Never overwrite the App's frozen-tool logic with the Web branch's whole `media.py`. The primary checkout's legacy `backend/app/main.py` and worker are not the Companion launch path.

```bash
cd /Users/drm/.codex/worktrees/local-companion-web/nyaru-clipper/web
corepack pnpm exec vitest run src/companion
corepack pnpm build
```

Use the same commands in the macOS worktree's `web/` directory. Launch the installed App normally. Browser/CLI instructions: [local companion](local-companion.md); provider instructions: [ChatGPT subscription](openai-subscription.md); clipping: [Saozi](saozi.md).

## Next work and history

The authorized scope includes development-branch publication, handoff updates and this machine's build16 replacement installation. Full translation/cut proofreading, subtitle/ArcTime feedback, more platform validation, signing/notarization, public distribution and branch merges require a separate scope.

Preserved snapshots: [before subtitle-editor publication](project-handoff-history-2026-10-16-before-subtitle-editor-publish.md), [before toolbar publication](project-handoff-history-2026-10-16-before-toolbar-publish.md), [before the 15 October delivery refresh](project-handoff-history-2026-10-15-before-delivery-refresh.md), [15 October](project-handoff-history-2026-10-15.md) and [14 October](project-handoff-history-2026-10-14.md). Historical uncommitted/unpushed statements, build14 and old branch heads apply only to their observation time.
