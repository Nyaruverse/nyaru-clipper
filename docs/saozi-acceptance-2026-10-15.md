# Saozi acceptance record: 2026-10-15

The later version is0.1.7 build11. See the [bilingual acceptance record](saozi-bilingual-acceptance-2026-10-15.md) for automatic bilingual output and online-validation limits. The0.1.6 evidence below is historical.

## Status

Implemented and installed as **macOS0.1.6 build10**. Full replay, paced live processing, local import and actual Bilibili live processing have observed evidence. After the user unlocked the Mac, playback and system export were verified in the installed native window using the Saozi task derived from40c0c9. The user confirmed normal audible output.

## Validation using40c0c9

| Flow | Independent validation task | Observed result |
| --- | --- | --- |
| Full replay | `1bd089ad75b3` | Continuous3275.299-second coverage,35 clips of60.139–119.84 seconds,34 real DeepSeek Flash calls; MP4 durations and zero-based SRT boundaries checked |
| Paced live simulation | `1276274cd22d` | Same recording fed at2x; real whisper.cpp and DeepSeek; two outputs before capture stopped, four final clips including28.3-second tail; capture exited |
| Local recording | `d8ad2ee92663` | Seconds300–450 from40c0c9 selected/uploaded through the actual UI to the installed bundle; real ASR and analysis;107- and43.033333-second clips; downloaded SRT hash matches the task artifact |

All56 protected original-task file hashes remained unchanged. Original media, subtitles, highlights and failure evidence are preserved. Reusing the accepted transcript does not revalidate full-source ASR. Cut semantics/reasons were not manually reviewed for every clip; complete topic coherence is not guaranteed.

## Bilibili and retained failure

An actual public room produced21.110667 seconds of readable capture and exited after stop. The installed UI then created actual Bilibili task `c1e3f1d167cf`: real ASR/DeepSeek,265.086662 seconds continuously covered by three clips of100.093/60.758/104.236 seconds. The first clip was published during capture; stop drained the tail without a disconnect warning. This is a short end-to-end check under current site conditions, not multi-hour reliability acceptance.

Task `d5732a75e13c` used a room that had ended by the test. The installed downloader returned `Streamer is not live`. The failed task is retained and is not counted as a pass.

## Regression and installation

- Selected backend: **257 passed**, including18 live/capture recovery tests. Selected frontend: **24 passed /4 files**. TypeScript/Vite build passed. Coverage is bounded and overlapping, not a whole-repository pass.
- Review reproduced the real ASR no-speech exception for offline input; Saozi now handles it without changing legacy modes. Disconnect warnings are exposed in the projection/UI.
- 1498 source/installed App files matched SHA256; strict signature verification passed for the installation and backup. Previous App: `~/Library/Application Support/Nyaru Clipper/app-backups/2026-10-15-0.1.5-build9-before-saozi/Nyaru Clipper.app`.
- Installed frozen backend reports `ready=true`;40c0c9 and new tasks are readable. Models, key, templates and previous exports are preserved.
- Actual UI inspected at390/1440 widths, with no horizontal overflow at390; preview decoded1280×720 video frames. A hidden-browser time=0 record does not establish continuous playback or speaker output.

## Local evidence

Browser worktree `.omo/evidence/`: `saozi-40c0c9.json`, `saozi-live-40c0c9.json`, `saozi-bilibili-capture.json`.

App worktree `.omo/evidence/`: `saozi-install.json`, `saozi-installed-local.json`, `saozi-installed-bilibili.json`, `saozi-native-acceptance.json`, `saozi-qa-matrix.md`, `saozi-ui/`. Native playback advanced from0 to10 seconds and was paused at21 seconds; the user confirmed normal audio. The first MP4 and SRT were exported through system save dialogs; both hashes match the task artifacts. The first save waited for macOS Downloads-folder permission and completed after the user allowed it; no code change was needed. Evidence contains private local paths/media and is excluded from Git.

Changes remain uncommitted/unpushed in the browser/App worktrees. Signing is ad-hoc; no notarization or public release. See the [Saozi guide](saozi.md).
