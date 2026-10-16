# Per-cue subtitle editor implementation plan

**Goal:** Deliver the approved per-cue editor on Web and macOS, preserving source tasks, with matching libass preview, ASS and burned video.

**Architecture:** A versioned task-local editing document stores a source fingerprint, revision, global SubtitleStyle and editable cues. Each cue has a stable ID, absolute source times, original/translation text, optional complete TextStyle overrides, and optional per-language emphasis. Source artifacts are immutable. Export hashes include the exact editing document. Preview PNGs and exports use the same ASS renderer and source pixel coordinate system.

**Constraints:** No paid/cloud calls, no credentials read, no new dependencies, no master merge or remote push. Reuse existing worktrees. Test only synthetic data in an isolated root. Preserve original subtitle defaults and template JSON compatibility. Burn remains limited to clips. Keep macOS frozen-tool resolution intact.

## Shared contract

TextStyle retains existing fields; adds bold, italic, underline (bool), opacity (0..1), spacing (-10..100), line_height (0.5..3), align (1..9), x/y (nullable source pixels), rotation (-360..360), scale_x/scale_y (10..400 percent), shadow (0..20), shadow_color (#RRGGBB), padding (0..40), max_width (10..100 percent), hidden (bool). Defaults preserve current rendering. `position` and `margin` apply when x/y are null. Explicit x/y bypass auto stacking. `emphasis` on each language is a list of `{start:int,end:int,color:str,bold:bool}` using Unicode codepoint offsets.

`Cue`: `{id:string,start_seconds:number,end_seconds:number,text:string,translation:string,original_style:TextStyle|null,translation_style:TextStyle|null,original_emphasis:Emphasis[],translation_emphasis:Emphasis[]}`.

`SubtitleDocument`: `{version:1,source_fingerprint:string,revision:int,style:SubtitleStyle,cues:Cue[],width:int,height:int,duration:number,fps:number}`. Revision starts 0. Base cues use `cue-000001` IDs. New split cues use `edit-<UUID>`. GET `/companion-api/jobs/{id}/subtitle-document` loads/defaults the document. POST same path accepts the full document and performs optimistic concurrency against revision; returns incremented revision. Reject invalid/stale sources/revision or mutation while manager busy. Atomic writes, safe paths and symlink rejection. GET never writes. Do not alter original artifacts or migration state. Defaults come from existing TemplateStore.

POST `/companion-api/jobs/{id}/subtitle-preview` body `{document:SubtitleDocument,time:number,bilingual:bool}` returns transparent PNG of active cues using the exact export libass path. Supports unsaved documents after source validation; no persistent preview files. Source resolution including portrait is authoritative. Hide stale frame while new render is pending and show errors. Memory caching is bounded. PNG output alpha must survive. Subtitles remain stationary during their active interval (complex animations are out of scope).

ExportRequest gains optional `document:SubtitleDocument|null`. If supplied, validate source fingerprint, preserve original checksum validation, and clip edited absolute cue times against selected clip start/end from `job.json` ranges. Apply all intersecting cues with clamped relative times. Export receipts include document; old requests unchanged. ArcTime ZIP includes edited ASS/SRT and editing document. SRT carries text/times only. Original edit document stores source times even when clip selected. Global style field in request must match document.style to avoid ambiguity.

## Tasks

- [x] 1. Backend: extend TextStyle and add document models/store, API, per-cue ASS renderer, exact transparent preview and export integration. Tests first: invalid ranges/emphasis, stale source, revision conflict, symlink, no source writes, clip boundary mapping, hostile ASS text, advanced style tags and PNG alpha. Run existing subtitle style/template/API/renderer tests and new document tests.
- [x] 2. Frontend: typed contract plus pure editing helpers/history; tests first for split/merge, Unicode emphasis, undo/redo, multi-selection, inherited styles, pixel nudge and clip coordinates. Add task-keyed editor session with debounced serialized save and explicit save/conflict UI. Disable edited exports until saved/current. All pending edits survive switching tasks within mounted workspace. Add per-cue list, controls and image-based precise preview with pointer drag, keyboard nudge, anchor grid, snapping, safe area, language linkage, playback loop and batch timing. Reuse template editor for global settings. No modification to running tasks.
- [x] 3. Integration: mirror only shared edited source files into Web worktree; preserve macOS-specific code. Run both frontend builds/tests, backend suites and synthetic real HTTP workflow; compare active rendered PNG with ASS and burned frames. Browser QA desktop/mobile and native WKWebView on task-owned app/root, never installed user data. Verify source/old export hashes unchanged.
- [x] 4. Review and handoff: independent code and visual review, repair findings; bilingual usage/acceptance notes with exact commands, artifacts and limits. Keep private evidence outside tracked source. No push or install over user app unless explicitly requested.

## Acceptance

Every approved setting is reachable in both builds. Save/reload, undo/redo, split/merge and source conflict work. An edited cue affects only selected cues. Full/clip ASS and burn reflect identical text, styles, anchors and times. The preview contains actual libass pixels. Source hashes and old export hashes remain unchanged. Tests, production builds and browser/native observations are recorded separately; no release claims.
