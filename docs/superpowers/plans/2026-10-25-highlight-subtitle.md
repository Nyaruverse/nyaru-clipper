# Highlight and subtitle integration implementation plan

> Execute tasks in this session using subagent-driven-development with review checkpoints.

**Goal:** absorb the collaborator's highlight algorithms and useful subtitle controls into both unified branches.
**Architecture:** reuse algorithms through unified operation adapters; reuse Documents, Publisher and libass; retain platform adapters.
**Tech Stack:** FastAPI, Pydantic, SQLModel, React/TypeScript, FFmpeg/libass.

## Global Constraints
Source commit 69d3fa0; preserve collaborator refs/history, original dirty worktrees, formal App/data and old readers. No force push, installation, model download or paid/live calls. Keep existing provider restrictions. No QR login, destructive re-ASR, setup replacement or graphics.

### Task 1: Unified topic analysis and export backend
Owner: backend implementation worker. Read `.omo/evidence/highlight-subtitle-20261025/backend-brief.md` for exact routes, inputs and acceptance cases.
- [ ] Port scoring/segmentation algorithms with source attribution and focused behavioral tests.
- [ ] Add validated analysis/export operation schemas, snapshotting, unified execution, immutable publication and projections/routes.
- [ ] Prove edited-document input, stale-version handling, cancellation, missing-factor cases, ordered export and adjacent queue behavior.
- [ ] Run focused tests, write report and review diff before marking complete.

### Task 2: Subtitle enhancements and highlight workbench
Owner: root. Files: existing subtitle_style.py/subtitle_render.py, subtitleStyle.ts/subtitleDocument.ts/TextStyleFields.tsx and tests; new HighlightPanel.tsx/topicApi.ts, existing Companion.tsx and companion.css.
- [ ] Add tests proving old-style compatibility and multiple outline rendering; implement outline layers in shared libass renderer and editor controls.
- [ ] Port font search/pinning with accessible keyboard interactions and preserved font validation.
- [ ] Bind topic API to the existing selected job/document, preview seeking and ordered selection/export; show queue/failure and missing-factor states.
- [ ] Run frontend tests/typecheck/build and backend rendering/document regressions; preserve existing editor behavior.

### Task 3: QA, review and macOS candidate
- [ ] Drive real isolated API/browser/media paths; collect artifacts and a QA matrix.
- [ ] Fix independent review findings and repeat affected checks.
- [ ] Commit explicit source/docs paths; create macOS candidate from fixed base and apply only shared integration commits.
- [ ] Verify shared-file identity/platform-specific preservation, run macOS build/native checks available locally and recheck collaborator remote SHA.
- [ ] Record exact commits, validation and unverified boundaries in paired delivery docs.
