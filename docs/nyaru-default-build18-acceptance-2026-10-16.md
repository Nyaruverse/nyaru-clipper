# Nyaru builtin default and build18 local installation

Verified: 16 October 2026, Asia/Shanghai. Version 0.1.10 build18 was packaged, installed and launched. Implementation and packaging commits are recorded in the [current handoff](project-handoff.md); this delivery publishes only the Web/macOS development branches. Master is unchanged.

## Behavior and evidence

- Builtin `nyaru` exactly matches the approved Mint Signal JSON: Hiragino Maru Gothic ProN 44 for Japanese, Noto Sans CJK SC 64 for Chinese, mint/pale white/dark purple. Both fonts are available locally; no fonts were downloaded or bundled.
- Fresh default uses Nyaru; existing saved custom defaults remain respected. For this explicitly authorized local update, the installed settings API changed the current default to Nyaru, retaining its old value in the full backup.
- New live tasks select the builtin automatically with an opt-out. The package includes prior ASS inspection, task snapshots and incremental styled exports. Legacy templates, saved editing documents and old outputs remain intact.
- macOS backend: 231 relevant tests passed. Each worktree passed 77 frontend tests and production builds; the final default-selection adjustment also passed 28 macOS task-interface tests. Web additionally passed 24 backend template/input tests. Duplicate runs do not add coverage. One existing Starlette/httpx deprecation warning remains.
- The final frozen runtime performed real local ASR and a 1–4 second clip: three recognized cues, 3.000000-second audio/video output. Builtin defaults, ASS inspection, styled ASS/burn, libass PNG preview and font checks passed on isolated data.
- Native installed WKWebView visibly selected the Nyaru builtin for live clipping. No production recording/download task was submitted.

## Installation and preservation

Installed app: `/Users/drm/Applications/Nyaru Clipper.app`.

Previous app: `/Users/drm/Applications/Nyaru Clipper Backups/20261016-174807/Nyaru Clipper-build17.app`.

Full data backup: `/Users/drm/Library/Application Support/Nyaru Clipper Backups/20261016-174807/Nyaru Clipper/`. Backup parents are 0700 and contain private configuration/authorization state; retained locally.

All 6,561 existing files / 9,935,483,555 bytes, permissions and symlinks were identical across replacement. After launch/native checks, only `runs/templates/defaults.json` changed as requested and one startup file was added. All 20 historical job IDs, provider configuration, authorization status, media and models were retained.

## Package and limits

macOS worktree archive: `.omo/evidence/nyaru-default-build18-2026-10-16/Nyaru-Clipper-0.1.10-build18-macOS-arm64.zip`, 520,742,043 bytes, 3,877 entries, integrity verified.

SHA-256: `534b9e4bf176923483f2fdc20b1a9f368ebbb9d2b7769c187a8bc67b5ec2bc41`.

Strict ad-hoc signature passed. Still arm64, minimum macOS 27.0, not notarized. Real Bilibili long-running capture/download and external AI were not repeated. Saved historical editing styles and outputs are not rewritten by changing defaults. Detailed receipts remain in the same local evidence directory and are excluded from Git.
