# Per-cue subtitle editor and build16 acceptance

Verified: 16 October 2026.

Feature commits: Web `576b538d336cbeaf9c869f049f3b7d063ad9f792`; macOS `a132fcc6125380a5451e5cfe2dd335ec55260e81`.

| Scope | Result and evidence |
| --- | --- |
| Both frontends | Each10files/65tests passed; TypeScript/Vite production builds passed; overlapping coverage is not additive |
| Backend | 160 regressions covering subtitles/templates/APIs/rendering/GUI/translation/macOS passed; Web separately ran50 overlapping document/font tests |
| Actual Web UI | 1440/1920/390widths, both system appearance preferences, four tabs,48top/end captures; no horizontal overflow; existing light palette retained |
| Final frozen backend/native WKWebView | Bottom/center/top multiline bilingual placement, separate language nudges and linked numeric positioning passed; selected bounds move+1X/0Y, sibling stays fixed |
| Preview/ASS/burn | Actual ASS coordinates versus PNG; burned-frame/composited-preview RMSE1.355/1.507/1.422of255, including lossy encoding |
| Data/failure paths | Sample neighbour/source/old-export hashes retained; changed sources/stale revisions/invalid timing rejected while drafts retained; missing-font warning passed |
| Review | Earlier G1 automatic multiline-anchor jump repaired; fresh position code review APPROVE/no blockers, independently14frontend/41backend tests and actual ASS transitions |


## build16 installation, rollback and preservation

The installed app is **0.1.8 build16** at `~/Applications/Nyaru Clipper.app`. This build rebuilt the frontend, froze backend/tools/model, compiled the Swift shell and reapplied local signing. Strict signature verification and Swift typechecking passed. With no active task, build15 was quit normally, replaced, and build16 opened successfully.

- Old app: `~/Applications/Nyaru Clipper Backups/20261016-114616/Nyaru Clipper-build15.app`.
- Full data backup: `~/Library/Application Support/Nyaru Clipper Backups/20261016-114616/Nyaru Clipper/`, under a 0700 directory. It includes authorization configuration: keep it local; never commit or share it.
- All **6,560 files / 9,935,471,576 bytes** had identical hashes across replacement. After restart all **20 historical task IDs** remained; all existing files were checked again and unchanged.
- The unsaved custom style was retained as “升级前自定义样式 2026-10-16”. Native demonstration changed X640 to641 then undid it, restoring X640/Y656, saved revision2 and inherited styles. Only that task's editing document and startup file were added by the demonstration/restart.
- Local ZIP `Nyaru-Clipper-0.1.8-build16-accepted.zip` is in the evidence directory above:514,619,440bytes,3,914entries,SHA256 `2badc99dc66bb1cfa44888d3a976ce87a693710e02c9fc6e534d00d89a15ff17`. App/ZIP/model are excluded from Git.


## Limits and reproduction

Private local evidence directory: macOS worktree `.omo/evidence/subtitle-editor-2026-10-16/`. It contains `acceptance.md`, `integration-backend.log`, `native-report.md`, `position-delta-review.md`, `installation-receipt.json` and the local candidate ZIP; these artifacts are not committed.

See [usage](subtitle-editor.md) and [current handoff](project-handoff.md) for branch, backup and continuation rules. Run `corepack pnpm exec vitest run src/companion` and `corepack pnpm build` inside each worktree's `web/`. Publication verifies code hashes against the accepted version; it does not rerun recognition/translation or stop the open App. Exact selection/logs for the 160 backend tests remain in the private evidence directory.

Original media, screenshots, authorization configuration, App/model, full backup and private test logs are excluded from Git. Only the two development branches are published; master baseline stays `0bcd8d503ac33f89c8e1cd526de5d7a44f6668b6`. Developer ID/notarization/public distribution, fresh-machine setup, Intel/older macOS, real provider-expiry/revocation and exhaustive fonts/styles remain unaccepted. Burning supports completed clips only.
