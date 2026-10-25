# Selective highlight and subtitle integration

The source is collaborator branch `feat/companion-topic-subtitle-updates`, pinned at `69d3fa0dea30a73ef0f0ef27591bc1abda9080f1`. Highlight and subtitle capabilities were adapted to the existing unified execution core, with provenance comments retained.

Web starts at `3e0582b47577b1fa7f26466fef7b78f7088c1fd7`; macOS starts at `73aa14b6def9e7e9b970a42621844e7c62f702f2`. Candidate branches are `codex/highlight-subtitle-web-2026-10-25` and `codex/highlight-subtitle-macos-2026-10-25`, prepared for fast-forward integration into `codex/local-companion-web` and `codex/local-companion-macos`. Existing platform differences and dirty original worktrees are preserved.

## Workflow

Open a task with saved subtitles in the unified-runtime Studio and choose 高光分析. Set an optional analysis interval and topic limit. Expand 弹幕与评分输入 to import a local XML/ASS file (UI limit 4 MiB), optionally naming a streamer/series to reuse its vocabulary profile.

Choose 分析高光话题, then start the unified queue from 任务记录. Analysis uses the current AI configuration and consumes the selected provider's quota in actual use. Results expose topic titles, summaries, hot terms, quotes and available scoring factors. Missing danmaku means no complete interaction score. Audio excitation is a heuristic, not validated laughter detection. Scores rank the current recording and require human preview.

Sort by time or score, select topics and generate separate or combined videos with original, Chinese or bilingual subtitles. Combined output follows selection order. Analysis/export use unified cancellation, retry and owned-process controls; admission freezes the document and configuration. Subtitle edits require reanalysis. Registered completed files are downloadable from the panel.

Per-cue advanced style editing, template design and subtitle settings share font search/favorites and layered outlines. Two extra outlines can supplement the base outline; preview and export use shared libass rendering. Existing content, timing, positioning, split/merge, undo and revision conflict protection remain in use. Favorites are browser-origin preferences: a macOS restart that changes the loopback port may lose the favorite list. Saved subtitle document styles persist.

## Verification and limits

- Backend full suite: **1589 passed, 3 skipped**. Independent recovery reader and final delta: **32 passed**.
- Frontend full suite: **338 passed in 41 files**; after the final mobile typography correction, **17 related tests passed**, with TypeScript and production build passing.
- Actual browser workflow produced 244 final screenshots at 390 CSS pixels, 1440 and 1920 under both system color preferences; the existing light design is retained. Coverage includes invalid import, queued/running states, offline cached presentation, keyboard selection, stale analysis and all three style consumers.
- Actual FFmpeg combined output was fully decoded and sampled to confirm reversed selection order (blue before red). Saved edits, undo and preservation of the adjacent cue were checked.
- A macOS candidate built and passed signature integrity verification. In an isolated runtime, native editing saved revision 3; after quit/reopen, text and three outline layers persisted. Recovery bundling now includes the outline type without modifying old reader pins.

Browser analysis uses an explicitly synthetic provider response. Media extraction, scoring, queueing, persistence and export run actual paths. No external AI calls, model downloads, real long-VOD semantic quality acceptance or new Windows/CUDA/ROCm qualification were performed. No formal App installation, formal data switch or historical migration occurred. QR login, Pro, remote danmaku fetching, destructive re-ASR/cleanup and rectangle graphics are excluded.

Local detailed evidence is under `.omo/evidence/highlight-subtitle-20261025/` in the Web candidate, including `backend-final-full.txt`, `browser-qa.json`, `media-qa.json`, `native-qa.json` and final reviews. Test media/screenshots are excluded from commits. The publication receipt there records final remote heads. Never push, rewrite or delete the collaborator branch.
