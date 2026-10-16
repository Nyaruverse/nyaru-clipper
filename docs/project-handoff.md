# Nyaru-Clipper project handoff

Verified: **16 October 2026, Asia/Shanghai**. This is the current entry point. Historical snapshots describe their observation time, not current heads, installations or service state.

## Publication and branch boundaries

This delivery adds per-cue subtitle editing on Web/macOS with shared preview, ASS and burned-video rendering. The user subsequently authorized installing build16 and committing/pushing this work and handoffs to the two development branches below, **leaving master untouched**. Implementation/tests are feature commits; usage, acceptance and this handoff follow in documentation commits.

| Development branch | Feature commit, before the handoff commit | Worktree |
| --- | --- | --- |
| `codex/local-companion-web` | `576b538d336cbeaf9c869f049f3b7d063ad9f792` | `/Users/drm/.codex/worktrees/local-companion-web/nyaru-clipper` |
| `codex/local-companion-macos` | `a132fcc6125380a5451e5cfe2dd335ec55260e81` | `/Users/drm/.codex/worktrees/local-companion-macos/nyaru-clipper` |

Publication uses an atomic push with explicit refspecs for those branches. The primary checkout's `feat/arctime-pro-plugin` and other branches are not pushed or merged. Local/remote master baseline is `0bcd8d503ac33f89c8e1cd526de5d7a44f6668b6`. Unrelated dirty work in the primary checkout is preserved.

