# Subtitle styles, templates and ArcTime handoff

The local Companion's subtitle panel configures original and translated text independently: font, size, foreground, outline, background opacity, top/bottom placement and margins. The same parameters drive preview, ASS downloads and burned clips, reusing existing recognition/translation timelines.

For the new per-cue editor, precise X/Y positioning, advanced styles, autosave and matching libass preview, see [Per-cue subtitle editing](subtitle-editor.md). Global defaults and templates remain under the drawer's Global style section; original download links retain the original results.

## Use

The built-in “猫雷 Nyaru｜薄荷电波·中日双语” is the fresh-install default: 44-point pale-white Japanese rounded text, 64-point bold mint Chinese, dark-purple outlines, scaled from a 1080-high canvas. New live tasks select it automatically and allow opting out. Legacy bilingual/white presets remain available. Builtins are readonly; save edited copies. Existing saved defaults remain respected; this local installation explicitly changed the default through the settings API, with the previous value retained in the full backup.

1. Select a completed task, full video or clip, and original/bilingual mode.
2. Open the top Subtitle style tool. Edit individual cues as described in the per-cue guide; expand Global style at the drawer bottom to edit defaults or apply templates. The styled preview toggle controls the overlay; subtitle fullscreen includes an exit control inside the picture.
3. Export ASS, burn a clip MP4, or export an ArcTime ZIP. Burning requires a completed clip and a libass-capable FFmpeg; missing capability is shown explicitly.
4. Download the completed output. The macOS app uses native save panels. Each new output records the submitted style, language mode and scope.

Sizes/margins use a 1080-high reference canvas; explicit per-cue X/Y use source pixels. Editing-document previews, ASS and burns share libass rendering. Automatic bilingual placement reserves spacing; explicit coordinates bypass stacking, so inspect overlaps. Invalid positions/times are rejected. Install selected fonts on both machines; third-party ASS players and ArcTime can interpret fonts/styles differently. The retained legacy preview without an editing document uses browser typography.

## Two template types

### Import ArcTime ASS styles for live clips

1. Export UTF-8 or UTF-16 ASS from ArcTime with valid `PlayResX/PlayResY`. Open Subtitle style → Global style and templates → Import ArcTime ASS style. The limit is 1 MiB and 256 styles.
2. Choose the original and translation styles independently, name the template and save. A single style can serve both languages. The result uses the existing template storage, JSON export, copy and rename operations.
3. Create a live task, enter the room ID and select the saved live subtitle template. Submission freezes its style. Editing or deleting the template does not affect that task; resume retains the frozen style.
4. Completed clips automatically receive additional ASS and burned MP4 outputs under Export → Styled subtitle exports. Available translations produce bilingual versions; incomplete translation allows original-language versions first. Original clips/SRT and earlier exports remain intact. Style errors preserve capture and originals; resume processing after recording ends to retry.

Supported fields are font, size, BGR colors and text alpha, bold/italic/underline, outline, shadow, nine-way alignment, side/vertical margins, spacing, rotation and scale. Script pixel measurements are normalized to the 1080-high reference canvas and rescaled for each video. Only style definitions are imported: text, per-line position/movement, override tags, fades, animation and karaoke are excluded. Strikeout, independent outline/shadow alpha and opaque boxes receive unsupported/approximation warnings. Out-of-range parameters fail visibly instead of being clamped.

Fonts must be installed locally; no fonts are downloaded. Live browser typography is approximate; generated ASS/burned videos are authoritative. Completed editing documents use libass previews. Burning shares the sequential recording consumer with recognition/translation and can increase backlog. Without libass, choose no template to continue recording.

Style templates support save-as, copy, rename, confirmed deletion and JSON import/export. Builtins are read-only. Copy selects the returned copy identity. Saved defaults survive restart; reset changes the current draft. Invalid parameters, corrupt JSON and duplicate names produce errors.

ArcTime project templates register a copied `.atpj` file up to 16 MiB. They can be selected, downloaded, deleted and linked to a style template. Unlink a referenced project before deleting it. Native bytes are preserved; Nyaru does not reinterpret their media, text or effects as its preview style.

Storage is `<run-root>/templates/`, separate from the DeepSeek key configuration. In the macOS app it is `~/Library/Application Support/Nyaru Clipper/runs/templates/`. Style/default writes are atomic and permission-restricted.

## ArcTime editing

The ZIP contains matching video/ASS/original SRT, existing bilingual SRT, `style.json`, checksums and instructions, plus `template.atpj` when selected. Video has no newly burned subtitles. Clips start at zero; full subtitles retain source times. Generated entries use relative filenames.

Extract into a new working directory, import `source.mp4` or `clip.mp4` into ArcTime Pro, then import the matching ASS with styles. Edit text/timing. Optionally use ArcTime's import-styles-from-another-project command with `template.atpj`, checking duplicate names, groups and resolution: replacing names can overwrite the converted font sizes with the template's sizes. To keep Nyaru's appearance, import project styles before ASS styles. Save a new project and preview it: ArcTime can reassign layers and add fades, so inspect bilingual placement/backgrounds.

ArcTime may save a media-named ASS beside the video; work on extracted copies and keep the original ZIP. Opaque ATPJ files may contain prior media paths and ArcTime user identifiers; inspect your template before sharing it. For a reusable Nyaru JSON, use the style-template download control; `style.json` in the handoff records the rendering parameters.

The macOS open-ArcTime control launches the application; open-folder opens the run directory. The handoff provides editable files and native template reuse, without generating a populated ATPJ or calling cloud transcription.

## Preservation and retry

New `styled-<identity>.ass/.mp4/.zip` outputs preserve source videos, SRT and recognition/translation caches. Styles and renderer revisions receive separate identities. Identical verified outputs are reused. One operation runs at a time and submission freezes its style.

Retry failed/interrupted exports. Verified published files can be recovered into history; unexpected files or mismatched receipts are preserved with errors. Downloads verify checksums. Historical outputs without stored style metadata are labeled explicitly instead of displaying the current draft as their style.
