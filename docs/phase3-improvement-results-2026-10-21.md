# Phase-three implementation and combined acceptance

Date:2026-10-21. Chinese counterpart:[第三阶段结果](/Users/drm/project/nyaru-clipper/docs/phase3-improvement-results-2026-10-21.zh-CN.md).

Status: **#22 → #23 → #8 → #9 → #10 implemented and individually reviewed; all 18 cumulative criteria accepted within the recorded scope, final gate APPROVE, no blockers; 26 pending.** All 13 previous corrections were included in fresh validation.

Branch remains `codex/code-improvement-2026-10-21`, HEAD `e8ea71085cf5c6ff6f671499872f5c166d31f89b`, all changes uncommitted. The initial204Git entries, complete tracked patch and471file hashes were preserved; original Companion worktrees were not modified. Host uv+pnpm remains primary, Docker fallback. Validation uses disposable databases, synthetic media and owned browser profiles, without App installation or real provider credentials.

## Individual changes

| ID | Behavior and evidence | Review |
| --- | --- | --- |
| #22 | Failure-recording/unlink errors cannot prevent finally releasing the owned admission; original failures survive, successful worker handoff retains ownership and replacement tasks remain protected. Red6fail/1controlpass →56pass, including dual ENOSPC, unlink, next HTTP202and handoff. | PASS |
| #23 | Complete sibling receipt write/flush/fsync followed by exclusive hardlink publication. Preserve malformed receipts and recover only without a product; unverifiable existing products remain protected. Format/identity unchanged. Red3fail/6pass →28module/9targeted pass, restart/conflict and verified recovery without encoding covered. | PASS |
| #8 | Capture submitted snapshot and clear only its own draft; later editable values remain dirty while cache reflects actual accepted settings. Red1fail →6pass. Real backend persists ja, late response retains newer en, second save persists en. | PASS |
| #9 | Task/source identity bounds local editor state; page clamps to current results while ordinary edits/revisions retain valid page/search/advanced state. Red4fail →37pass; actual cached21-cue page2→2-cue task remains visible. | PASS |
| #10 | Initial task/source selection is distinct from explicit empty selection; subsequent documents prune every stale ID, including mixed valid/stale sets. Red4fail →43pass, covering clear, harmless bulk operations, task/source switches and split/undo. Actual parent/child remains0selected and first cue unchanged. | PASS |

Counts overlap and are not summed. This does not close #14 with #22, #13/#27/#37 with #23, or #24/#25 with editor changes.

## Fresh combined validation

- Full backend:**1042passed**,0failures/errors/skips,100.03s, one existing Starlette warning. Prepared Python3.11.16 matches51runtime pins;58packages compatible; all three requirements profiles validate.
- Actual shared release helper:2backend smoke,**232frontend tests/32files**, project TypeScript/Vite build and**17workstation browser cases**, final exit0. Initial typecheck rejected six new test-selector options; equivalent anchored-name regexes corrected them and the whole entry passed. Original failure retained.
- CLI and current frozen Companion each pass**1real same-origin smoke**. Additional actual workflows cover all5new IDs,0page errors and18state/viewport screenshots. Empty selection exits1; owned processes/temporary roots are cleaned and caller marker retained.
- Previous cache/source-replacement, real FFmpeg/SQLite/export-download-decode/failure-retry workflows pass again; WhisperX/provider boundaries remain controlled. Full backend covers previous redaction/process/SRT/queue/cleanup corrections.
- New CPU Docker image migrates fresh/legacy temporary DBs to20260714_01and retains old task/stage/queue data;93image source hashes match current backend. Host/container readiness200→locked503/tasks500→recovered200takes1.086/1.132s. Desktop restored stopped.
- Current macOS candidate built in the verified32distribution declared environment; frozen root/jobs HTTP200and deep strict signature pass, bundled frontend equals current build. Independent current frozen GUI/auth probe verifies synthetic valid/invalid RS256.
- Default Chromium and selected Chrome each pass4actual sandbox-on cases; invalid executable fails without fallback. Supplementary config inherits product selection; product runner defaults are unchanged.

Evidence:[18criterion matrix](/Users/drm/project/nyaru-clipper/.omo/evidence/phase3-recovery-and-draft-safety-2026-10-21/combined-acceptance.md),[actual QA](/Users/drm/project/nyaru-clipper/.omo/evidence/phase3-recovery-and-draft-safety-2026-10-21/manual-qa-report.md),[exit receipts](/Users/drm/project/nyaru-clipper/.omo/evidence/phase3-recovery-and-draft-safety-2026-10-21/qa-exit-receipts.json).339frozen source/config/test files identify candidate `20f2ae93ee965ab405f5eb5f8966022ea4755d5aaf180258d61d7f630c3fb445`. Before documentation updates, only11authorized source/test paths differed from471baseline files, none deleted;99original Companion source hashes match.

## Limits and next scope

Not run:Linux CUDA/WSL ROCm/full business Compose GPU stack, real download/provider/login/ASR inference, installed/native-window quit/reopen, or power-loss durability. Extra skill checker cannot resolve TypeScript and is not a pass; project typecheck/build did pass and LSP was not installed. Captures establish observed states, not a complete design/font/contrast audit. Undeletable uploads remain for later cleanup; no scheduler added.

[Final gate](/Users/drm/project/nyaru-clipper/.omo/evidence/phase3-recovery-and-draft-safety-2026-10-21/final-gate-review.md): **APPROVE, blockers=[], codeQualityStatus=WATCH**. Independently verified 339 source hashes, 11 authorized code/test changes, 99 original Companion files, 93 image source hashes and the final 1042-case XML. WATCH covers existing large modules and weakly typed cache dictionaries; no scoped behavioral failure was established.

Cumulative ledger: **18 accepted / 26 pending**. Remaining IDs: #11,#13,#14,#15,#16,#17,#18,#19,#24,#25,#26,#27,#28,#29,#30,#31,#33,#34,#35,#36,#37,#38,#39,#40,#41,#42. #37 still needs historical-draft compatibility design; #17 → #25 remain a later native logging/quit batch.
