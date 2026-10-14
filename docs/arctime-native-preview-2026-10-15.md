# ArcTime native preview diagnosis and acceptance

2026-10-15 Asia/Shanghai. ArcTime Pro 4.5 on this Apple Silicon Mac.

The synthetic project's native video, bilingual subtitles and style preview passed. This closes the previously unconfirmed native-preview criterion; a lossless visual roundtrip is still not claimed.

## Cause and correction

ArcTime's Java main window3845 (PID49990) and video window4540 (`Mpv-For-Arctime`, child mpv PID73082) have different owners. The old Swift bridge enumerates only `ArcTime Pro`; `screencapture -l3845` omits the video window and shows a black placeholder.

Capturing the child player with `-l4540` shows video and subtitles. Raising ArcTime through the existing authorized Swift AX bridge and capturing the real display region with `-R323,212,1272,717` also shows the composited image. Repeated Java-only capture remains black while player/display captures pass. No player options, installed files or system settings were changed. The earlier full-region black screenshot remains a historical observation; it did not reproduce today, so not every earlier black capture is attributed to single-window capture.

QA now checks both the independent player and actual display. Window/PID/socket identifiers are session-specific and must be enumerated again in a new run.

## Observed acceptance

- At paused1.28s, native video shows white Japanese on a black background and smaller green Chinese in a separate lower position.
- The existing Swift bridge clicked native Play/Pause. Read-only mpv IPC confirmed `pause=false`, time advancement through3.12s and5.52s, then `pause=true` after Pause.
- At3.12s, both native-window and actual-display captures show Japanese, two-line Chinese, background, outline, colors and in-frame positions. Captures were opened and visually inspected.
- At5.52s, literal braces and backslash-N remain visible without becoming formatting commands.
- A real timeline click seeks to3.04s; the paused image still shows the bilingual multiline subtitles.
- The same synthetic-image check exits1 for two Java-only captures and0 for seven player/display captures. Blue coverage is98.47–99.07%, with white and green text pixels present. This fixture-specific check supplements visual inspection; it is not a generic video detector.
- SHA256 of `input-original.ass`, native-saved `clip.ass` and `clip.atpj` still matches the14October baseline.

Evidence directory: `/Users/drm/.codex/worktrees/local-companion-web/nyaru-clipper/.omo/evidence/arctime-player-2026-10-15/`. See [actual multiline screen](/Users/drm/.codex/worktrees/local-companion-web/nyaru-clipper/.omo/evidence/arctime-player-2026-10-15/screen-multiline-playing.png), [literal-character screen](/Users/drm/.codex/worktrees/local-companion-web/nyaru-clipper/.omo/evidence/arctime-player-2026-10-15/screen-literal-playing.png), [playback receipt](/Users/drm/.codex/worktrees/local-companion-web/nyaru-clipper/.omo/evidence/arctime-player-2026-10-15/playback-receipt.json) and [journal](/Users/drm/.codex/worktrees/local-companion-web/nyaru-clipper/.omo/evidence/arctime-player-2026-10-15/journal.md).

`verify-playback.py` records native button actions and read-only IPC state; its fixed identifiers and paused1–2s precondition deliberately constrain reuse. `swift check-preview.swift <screenshot paths...>` independently checks saved captures. Raw main-window captures may include an account marker and remain private; share player-region captures.

Only QA scripts and records changed, so no product rebuild or unrelated whole-repository test rerun was needed. ArcTime font rounding, fades, layer changes and same-name template overwrites remain limitations. Speaker audio, other fonts, machines and platforms were not checked. ArcTime is left paused on the synthetic project at3.04s.
