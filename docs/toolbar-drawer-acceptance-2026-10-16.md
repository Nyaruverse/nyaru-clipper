# Top toolbar and right drawer · 16 October 2026

The user approved the conversation's “top options with right drawer” preview. Six entries replace the permanent sidebar: New task, Slicing, Subtitle style, AI settings, Task history and Export. The drawer starts closed. Clicking an entry opens it; clicking the active entry closes it; selecting another entry switches the single visible section. The close control and Escape also dismiss it and return keyboard focus to the active trigger.

Forms remain mounted so URL/range drafts, the selected local recording, template names and provider drafts survive toggles. Source and slicing controls share the existing submission form; required-input validation reveals the relevant section. The desktop drawer sits beside the preview and scrolls independently; narrow windows use a right overlay. Progress, connection/task errors, recovery and live stop remain in the workspace.

## Verification

- Both macOS and Web worktrees passed `corepack pnpm exec vitest run src/companion`: **5 files, 47 tests each**, overlapping coverage rather than additive counts. The pre-change baseline was 41 tests. New checks cover toggling, drafts, file selection, Escape focus and cross-section validation.
- Both passed TypeScript/Vite production builds with `corepack pnpm build` and `git diff --check`.
- The production frontend was driven with local HTTP/video fixtures through all six entries at 1440, 1920 and 390 widths with both system appearance preferences. Checks also cover drawer scrolling, empty/recording states, uninterrupted playback and reduced motion. The existing fixed light product palette remains; this is not a new dark theme. No browser JavaScript errors or real task/provider writes occurred.
- In the installed native window, all six triggers were opened and closed by clicking the same entry. URL draft preservation and Escape dismissal were also observed. Task counts were 20 before and after, with no active task during the update.
- Installed version: **0.1.8 build15**, `~/Applications/Nyaru Clipper.app`. This local update reuses build14's native launcher, frozen backend, tools and model, replaces the built frontend and build number, and reapplies local signing. Strict signature verification passed; referenced HTML/JS/CSS SHA256 hashes match the production build. The backend was not refrozen.
- build14 remains at `~/Library/Application Support/Nyaru Clipper/app-backups/2026-10-16-before-toolbar-build15/Nyaru Clipper.app`. Existing models, task directories and provider/authorization configuration were not migrated or cleaned.

Private evidence is under the macOS worktree's `.omo/evidence/toolbar-drawer-2026-10-16/`: `browser-qa.json`, `native-qa.json`, `install-assets.json`, viewport captures, `native-style-open.png` and `native-closed.png`. Evidence and candidate app copies stay outside Git.

## Limits

This verifies the UI and existing call contracts, without repeating real download, ASR, translation, recording, burning, export or native-save permission acceptance. No dependencies, API/database changes, Pro calls, master merge or public release were introduced. The toolbar implementation, tests and this acceptance record are published on the Web/macOS development branches; see the [current handoff](project-handoff.md) for commit and push status. Previous handoff content remains in historical snapshots.
