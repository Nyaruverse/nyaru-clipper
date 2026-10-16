# ASS style import and live application acceptance

Date: 16 October 2026. This record describes ASS-stage validation before packaging. These changes were subsequently included in the installed build18 and the Web/macOS development-branch publication; see the [current handoff](project-handoff.md) and [build18 acceptance](nyaru-default-build18-acceptance-2026-10-16.md).

## Implementation

- Bounded UTF-8/BOM and UTF-16 ASS style inspection (1 MiB, 256 styles), Format-based fields, validated resolution/colors/fonts/numbers, BGR/alpha conversion and resolution normalization. Text and override commands are excluded. Users explicitly map original/translation styles and save ordinary templates.
- New live tasks select a saved template and freeze its style/digest. Finished clips automatically publish additional ASS and burned video; bilingual availability, including manual translation retry, triggers bilingual outputs. Template changes/deletion do not change existing tasks. Verified exports are reused.
- Errors preserve recording/originals and expose resume recovery. Completed live editing documents start with the frozen style; side margins agree across ASS, burning and editing anchors.

## Evidence

- Each worktree passed 227 backend tests, 75 Companion frontend tests and TypeScript/Vite production builds. Duplicate runs do not add coverage. One pre-existing Starlette/httpx deprecation warning remains; LSP is unavailable, so Python evidence comes from executed tests.
- Real Chrome/local API: inspect ASS, map languages, save template, select for new live task, reject invalid input without replacing the current style. Six mapping captures at 390/1440/1920 widths and light/dark preferences, plus selection/error captures; no browser script errors or horizontal page overflow. Existing paper colors remain under dark preference; this does not introduce a dark theme.
- Real FFmpeg/libass: 160.512 seconds of synthetic recording chunks produced three clips and six styled artifacts, with the first ASS/MP4 pair published before input ended. Inspected burned frame shows imported red text, black outline and top-left placement. First video duration: 60.2 seconds. Resume retained export identities without duplicate encoding.
- Local evidence: macOS worktree `.omo/evidence/ass-style-import-2026-10-16/`, including `browser-qa.json`, `media-smoke.json`, captures and isolated media. Evidence is excluded from Git.

## Limits

ASS input was synthetic; browser and FFmpeg were real. ASR/cut selection used fixtures. No real live connection, external AI or pixel-identical acceptance against a user-provided ArcTime ASS sample. Inline overrides, per-line positions, animation and karaoke are excluded; strikeout, independent outline/shadow alpha and opaque boxes receive warnings. Live browser preview is approximate; ASS/burned files are authoritative. Burning can increase backlog.

Existing user tasks, models, config and installed app were untouched. Work stays in the two existing development worktrees; the primary checkout and master were unchanged. See [usage](subtitle-styles.md).