Repository: [Nyaruverse/nyaru-clipper](https://github.com/Nyaruverse/nyaru-clipper), origin `https://github.com/Nyaruverse/nyaru-clipper.git`. Final HEADs include the following handoff commits, so the feature SHAs above are not final remote heads. Recheck when continuing:

```bash
git ls-remote origin refs/heads/codex/local-companion-web refs/heads/codex/local-companion-macos refs/heads/master
git -C /Users/drm/.codex/worktrees/local-companion-web/nyaru-clipper status --short
git -C /Users/drm/.codex/worktrees/local-companion-macos/nyaru-clipper status --short
```

The exact private publication receipt is in the macOS worktree's `.omo/evidence/subtitle-editor-2026-10-16/publish-receipt.json`, outside Git. Source publication and local installation do not establish notarization, public distribution or all-platform acceptance.

## Current features and entry points

The six-entry toolbar and independently scrolling right drawer remain. Open a completed task, click a cue, then choose Position. X/Y are output-video image pixels excluding player letterboxing. Drag the red + handle or focus it and press arrows for 1 pixel, Shift for 10. Anchor grid, snapping, safe area, centering, automatic positioning and original/translation linkage are supported. Batch moves use each cue's own previous position.

The Content/Position/Style/Timing tabs support independent original/translation text, partial emphasis, fonts/advanced layout, split/merge, frame adjustment, batch shifts, looping, style clipboard, undo/redo and serialized autosave. A per-language style is a complete override until inheritance is restored. Conflicts retain drafts; changed sources require explicit reset with a backup of the old editing document.

Edits live in task-local `subtitle-document.json`; source subtitles/media, recognition/translation results and prior exports remain immutable. Precise preview is a transparent image rendered by the same libass path as ASS/burning. Clip export intersects absolute source times and rebases them to clip zero; ASS precision is centiseconds. Burning remains completed-clips-only. Original SRT downloads remain original; edited SRT and JSON are included in ArcTime ZIP. See [per-cue editing](subtitle-editor.md).

## build16 installation, rollback and preservation

The installed app is **0.1.8 build16** at `~/Applications/Nyaru Clipper.app`. This build rebuilt the frontend, froze backend/tools/model, compiled the Swift shell and reapplied local signing. Strict signature verification and Swift typechecking passed. With no active task, build15 was quit normally, replaced, and build16 opened successfully.

- Old app: `~/Applications/Nyaru Clipper Backups/20261016-114616/Nyaru Clipper-build15.app`.
- Full data backup: `~/Library/Application Support/Nyaru Clipper Backups/20261016-114616/Nyaru Clipper/`, under a 0700 directory. It includes authorization configuration: keep it local; never commit or share it.
- All **6,560 files / 9,935,471,576 bytes** had identical hashes across replacement. After restart all **20 historical task IDs** remained; all existing files were checked again and unchanged.
- The unsaved custom style was retained as “升级前自定义样式 2026-10-16”. Native demonstration changed X640 to641 then undid it, restoring X640/Y656, saved revision2 and inherited styles. Only that task's editing document and startup file were added by the demonstration/restart.
- Local ZIP `Nyaru-Clipper-0.1.8-build16-accepted.zip` is in the evidence directory above:514,619,440bytes,3,914entries,SHA256 `2badc99dc66bb1cfa44888d3a976ce87a693710e02c9fc6e534d00d89a15ff17`. App/ZIP/model are excluded from Git.

## Verification and boundaries

| Scope | Result and evidence |
| --- | --- |
| Both frontends | Each10files/65tests passed; TypeScript/Vite production builds passed; overlapping coverage is not additive |
| Backend | 160 regressions covering subtitles/templates/APIs/rendering/GUI/translation/macOS passed; Web separately ran50 overlapping document/font tests |
| Actual Web UI | 1440/1920/390widths, both system appearance preferences, four tabs,48top/end captures; no horizontal overflow; existing light palette retained |
| Final frozen backend/native WKWebView | Bottom/center/top multiline bilingual placement, separate language nudges and linked numeric positioning passed; selected bounds move+1X/0Y, sibling stays fixed |
| Preview/ASS/burn | Actual ASS coordinates versus PNG; burned-frame/composited-preview RMSE1.355/1.507/1.422of255, including lossy encoding |
| Data/failure paths | Sample neighbour/source/old-export hashes retained; changed sources/stale revisions/invalid timing rejected while drafts retained; missing-font warning passed |
| Review | Earlier G1 automatic multiline-anchor jump repaired; fresh position code review APPROVE/no blockers, independently14frontend/41backend tests and actual ASS transitions |

See the [sanitized acceptance summary](subtitle-editor-acceptance-2026-10-16.md). Private raw evidence remains under the above `.omo/evidence/`: `acceptance.md`, `integration-receipt.json`, `native-candidate-*-verification.json`, `native-report.md`, `position-delta-review.md`, `installation-receipt.json`. Earlier rejecting reports and failing tests are retained as history, not current failures.

Not reaccepted here: real downloads, ASR, provider authorization/expiry/revocation, all font/glyph/style combinations, native save/confirmation panels, new machines or Intel/older macOS. The authorized replacement upgrade on this machine completed. Target remains arm64/macOS27.0+, ad-hoc signed and not notarized. Animations, karaoke, motion keyframes, perspective, vector masks and full-video burns remain outside scope.

## Preserved real-task observations

The 15 October handoff recorded these processing/translation states as completed. Media processing was not repeated. build16 installation verified full current data-directory file hashes; historical quality conclusions retain their original limits:

| Scenario | Task | Historical result |
| --- | --- | --- |
| Original full replay Saozi | `1bd089ad75b3` | 3275.299 seconds / 35 clips; Flash 658/658, original retained |
| User-requested OpenAI rerun | `3a01f1263649` | 34 clips; GPT-6-Luna 658/658; new cuts/translation, no Flash cache reuse |
| Local recording | `73fbcd311737` | 150.033333 seconds / 2 clips; ChatGPT 21/21 |
| Bilibili live recording | `68faca68e130` | 181.105 seconds / 2 clips; ChatGPT 40/40; first bilingual clip before stop |
| Web-created local task | `472c1adbd0d1` | 150.033333 seconds / 2 clips; ChatGPT 21/21; short tail retained |

Network interruption/recovery evidence is retained; successful recovery does not establish continuous provider availability. Translation/cut quality was sampled, not exhaustively proofread. Native build14 playback and NSSavePanel saving previously passed; the user did not grant WKWebView Downloads permission and explicitly accepted that boundary. Do not describe it as permission granted or technical acceptance. See [Web acceptance](web-app-acceptance-2026-10-15.md), [subscription acceptance](openai-subscription-acceptance-2026-10-15.md), [Saozi acceptance](saozi-acceptance-2026-10-15.md) and [bilingual completion](saozi-bilingual-acceptance-2026-10-15.md).

## Runtime, source and preservation rules

App data is under `~/Library/Application Support/Nyaru Clipper/`: `runs/`, `models/` and `app.log`. Provider settings are in `runs/config.json`; ChatGPT authorization is in `runs/.chatgpt/` (0700 directory / 0600 files). Never read, copy, commit or expose secret values. Templates live under `runs/templates/`. Preserve task manifests, source media, prior exports, failure and recovery evidence. CLI `data/local-runs/` history is not automatically imported.

The App's loopback port changes on restart; use current startup state, not a hardcoded old port. Never start a second service writing the same task root. No public exposure, multiple workers, paid/cloud ArcTime calls or **DeepSeek Pro**. Providers are DeepSeek Flash and ChatGPT subscription; new defaults affect new tasks only, retries retain the task's recorded provider/model, without automatic fallback.

Shared implementation lives in the feature worktrees under `backend/app/arctime/` and `web/src/companion/`. macOS-specific paths are `desktop/macos/`, `backend/app/arctime/macos.py` and `scripts/build_macos_app.py`. Never overwrite the App's frozen-tool logic with the Web branch's whole `media.py`. The primary checkout's legacy `backend/app/main.py` and worker are not the Companion launch path.

```bash
cd /Users/drm/.codex/worktrees/local-companion-web/nyaru-clipper/web
corepack pnpm exec vitest run src/companion
corepack pnpm build
```

Use the same commands in the macOS worktree's `web/` directory. Launch the installed App normally. Browser/CLI instructions: [local companion](local-companion.md); provider instructions: [ChatGPT subscription](openai-subscription.md); clipping: [Saozi](saozi.md).

## Next work and history

The authorized scope includes development-branch publication, handoff updates and this machine's build16 replacement installation. Full translation/cut proofreading, subtitle/ArcTime feedback, more platform validation, signing/notarization, public distribution and branch merges require a separate scope.

Preserved snapshots: [before subtitle-editor publication](project-handoff-history-2026-10-16-before-subtitle-editor-publish.md), [before toolbar publication](project-handoff-history-2026-10-16-before-toolbar-publish.md), [before the 15 October delivery refresh](project-handoff-history-2026-10-15-before-delivery-refresh.md), [15 October](project-handoff-history-2026-10-15.md) and [14 October](project-handoff-history-2026-10-14.md). Historical uncommitted/unpushed statements, build14 and old branch heads apply only to their observation time.
