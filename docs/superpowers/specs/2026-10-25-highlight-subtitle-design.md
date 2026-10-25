# Highlight algorithms and subtitle editing integration

Approved scope: selectively port collaborator algorithms and editor enhancements into the current unified Web and macOS branches. Source commit: 69d3fa0dea30a73ef0f0ef27591bc1abda9080f1. Web base: 3e0582b47577b1fa7f26466fef7b78f7088c1fd7; macOS base: 73aa14b6def9e7e9b970a42621844e7c62f702f2.

## Contract
- Preserve collaborator refs and history, original dirty worktrees, formal App/data and pinned recovery readers. No force push, resets, cleanup, model downloads, external paid calls, installation or data migration.
- Port topic segmentation/title/summary, time-range options, danmaku import, audio/interaction scoring, hot terms/quotes and streamer profiles. Keep missing-factor states explicit. Scores are relative heuristics, not calibrated quality or literal laugh detection.
- Topic analysis and export run in the unified executor with frozen editing-document/config snapshots, cancellation and immutable publication. Inputs come from Documents/ResolvedArtifacts, never a fabricated live job.json.
- Support separate or combined selected topic exports in user selection order, using the current editor document and common libass renderer.
- Preserve all existing cue editing, split/merge, timing, positioning, undo/redo, source integrity and CAS. Add searchable/pinned fonts and up to three outline layers for both languages. Old documents remain readable.
- Keep Flash/ChatGPT provider limits; no QR login, Pro model, setup-script replacement, destructive re-ASR or global cleanup features. Rectangle graphics are outside this scope.
- Shared Web/macOS implementation is identical; retain native platform differences.

## Delivery
Isolated candidate commits for both named branch bases; local API/browser/real-media evidence and independent review. Remote publication is a separate reported state. No claim of external-provider or unavailable-platform acceptance.
