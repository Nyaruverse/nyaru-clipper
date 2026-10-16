# ASS style import and live application

Goal: import ArcTime-exported ASS style definitions, save a reusable bilingual template, and apply a frozen copy to live clips.

The user approved the ASS conversion approach. Reuse TemplateStore, TextStyle, SubtitleExports and the existing recorder. No dependencies, original-media rewrites or changes to existing tasks. Work in the existing macOS and Web development worktrees; master and the dirty primary checkout are excluded.

- [x] Add parser/API tests for resolution scaling, ASS BGR/alpha, alignment, malformed files, size limits and visible unsupported-effect warnings. Implement a bounded styles-only parser and inspection endpoint; save through the existing template endpoint after explicit language mapping.
- [x] Add import UI in the existing subtitle drawer: select ASS, choose original/translation styles, review warnings, save a named template. Keep JSON and ATPJ paths working. Verify in Vitest and a real browser.
- [x] Add an optional saved-template selector to new live tasks. Snapshot the template at submit, retain it on resume, and automatically export ASS and burned MP4 per completed clip using the existing registry and renderer. Publish original-language outputs first and bilingual outputs when ready; failure must preserve capture and originals and remain visible.
- [x] Test partial live export, pinned style after template changes/deletion, restart recovery, export errors and old jobs without templates. Run targeted backend/frontend regressions and production build; exercise real FFmpeg rendering on isolated media.
- [x] Synchronize shared changes to Web, update paired usage/handoff docs, and report exact verification boundaries. Packaging/install and Git publication remain separate follow-up actions.

Evidence and limits: [acceptance](../../ass-style-import-acceptance-2026-10-16.md).
