# Highlight workflow fixes and real-video retest — 2026-10-26

Installed: `/Users/drm/Applications/Nyaru Clipper.app`, **0.1.21 build 33**, using the existing unified runtime, credentials and model. Real processing, exports and Web media checks passed. The user directly confirmed that the native App shows the video and plays it normally; human visual acceptance is recorded separately from automatic checks.

## Changes

- Separate translation provenance placeholders from actual provider models; retain credential, authorization and pinned-provider guards.
- Persist whisper.cpp's actual detected language, checksum it with cached chunks and bind it to the source. Keep the requested `auto` identity unchanged; publish verified `ja` to translation.
- Add explicit, mutually exclusive `recognition_only` recording support. Unified creation defaults to recognition followed by reviewed highlights, without an unrelated 30-second preclip; manual, legacy and live workflows remain available.
- Request selective highlights instead of a full topic partition. Target 40% duration and allow complete cue boundaries, rejecting totals above max(60 seconds, 50% of the analysis span). This is not general subjective-quality acceptance.
- Preview separate and combined outputs directly without source overlays, source-global looping or a misleading timeline. Preserve source return and review controls.
- Fix focused range editing at 760×560, toolbar wrapping, and clipped generated video at 390×844. Show the saved task title/source, immediately refresh a changed title, avoid vnull, and explain recognition-only empty exports honestly.
- Persist validated per-task review drafts across same-origin reloads; retain stale-analysis reset and storage failure handling.

## Real run

Source: the same real `直播-1276274cd22d.mp4`, **328.300 seconds**, 1280×720. No synthetic video, fake captions or mocked provider was used.

Task: `7a69c98888d15620b3aa11e9fba5dbc9`, titled `真实高光完整复测 · build30 · 自动日语`.

The native UI imported the file, queued local ASR with automatic language, generated **50 cues / ja / no preclips**, and directly requested actual DeepSeek translation: **50/50 cues, document v1**. Native highlight analysis covered all cues and returned **4 candidates totaling 131.800 seconds (40.15%)**, without filling the requested maximum of five. Missing audience scores remained unavailable.

Native review selected `[2,0]`, with ranges **272.9–315.0** and **141.4–204.7**, and confirmed a combined bilingual export. All four task operations succeeded. Actual Web playback and download buttons produced two **42.100 / 63.300-second** clips and a **105.421333-second** combined video. All three fully decoded with FFmpeg: H.264 + AAC, 1280×720. Decoded frames show N2/listening content first and unread-message content second, with burned-in bilingual captions.

Generated playback starts at zero and has no source overlays or loop. Original-source looping at 300–303.2 seconds still works, and disabling it stops exactly at 303.2. Same-origin reload restores reviewed selection/ranges. Final build 33 layouts and Web playback were captured afresh. The full real processing run used build 30; subsequent builds changed CSS/build metadata only, with identical backend Python and frontend JS content hashes.

An interim failed analysis on `f98b6a7d...` is preserved: an overly strict initial 40% guard rejected whole-cue boundaries. It is not counted as a pass.

## Evidence

Directory: `/Users/drm/.codex/worktrees/highlight-subtitle-macos/nyaru-clipper/.omo/evidence/watch-workbench-fixes-20261026/`.

- `frontend-final.txt`: 365 frontend tests passed; `build-33.log`: typecheck, build and signature.
- `web-backend-final.txt`: 139 related backend tests; `integration-tests.txt`: 32 native/translation checks; `cue-budget-green.txt`: 62 boundary checks after calibration.
- `final-install-runtime.json`, `final-operations.json`, `final-media-validation.json`, `real-bilingual-*.mp4`, decoded frames.
- `compact-build33.json`, `phone-build33.json`, playback/loop/reload receipts and screenshots.
- `data-preservation.json`, `review.md`, `frontend-report.md`, `source-sync.json`, `shared-fix.patch`, `polish-equivalence-final.json`.

## Preservation, rollback and limits

The **21 original files**, **two existing task contexts**, source digest, public template/workflow setting response hashes and registered runtime manifest remain unchanged. SQLite quick_check passed. The queue is paused; four real test tasks and the interim failure remain. No credentials, model downloads, sealed historical sources, recovery pins, commits or pushes were changed.

Backup: `/Users/drm/Library/Application Support/Nyaru Clipper Backups/workbench-fixes-20261026-1723/`, containing the original installed 0.1.20 App and a pre-update unified snapshot. Quit normally and preserve current data before switching Apps; never overwrite newer data with the older snapshot.

- **Native visible playback was accepted by the user**, who directly replied “可以看到并正常播放” (can see it and it plays normally). See `native-human-acceptance.json`. Native controls and HTTP 206 ranges are observable automatically, but native captures remain black and coordinate activation fails with noWindowsAvailable. Native visual acceptance therefore comes from the human confirmation, not an automatic pixel check. Web frames, natural playback to the end and full file decoding were independently checked.
- Random native ports change the localStorage origin, so review drafts do not survive App restart. Frozen exports remain durable. Historical `auto` jobs without actual language metadata are not guessed or rewritten; re-recognize them or use the new verified task.
- No word-for-word linguistic, long-VOD/live, dark-system, Windows/GPU, crash-recovery or notarization acceptance is added. Captions and subjective highlights still require human review.
