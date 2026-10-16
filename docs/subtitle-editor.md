# Per-cue subtitle editing

Updated: 16 October 2026. Shared by Web and macOS Companion. Version 0.1.8 build16 was installed locally with the user's authorization, preserving historical tasks and data. See the [current handoff](project-handoff.md) for development-branch publication. The app is ad-hoc signed and not notarized.

## Usage

1. Open a completed task and click a transcript cue, or open the top Subtitle style tool. The drawer contains Content, Position, Style and Timing. Clicking a cue selects/seeks it; checkboxes support multiple selection. Search filters the list, paginated at 20 cues.
2. Content edits the current cue's original and translation independently. For local emphasis, choose the language, select text in the read-only selection box and apply color/bold. Editing that language's text clears its old emphasis ranges to prevent misaligned spans.
3. Position provides X/Y numbers, nine anchors, an on-video drag handle, arrow-key nudges, centering and automatic-position reset. Arrows move **one output-video pixel**, Shift moves ten. Shift constrains the main drag axis; Alt bypasses snapping. Guides and the safe area can be hidden.
4. Style provides font, bold/italic/underline, size, opacity, letter spacing, line height, wrapping width, rotation, X/Y scale, outline, shadow, background color/opacity/padding and hiding. Font suggestions come from the server's installed families. Missing families warn; unavailable enumeration is explicitly unknown. Family availability does not certify coverage of every glyph.
5. Timing provides start/end seconds, one source-frame shifts, batch offsets, splitting at the playhead and merging adjacent cues. Splits distribute text proportionally to time and need editorial review. Merges keep the first cue's independent style. Enable cue looping and start video playback to loop.
6. Position/style changes apply to the selected cues. Languages can be edited independently or linked. Copy/paste styles or positions, apply the global template or restore inheritance. Global styles/templates remain at the drawer bottom. An independent language style is a complete override; restore inheritance to follow later global changes again.

X/Y refer to the source video's effective picture, excluding player letterboxing. Existing font/margin units still scale from a 1080-high canvas. Explicit X/Y bypass automatic bilingual stacking; inspect intentional overlaps visually.

## Saving and preservation

Changes autosave after approximately 650 ms. Wait for the saved status before exporting. Undo/redo retain up to 100 session edits. Switching tasks preserves each task's draft within the current page; a normal restart restores successfully saved revisions. The browser attempts to warn about unsaved work on exit; this is not a substitute for the saved status.

Edits live in task-local `subtitle-document.json`, with optimistic revision checks. Invalid times/coordinates, changed sources or revision conflicts reject saving while retaining local drafts and the server's prior version. On error, expand the current JSON draft to copy a backup before comparing or explicitly restarting from source. Replacing a changed-source document preserves a backup first.

Original SRT, recognition/translation data, source media and old exports are not overwritten. Existing SRT/TXT links retain original results. Edits affect new styled exports. Do not edit source artifacts to bypass validation or run a second service against the same task root.

## Preview and export

The precise preview uses the same ASS/libass renderer as exports, compositing transparent images over the effective video picture. A changed scene shows rendering state instead of obsolete subtitle pixels. FFmpeg with libass is required. Editing invokes no ASR, translation or paid service.

- ASS retains edited text, per-cue styles, positions and times for full video or clips.
- Burned MP4 retains the effects for completed clips only. Lossy video encoding means its pixels need not equal the transparent PNG exactly.
- ArcTime ZIP includes edited ASS/SRT, the editing document, styles and existing handoff assets. SRT carries text/times only; advanced visuals need ASS or burning. Check third-party font/style interpretation after import.

Clip exports intersect absolute source times with the selected clip, clamp boundaries and translate to the clip's zero point. ASS has centisecond timing; preview follows the same boundaries, regardless of extra decimal places in time inputs.

## Verification and limits

Each worktree passed **65 Companion frontend tests** and TypeScript/Vite production builds; overlapping counts are not additive. **160 backend regression tests passed**, covering subtitles, templates, APIs, rendering, GUI, translation and macOS; an upstream TestClient deprecation warning remains. The Web worktree independently passed the 50 document/font tests included in that total. Multiline top, bottom and center positioning regressions cover converting automatic anchors into explicit coordinates without moving the other language.

Real synthetic HTTP workflows cover edit/save, transparent preview, ASS and burned video. Portrait and odd-size preview composites differ from direct ASS by at most 3/255 per channel. Final build16 frozen-backend/native-WKWebView tests cover multiline bottom, center and top pairs, separate original/translation nudges and linked numeric positioning. Preview versus burn RMSE was 1.355, 1.507 and 1.422/255 respectively; lossy encoding is included. Pixel bounds confirm a one-pixel horizontal move with unchanged vertical placement and unchanged counterpart. Adjacent cues, original files and old export hashes stayed unchanged. Changed-source, stale-revision and invalid-time requests were rejected in earlier acceptance; missing-font warning and restoration passed.

Private local evidence lives in the macOS worktree's `.omo/evidence/subtitle-editor-2026-10-16/`, including `acceptance.md`, `integration-backend.log`, `browser-reviewed-visual-matrix.json`, `native-candidate-{bottom,center,top}-verification.json`, `native-report.md` and `position-delta-review.md`. The earlier rejecting `final-gate.md` is retained as history; its G1 repair passed the fresh delta review and packaged-app checks. Evidence and synthetic media are not product source.

Real downloads/ASR/provider authorization, exhaustive fonts/glyphs/style combinations, native save/confirmation dialogs, new machines and Intel/older-macOS compatibility were not reaccepted. The build still targets arm64/macOS 27.0+. The existing fixed light palette remains under both system appearance preferences. Complex animation, karaoke, movement keyframes, perspective and vector masks are outside this scope.

This machine's build15-to-build16 replacement, startup, 20 historical tasks and full data hashes were verified; this does not accept fresh-machine setup. See [installation/acceptance](subtitle-editor-acceptance-2026-10-16.md).
