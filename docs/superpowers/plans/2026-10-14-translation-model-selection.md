# Translation model selection implementation plan

**Goal:** Select and persist DeepSeek Flash or V4 Pro for new bilingual translations in the existing App.

**Architecture:** Extend the existing private configuration endpoint with optional model updates that preserve the Key. Pass a validated model snapshot to translation requests and checkpoints. Started tasks retain their recorded model for retries; source files and existing outputs remain protected.

**Tech stack:** FastAPI, httpx, React/TypeScript, current macOS packaging; no new dependencies.

## Constraints

- Default `deepseek-flash`; supported alternative `deepseek-v4-pro`, verified in official documentation on 2026-10-14.
- Preserve Key-only legacy configurations, atomic saving and permissions 0600; never return credentials.
- Use existing source, timelines and translation caches; no download or recognition.
- Preserve unrelated dirty changes; do not commit or push.

## Implementation

- [x] Add failing GUI/provider/UI regressions for persistence, preserving Key, request model, cached-model retries and invalid selection.
- [x] Extend `backend/app/arctime/translation.py` and `gui.py`, then `web/src/companion/Companion.tsx` with a native select and save action.
- [x] Run targeted regressions and frontend build; synchronize shared files to existing web/App worktrees.
- [x] Rebuild/install App 0.1.4 build5; verify frozen persistence and visible UI with isolated test credentials.
- [x] Update paired guide/acceptance/handoff and privacy-filtered project maintenance record.
