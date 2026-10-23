# Historical task functional acceptance

Date: 23 October 2026 (Asia/Shanghai). Tested the frozen backend and bundled workbench of candidate `unified-native-build-20261023-01`. **The API matrix has 19 passing groups and 2 failing groups; overall acceptance failed.** Both product defects remain unfixed. Historical workstation takeover and native interaction under a locked screen have separate limits. This run adds isolated runtime data, QA scripts and documentation; product sources, packages and formal cutover are unchanged.

## Samples and execution boundaries

| Sample | Use in this run | Evidence boundary |
| --- | --- | --- |
| CLI history `4beb340e0219`, `b6ee69e3b13a`, `e42790586570`, `061b0ecce533`, `2b46c356913c` | Copied into a new domain, registered under a new source UUID, prepared, verified and taken over | Five existing jobs share one 20.4-second Tingting/FFmpeg synthetic source; the first three have two manual clips each, the last two one highlight each; these are not five real programs |
| Retained real recording `录播-472c1adbd0d1.mp4` | A copy was processed as new isolated replay task `6a33ec62805c5b4dbbd69d8f2f82259d` | 150.033333 seconds, actual whisper.cpp small/ja inference generated 21 cues and a 0–15-second clip; this is a new replay, not restoration of a deleted task |
| Original workstation `task-ec2a386fa864` | Read-only SQLite backup and task copy, followed by preparation in an isolated domain | The old database still references `/home/drm/workfile/...`; those paths were not rewritten to manufacture successful takeover. Five unregistered directories remain unknown data |
| Earlier `40c0c9a8e93e`, `7fe886d15999` | Cleanup state checked only | Their 658/1448-cue task directories, drafts and derived videos were permanently deleted. They were not restored, and old reports were not presented as new reopen evidence |

The real source is `/Users/drm/Movies/Nyaru Clipper/原始录播/20261017-014802/完整原片/录播-472c1adbd0d1.mp4`, 40,136,792 bytes, SHA256 `aa444790a8f22575bda82335e451ff8a7e4c927671a1e44f25bc41dc139790c7`. Only two translations were entered manually with explicit QA labels; no translation provider was called. The 21 recognized cues were not semantically reviewed line by line.

## Acceptance matrix

| Feature | Result | Observed evidence |
| --- | --- | --- |
| Historical Companion takeover | Pass for five samples | Frozen CLI takeover, initially paused queue; all original cue text/times and source/clip digests match |
| Library | Pass | Pagination, search, title, tags, archive/unarchive, stale metadata version 409 |
| Subtitle persistence and revisions | Pass | Original/translation, style/position/time edits; stale409, invalid-time rejection, immutable version history, original SRT preserved |
| Workbench editing | Pass on browser surface | Page2 of21 cues; switching to2-cue history resets pagination; X640→641→undo640; split21→22, undo/redo; merge21→20 then undo; final21 cues/revision5 with original text and times restored, reload persists |
| Preview | Partial | PNG/libass, video metadata, source/clip selection and seeking passed; play accepted with readyState4 while locked but time did not advance, so continuous playback is unaccepted |
| Templates/public preferences | Pass for storage contracts | CRUD, same-ID revision updates, stale CAS, import/download, default-template and project-reference deletion protection; ATPJ used QA bytes, not a validated real ArcTime project |
| SRT/VTT/ASS/ArcTime ZIP | Pass for artifact contracts | Original/saved, full/clip downloads, timelines, ZIP members and export content verified; ArcTime application was not launched |
| CPU subtitle burn | Pass | Six-second synthetic historical clip and15-second real clip through product export endpoints; real clip submitted by workbench button, downloaded via link, checked against registered digest, tracks, full decode and subtitle frame |
| Queue | Pass | Pause/start, ordering, priority, per-item pause, cancel/explicit retry, stale revision rejection, repeated export reuse |
| Process crash and reopen | Pass on frozen backend surface | Actual SIGKILL during export, interrupted after restart with no automatic retry; explicit attempt2 succeeds; final paused reopen preserves draft and4 exports. Native CmdQ/NSSavePanel blocked by lock screen |
| Missing credentials/bad input/artifact | Pass | Empty-credential translation refusal, invalid path, missing task, malformed template and missing registered artifact have refusal receipts |
| Partial translation progress | **Fail F01** | Only1/2 cues translated, API says completed/2/2; real recording initially had1/21 translated and UI also reported21/21 complete |
| Historical highlight semantics | **Fail F02** | Two highlights project mode→ranges, score0.77→null and four reasons→empty; clip ranges and media digests remain intact |
| Historical workstation takeover | Partial/pending | Preparation rejects old-host absolute artifact paths; zero bindings/operations, original database/directories unchanged; not a successful migration |
| GPU/live/cross-platform | No new functional acceptance | This run only reads GPU historical results, documented in remote receipts; no new inference. Real live, CUDA/WSL ROCm/AMF, OS reboot and boot ordering retain their existing gates |

