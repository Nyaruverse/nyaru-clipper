# Local companion acceptance — 2026-10-12

Branch: `feat/arctime-pro-plugin`. Changes remain uncommitted. This report covers the local CLI, not the existing web workstation or ArcTime desktop automation.

## Verified surface

The actual `scripts/local_companion.py` entrypoint downloaded a generated Chinese video from a temporary localhost HTTP server, ran local whisper.cpp, produced complete SRT/TXT/JSON transcripts, and exported MP4/SRT pairs. The source was 20.4 seconds, created with macOS Tingting speech and an FFmpeg test video. No subtitle fixture was supplied to ASR.

Runtime: Python 3.11.16, whisper.cpp 1.9.5, multilingual GGML `small`, local FFmpeg and yt-dlp. Model SHA-256 matched upstream Hugging Face LFS metadata:

`1be3a9b2063867b937e64e2ec7483364a79917e157fa98c5d94b5c1fffea987b`

The independent environment is `~/.cache/nyaru-clipper/companion-venv`; the model is `~/.cache/nyaru-clipper/models/ggml-small.bin`. Homebrew installed whisper.cpp and updated its dependencies. No backend database was initialized by these CLI jobs.

| Mode | Run under `data/local-companion-acceptance/` | Result |
|---|---|---|
| Explicit ranges | `ranges/0869e21d99cf` | 2–8 s and 10–16 s produced two 6.0 s clips |
| Highlights | `highlights/1878b2958d6a` | One qualifying 20.4 s clip, score 0.77; requested maximum was two |
| Fresh uninterrupted run | `fresh/adb4fe536724` | Actual download → local ASR → highlight export completed without intervention |
| Final export/recovery | `final-ranges/4135da41f2fe` | Final exporter retained diagnostics; exact-match subtitle-only recovery regenerated the missing 6.0 s video without replacing SRT |

FFprobe confirmed audio and video streams and expected durations. FFmpeg decoded each output completely without errors. Subtitle boundaries were within clip durations, and sidecar SRT exactly matched clipped/rebased source cues. Completed-job resume preserved clip and subtitle hashes without additional ASR. Recognition recovered the expected Chinese text including “本地字幕工具” and “全部使用本地计算”; this is not a broad accuracy benchmark.

## Failures retained and resolved

- Initial Homebrew auto-update queued at the configured mirror. The first install ultimately completed; a concurrent retry hit a Homebrew lock and was not treated as success.
- The first real exports failed because the independent environment lacked `anyio`, imported indirectly by the shared exporter. Added it to the runtime and both setup guides, added Python export-import checks to `doctor`, and added CLI error regressions. Both jobs resumed from existing transcripts without repeating ASR.
- Initial legacy highlight regressions lacked Alembic in the isolated test environment. Installed the test dependency; subsequent selected regression run passed.

## Regression verification

Run from `backend/`:

```bash
/tmp/nyaru-arctime-tests/bin/python -m pytest tests/test_local_companion_cli.py tests/test_arctime_workflow.py tests/test_local_asr.py tests/test_arctime_media.py tests/test_arctime_desktop.py tests/test_highlights.py tests/test_export_encoding.py -q
```

Observed: **80 passed**, also rerun independently by the code reviewer. Coverage includes cached chunk integrity/source identity, timestamp rebasing, failed/empty recognition, locks, partial export and subtitle-only recovery, retained failed-encoding diagnostics, changed artifacts, CLI validation and legacy cloud job refusal. Tests stub external ML/tools; real inference evidence is the separate CLI runs above. `doctor` returned ready from outside the repository working directory. `git diff --check` passed.

Independent read-only code review approved the implementation with no blockers. Follow-up fixes preserve export logs and recover exact-match orphan subtitles. Pre-existing ASS parsing remains as a shared companion utility; JSON contracts retain the existing dictionary style. The review report is `.omo/evidence/local-companion-code-review.md`.

## Acceptance boundary

Public-site authentication/access, real long-video recognition quality and performance, word-level forced alignment, semantic/video-based highlight detection, a graphical interface and ArcTime import automation were not tested or implemented by this iteration. Five-minute rebasing is tested with deterministic subprocess fixtures. Current highlight selection uses local subtitle rules. This entrypoint contains no ArcTime desktop adapter or paid-service submission calls.
