# Nyaru default subtitle and build18 installation

The user approved the finished Mint Signal style and explicitly requested builtin/default integration and local replacement while preserving tasks/configuration.

- [x] Add the existing design as builtin template nyaru, use it when no saved default exists, retain old templates and custom defaults. Default the live creation selector to nyaru and preserve opt-out. Test persistence, readonly builtin identity, language styles and live request payloads.
- [x] Keep shared source in both development worktrees, run relevant backend/frontend suites and production builds, bump macOS to 0.1.10 build18 and freeze existing ASS/live changes into the package.
- [x] Exercise the frozen runtime with isolated data: actual local ASR/export, builtin defaults, ASS inspection and styled rendering. Verify native signature and archive.
- [x] Confirm no running production task, capture task/configuration status, quit the app, privately back up the old app and full data with hashes/permissions/symlinks, stage/replace the app, and launch.
- [x] Use the installed API to set only the requested subtitle default; verify every old data file except defaults.json and runtime startup/log files remains identical. Verify native UI, task IDs, provider state, fonts and builtin default; update paired handoff/acceptance docs. No Git commit/push or master changes.
