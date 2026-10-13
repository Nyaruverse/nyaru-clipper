# ArcTime companion

Superseded by `2026-10-12-local-companion-design.md`: the user selected local ASR and no ArcTime paid calls on 2026-10-12. This document records the previous design only.

The user approved a companion application with desktop automation, using ArcTime's whole-media speech transcription to produce both text and timings. This is not audio/text alignment with a supplied script.

## Scope

First implementation targets the installed macOS ArcTime Pro 4.5. A Python CLI downloads one HTTP(S) video URL with yt-dlp, imports a private working copy into ArcTime, opens speech transcription, retrieves the result, saves the project's ASS, converts it to SRT, and exports either explicitly supplied time ranges or the highest scoring highlight windows. It requires no WhisperX, translation, GPU worker, or backend database. Existing subtitle rendering, highlight scoring and video encoding remain the shared implementations.

macOS's accessibility tree does not expose this Java window on the development machine. A native Swift helper uses CoreGraphics window enumeration, Vision text recognition, and targeted keyboard/mouse events. Automation must target a verified ArcTime process and the same managed video throughout. It must refuse to replace an unrelated project. The helper compiles into an OS temporary directory; no application bundle is modified.

## Durable workflow

Each run uses a new directory with a manifest, source video, ArcTime project/ASS, normalized SRT, clips and per-clip SRT. The manifest is published atomically. A local desktop lock serializes ArcTime interactions and a run lock prevents concurrent modification of a run. Download filenames never contain URL data or remote titles.

Before a chargeable start click, persist `submission_pending`. After a successful click persist `transcribing`. Resume must never repeat the start click in either state. Save the ArcTime project after submission so task identity survives restarting ArcTime. On uncertainty report recovery instructions and retain the run. A resume operation opens the saved managed project and retrieves results; it never creates another cloud job. Login and engine selection remain account-specific prerequisites; automation checks the login state and rejects engines labelled as not producing a timeline.

The user may interrupt local polling; this does not cancel ArcTime's cloud job. UI updates, authentication, balances, cloud failures and missing permissions are explicit failures, not simulated successes. An exported, parsed, nonempty subtitle file is the only completion signal.

## Selection and output

`--range START END` is repeatable, accepts seconds or HH:MM:SS.mmm and must satisfy finite 0 <= start < end <= media duration. `--highlights N` selects up to N non-overlapping candidates using the existing subtitle-gap windowing and scoring. No candidates is a successful empty selection, never a fabricated fallback clip. Scores and reasons remain in the run manifest. Subtitle cues are clipped at range boundaries and rebased to zero.

Encode into unique temporary MP4 files, probe the output, then atomically publish. Never overwrite an existing final clip. On partial failure retain already completed clip pairs and resume the remaining selection. Source and selection identity are validated on resume.

## Acceptance

Tests cover malformed timings and subtitle files, ASS tags and commas, cue clipping/rebasing, ranking and overlap, atomic publication, stale source detection, failed/repeated cloud submission, desktop lock, and subprocess argument safety. A local HTTP video verifies real yt-dlp and ffmpeg. Native helper compilation and read-only ArcTime inspection verify the actual desktop surface. Full cloud acceptance requires the user's logged-in account and a supplied short video; mocked transcription does not establish that acceptance.
