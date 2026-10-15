# Companion toolbar and right drawer

**Goal:** Implement the approved top-option toolbar and modeless right drawer. Clicking the active option closes it; selecting another option switches its content. Preserve drafts, preview playback, task control, and existing provider/export behavior.

**Architecture:** Keep the current Companion queries, mutations and mounted forms. A single `Tool | null` state controls six toolbar entries and the visible drawer section. Creation and slicing share one form; native invalid events reveal the input's section. SubtitleEditor supports embedded rendering while preserving its standalone disclosure.

**Stack:** React 18, TypeScript, existing Lucide icons and CSS design tokens; no new dependencies.

## Constraints and reference

- Approved reference: the "顶部选项 · 右侧抽屉" variant of the conversation's toolbar preview.
- The six entries are 新建任务、切片方式、字幕样式、AI 设置、任务记录、导出.
- Initially closed; one open section at a time; same trigger, close button and Escape dismiss.
- Toolbar remains reachable while the page scrolls; drawer is independently scrollable and does not cover desktop video.
- Keep progress, failures, resume and live stop outside the drawer.
- Keep form values mounted, including file inputs and local template/provider drafts.
- Web and macOS worktrees share identical changed frontend source. Preserve existing handoff edits and backend differences. No commit/push or provider call is required.

## Implementation and verification

- [x] Add behavioral tests in `web/src/companion/Companion.test.tsx` for click toggling, draft preservation, section switching and Escape focus return. The first run failed because the toolbar was missing.
- [x] Update `DESIGN.md`, `Companion.tsx`, `SubtitleEditor.tsx` and `companion.css`. Use `setTool(current => current === id ? null : id)`; keep hidden panel contents mounted. Reuse SubtitleEditor controls and query state.
- [x] Update existing Companion/ChatGPT tests to navigate via the toolbar before exercising their unchanged provider, job, export and resume assertions. All 47 Companion tests and the production TypeScript/Vite build pass.
- [x] Mirror only changed shared frontend/design files to the Web worktree; its 47 Companion tests and build pass too.
- [x] Drive the production UI through all six options, repeated-click close, Escape, cross-panel drafts, empty/completed/live states, validation failure, scrolling, desktop/narrow windows and reduced motion. Screenshots and action receipts are under `.omo/evidence/toolbar-drawer-2026-10-16/`.
- [x] Install and verify local macOS build15 using the existing build14 runtime; preserve build14 and user data. Native six-entry click toggling, draft preservation and Escape were observed.
- [x] Review the scoped diff and record verification boundaries in `docs/toolbar-drawer-acceptance-2026-10-16.md` and its Chinese counterpart. No real processing/provider operation was performed. The user subsequently authorized development-branch commits and pushes; publication is recorded in the current project handoff.
