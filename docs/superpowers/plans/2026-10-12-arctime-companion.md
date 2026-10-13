# ArcTime Companion Implementation Plan

Superseded by `2026-10-12-local-companion.md`. Cloud transcription tasks below are historical and must not be executed for the local companion.

**Goal:** Video URL -> ArcTime speech transcription -> range/highlight MP4 and timed SRT exports.

**Architecture:** Independent local jobs avoid coupling a desktop cloud task to the existing GPU worker or SQLite transactions. Python orchestrates media and recovery; Swift reads and drives the verified ArcTime window. No additional production Python package is required beyond existing tools and dependencies.

**Constraints:** macOS ArcTime Pro 4.5 first; preserve existing uncommitted changes; do not commit or push; no credentials in manifests; no automatic resubmission; no unrelated project replacement.

## Task 1: Media contracts and exports

Files: `backend/app/arctime/media.py`, `backend/tests/test_arctime_media.py`.

- [ ] Write failing tests for `parse_time(value: str) -> float`, `read_subtitles(path: Path) -> list[SubtitleSegment]`, `select_clips(segments, duration, ranges, highlight_count) -> list[dict]`, `clip_subtitles(segments, start, end) -> list[SubtitleSegment]`.
- [ ] Run `/tmp/nyaru-arctime-tests/bin/python -m pytest tests/test_arctime_media.py` from backend. Missing module establishes the initial red test.
- [ ] Implement strict SRT and ASS parsing. Split ASS dialogue records with a maximum split of 9, preserve commas in text, drop override tags, convert line breaks, reject empty/invalid or unsorted timelines. Use shared `render_srt`.
- [ ] Validate times with `math.isfinite`, preserve complete words at clip boundaries, sort existing highlight scores descending and greedily reject overlapping windows.
- [ ] Implement `download_video(url, directory)` using yt-dlp argv, no shell, no playlist, bounded errors with no captured URL/cookie output. Probe video duration and streams with ffprobe.
- [ ] Implement `export_clip` with shared `execute_video_export` and a unique temporary destination, ffprobe validation, safe publication of MP4/SRT pairs and retry validation.
- [ ] Re-run focused tests and existing subtitle/highlight/export regressions.

## Task 2: Actual desktop bridge

Files: `backend/app/arctime/desktop.py`, `backend/app/arctime/bridge.swift`, `backend/tests/test_arctime_desktop.py`.

- [ ] Test that invalid platform, missing permissions, ambiguous windows, changed project, unknown OCR buttons and failed status cannot trigger a start click.
- [ ] Swift: list only `ArcTime Pro` windows; identify owning PID; verify its executable is inside the selected ArcTime app; activate it and recheck foreground PID immediately before each event. Capture only ArcTime windows and recognize Chinese/English text using Vision.
- [ ] Expose bounded inspect, keyboard and text/button actions as JSON over argv/stdout. Errors return a nonzero exit and a stable code. Compile once into an OS temporary directory.
- [ ] Python: preflight, import managed video, open Cmd+1 transcription, check login and timeline-capable engine, start once, poll result/get button, save managed project and ASS. Use concrete observed labels and fail closed on unknown dialogs.
- [ ] Compile bridge and verify read-only native inspection; verify import and transcription-dialog opening using a generated local test video. Do not press cloud Start without the user's provided acceptance video/account.

## Task 3: Jobs, recovery and CLI

Files: `backend/app/arctime/workflow.py`, `backend/app/arctime/cli.py`, `scripts/arctime_companion.py`, `backend/tests/test_arctime_workflow.py`.

- [ ] Add failing tests: end-to-end with a fake desktop boundary, `submission_pending` resume never calls Start, lock contention, source hash mismatch, partial exports, invalid selections before cloud submission.
- [ ] Implement atomic manifests with source hash, duration, mode/selection, state and completed clip pairs. Preserve source URL only for the active download call, never in the manifest.
- [ ] Use `fcntl.flock(LOCK_EX | LOCK_NB)` for a per-user desktop lock and per-job lock. Validate run-relative paths on loading manifests. Save pending state before crossing the cloud submission boundary.
- [ ] Implement `doctor`, `run URL --range START END [--range ...]`, `run URL --highlights N`, and `resume RUN_DIRECTORY`. JSON errors include stable codes and the recovery directory, not raw external command output.
- [ ] Test subprocess argument boundaries, timeouts, interrupted polling and completed-run idempotence.

## Task 4: Documentation and acceptance

Files: `docs/arctime-companion.md`, `docs/arctime-companion.zh-CN.md`, both docs indexes.

- [ ] Document setup, macOS permissions, ArcTime login/engine prerequisites, exact run/resume examples and cloud billing/recovery behavior.
- [ ] Run real download and both real export modes using an isolated local HTTP video and a known subtitle fixture. Verify durations, audio/video streams and rebased subtitles.
- [ ] Run focused tests, relevant existing regressions, CLI help/doctor, and native compilation.
- [ ] Compare final diff against pre-existing dirty files. Report cloud acceptance separately from local/media tests. Retain all failures and job recovery data.
