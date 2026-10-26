# Watch Workbench formal installation — 2026-10-26

Installed **0.1.20 build 28** at `/Users/drm/Applications/Nyaru Clipper.app`, under the user's explicit installation request. Ordinary app launch and normal quit/reopen both entered Watch Workbench using `/Users/drm/Library/Application Support/Nyaru Clipper/unified/runtime.json`.

## Preservation

- The original legacy desktop root contains **0 registered 12-character task directories**; the original desktop inventory and the new API both contain zero tasks. No QA tasks/media were imported.
- All **21 original active data/configuration files** were backed up and remain byte-identical, including existing model, configuration and credentials. Existing app-backup directories were not moved or overwritten.
- Five existing public template/project files were registered byte-for-byte through the unified global-document store. Default subtitle style, all style/project templates, studio defaults, provider and model choice match the original API representation after reopen. Credentials remain referenced at their original `runs` path; the existing model path is retained.
- The queue starts paused. No recording/ASR/export task, external AI call, model download, source takeover/sealing, old recovery pin change, commit or push occurred.

## Package and verification

The installed backend, media tools and Web resources come from the tested `watch-workbench-macos-20261026-04` candidate. Only the native entry and bundle version were updated: absent explicit `--unified-runtime`, the native entry chooses an already registered `unified/runtime.json` in the standard Application Support folder, otherwise retaining the legacy default. An explicit runtime still has priority, and invalid registered manifests fail rather than silently resetting data.

Swift type checking and **8 native-related tests** pass, covering registered/default/explicit runtime selection plus existing quit/log/model/process behavior. Strict deep code-signature checks pass. The formal native UI and localhost API were checked before and after normal quit and reopening through the App entry. Receipt: `.omo/evidence/watch-workbench-install-20261026/after.json` in the macOS source worktree.

## Backup and rollback

Backup: `/Users/drm/Library/Application Support/Nyaru Clipper Backups/watch-workbench-20261026-085605`. It contains `data/` (the original active data), a verified old App copy, and `Original installed App.app` (the original installation preserved by rename).

To return to the old version, quit Nyaru Clipper, preserve the current installed App and new `unified/` runtime, then copy `Original installed App.app` back to `/Users/drm/Applications/Nyaru Clipper.app`. That original native entry uses the unchanged legacy data root; do not copy a stale backup over newer data. This rollback returns to the old view and does not import work subsequently created in the unified runtime.

The installation does not add real-stream highlight-quality, external-provider, GPU/WSL, reboot-protection or notarization qualification. The previous candidate-only installation statements are historical and superseded by this receipt.
