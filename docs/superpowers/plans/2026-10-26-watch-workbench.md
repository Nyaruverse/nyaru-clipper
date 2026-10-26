# Watch Workbench Implementation Plan

> **For agentic workers:** Use executing-plans inline, task by task. Do not commit or publish without a separate user request.

**Goal:** Implement the user-approved 看片工作台 using actual task video, highlight candidates, ordered selection and queued exports in both Companion frontends.

**Architecture:** Retain the existing player and subtitle session while presenting highlights beside it. Cache task-scoped highlight drafts in the existing QueryClient. Keep queue admission, revision checks and immutable publication. Add a bounded optional export-range override so the approved trim controls affect the real export.

**Tech Stack:** Existing React, TypeScript, TanStack Query, FastAPI/Pydantic and FFmpeg; no new dependencies.

## Global constraints

- Reference: `nyaru-highlight-designs.html`, variant 看片工作台, selected by the user in this chat.
- Reuse the two highlight-subtitle candidate worktrees; preserve their four existing modified documents exactly.
- Keep the light Companion design and its existing tokens; the root Workstation design remains separate.
- Do not install/replace the formal App, change formal data, call external AI, download models, commit or push.
- Never imply incomplete analysis covered the whole video; never remove document-staleness or translation checks.
- Native/HTTP QA uses a fresh independent fixture root and synthetic provider responses; real FFmpeg export remains required.

## Task 1 — Export the reviewed candidate range

Files: `backend/app/arctime/topic_models.py`, `backend/app/services/topic_admission.py`, `backend/tests/test_unified_topics.py`, generated OpenAPI/types when affected.

- [x] Add failing boundary and admission tests for `ranges=[{index: 0, start_seconds: 1, end_seconds: 9}]`: retain selection order, reject duplicate/unselected indices, inverted bounds and time beyond source duration.
- [x] Add frozen `TopicExportRange` and optional `TopicClipOptions.ranges`; validate at admission, freeze adjusted result boundaries and check translation over the adjusted range.
- [x] Run `PYTHONPATH=backend /Users/drm/.cache/nyaru-clipper/companion-venv/bin/python -m pytest -q backend/tests/test_unified_topics.py` and regenerate affected contracts with the existing exporter.

## Task 2 — Video and candidates form one workbench

Files: `web/src/companion/{Companion,StudioToolbar,TopicSegmentsPanel,SubtitlePreview}.tsx`; focused new draft, range and selection components; scoped CSS and `web/src/companion/DESIGN.md`.

- [x] Add red tests for draft preservation after remount/task switching, ordered selection, coverage warning, range payload, generation confirmation and bounded playback.
- [x] Cache draft by task; reconcile selections only for a new analysis identity. Keep analysis and export calls explicit.
- [x] Default the unified daily workspace to video plus highlights, hide auxiliary tools until opened, preserve the mounted player/session, provide analysis options and queue access without moving the player out of view.
- [x] Implement actual preview range, loop/stop, trim validation, selected duration/order and export confirmation. Show empty, unavailable-score, stale, truncated and failure states.
- [x] Test with `web/node_modules/.bin/vitest run src/companion`; build with `web/node_modules/.bin/tsc -b` and `web/node_modules/.bin/vite build`. Preserve legacy/live/template/settings regressions.

## Task 3 — Verify and hand off both sources

Files: paired `docs/watch-workbench-2026-10-26*.md`; `.omo/evidence/watch-workbench-20261026/` (local-only).

- [x] Review all callers; synchronize only the explicit shared source/test/design/doc files to macOS after confirming their old hashes match.
- [x] Use the existing isolated QA fixture pattern with a new root: real source video, actual local API/queue, synthetic provider, trimmed and reversed-order FFmpeg outputs. Never reuse formal or sealed domains.
- [x] Check rendered desktop and 390px layouts, keyboard controls, player persistence, failed/empty/stale/partial analysis, selection restoration and actual export artifacts. Record browser actions/screenshots and source hashes.
- [x] Run the parent inline gate review after hands-on QA under the Codex-specific review-work rule; fix proven blockers and rerun affected checks. Preserve pre-existing dirty documents and report implementation/validation separately from installation.