The21-group API matrix is in [manualQa.json](/Users/drm/project/nyaru-clipper/.omo/evidence/historical-task-acceptance-20261023/api/manualQa.json). Do not add its counts to real-source/browser supplements or earlier unit tests. The first assertion that every crash must automatically pause was a QA expectation error, retained in prior attempts. Preserving admissions after an ordinary export crash is not a third product defect; initial pause during takeover remains a separate gate.

## Two open defects

**F01: a partial translation reports the entire document complete.** `backend/app/arctime/native_projection.py` treats any nonempty cue translation as completed and sets done to the entire cue count; the workbench also appends “complete.” Count nonempty translations separately, retain partial state and avoid describing a manual draft as provider completion. Revalidation must cover zero/partial/all translations, clearing translations, save/reopen and full/clip downloads. See the [independent reproduction](/Users/drm/project/nyaru-clipper/.omo/evidence/historical-task-acceptance-20261023/api/partial-translation-count.json).

**F02: migrated highlight metadata is lost in projection.** Historical tasks without a new processing operation default to ranges, and clip projection omits their saved scores/reasons. Preserve/read mode and selection metadata from registered history; absence of a new operation cannot imply manual ranges. Revalidate manual/highlight modes for both native/migrated tasks, comparing mode, bounds, score, reasons and source digest. See [source/projection comparison](/Users/drm/project/nyaru-clipper/.omo/evidence/historical-task-acceptance-20261023/api/mode-fidelity.json). Original files remain intact, but compatibility display is incomplete.

Fixes require a new candidate identity and affected-path revalidation. This package remains available for reproduction; source fixes cannot be credited to an older package. Workstation paths require an explicit source-root mapping/recovery procedure before preparation is repeated; do not edit formal SQLite or bulk-adopt unknown directories.

## Artifacts, isolation and preservation

Real product: [downloaded MP4](/Users/drm/Downloads/styled-b7144b15f36664c5539b.mp4), 4,707,200 bytes, SHA256 `5da9e0e09ccbc9f04ce9db0af109c5f97c3ffbabf28944e535fbad17c81278f1`; H.264/AAC,1280×720,30fps,450 frames,15-second video and15.018-second container. Export used revision2. Later editing drills were undone and saved as revision5; existing products were not claimed to update automatically. The [2-second subtitle frame](/Users/drm/project/nyaru-clipper/.omo/evidence/historical-task-acceptance-20261023/ui/real-burn-frame-2.png) and [final verification](/Users/drm/project/nyaru-clipper/.omo/evidence/historical-task-acceptance-20261023/final-browser-verification.json) are retained.

| Purpose | Isolated directory and constraints |
| --- | --- |
| Frozen API QA | `/Users/drm/.cache/nyaru-clipper/historical-api-20261023-01`; fresh source/credentials, nowR2 after writes; no direct source-copy thaw |
| Real source/workbench QA | `/Users/drm/.cache/nyaru-clipper/historical-native-20261023-01`; revision5, two registered exports, queue paused; use its pinned runtime-recovery and guard; newR2 domain, not a replacement for old sealed domains |
| Rejected workstation preparation | `/Users/drm/.cache/nyaru-clipper/historical-workstation-20261023-02`; source registered but never activated;01 is the empty directory retained after an initial QA Python-version mismatch |
| Authoritative evidence | `/Users/drm/project/nyaru-clipper/.omo/evidence/historical-task-acceptance-20261023`; api/real/ui/remote preserve their own scope, including earlier expectation errors and failures |

The five original tasks and real source retain identical content digests, inodes/modes/flags and other inventory fields. Formal App-data metadata matches the initial baseline; all14 archived originals match existing digest/size entries. Formal data bodies and credentials were not read in full. OldR2 domains, formal App and formal data were not switched;190 non-document packaging inputs retain their digests. App executable, frozen backend and reader identity checks match.

The created candidate/helper processes are stopped. The native process ended by SIGTERM, which is not user CmdQ acceptance. Do not retry native UI until the lock screen is unlocked; subsequent explicit launches still require the absolute runtime and matching guard, never the default double-click entry. F01/F02 and platform gates prevent formal cutover orP6 retirement.
