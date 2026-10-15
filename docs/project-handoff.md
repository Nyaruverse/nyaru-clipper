# Nyaru-Clipper project handoff

Verified: **16 October 2026, Asia/Shanghai**. This is the current entry point. Historical snapshots describe their observation time, not current branch heads, installed versions or service state.

## Publication and branch boundaries

The user authorized committing and pushing the top toolbar/right drawer change to the following two development branches, **leaving master untouched**. Implementation, tests and bilingual usage/acceptance notes are in the feature commits; this handoff and preserved snapshots are in the following documentation commits.

| Development branch | Feature commit, before the handoff commit | Worktree |
| --- | --- | --- |
| `codex/local-companion-web` | `cf2cfd0fefc2bd3f7e9925fb5f2be747c088daaa` | `/Users/drm/.codex/worktrees/local-companion-web/nyaru-clipper` |
| `codex/local-companion-macos` | `b0dee61d4112a2ce965dec9d92a779ca0b8e2361` | `/Users/drm/.codex/worktrees/local-companion-macos/nyaru-clipper` |

Publication uses an atomic push with explicit refspecs for these two branches. It does not push the primary checkout's `feat/arctime-pro-plugin` or any other branch. Local/remote `master` remain at baseline `0bcd8d503ac33f89c8e1cd526de5d7a44f6668b6`, without a merge. Unrelated dirty work in the primary legacy-workstation checkout is preserved.

Repository: [Nyaruverse/nyaru-clipper](https://github.com/Nyaruverse/nyaru-clipper), origin `https://github.com/Nyaruverse/nyaru-clipper.git`. Transfer completed on 15 October; account-role observations are preserved in the snapshot and are not a promise of permanent permissions.

Final branch HEADs include the subsequent handoff commits, so the feature SHAs above are not the final HEADs. Recheck them when continuing:

```bash
git ls-remote origin refs/heads/codex/local-companion-web refs/heads/codex/local-companion-macos refs/heads/master
git -C /Users/drm/.codex/worktrees/local-companion-web/nyaru-clipper status --short
git -C /Users/drm/.codex/worktrees/local-companion-macos/nyaru-clipper status --short
```

The exact private publication receipt is in the macOS worktree at `.omo/evidence/toolbar-drawer-2026-10-16/publish-receipt.json`, outside Git. This is development-branch source publication, not Developer ID signing, notarization or a public installer release.

## Current interface and local installation

The six top entries are New task, Slicing, Subtitle style, AI settings, Task history and Export. The drawer starts closed. Clicking an entry opens it; clicking the same entry closes it; another entry switches the single visible section. Close and Escape also dismiss it and return keyboard focus. Mounted forms preserve URL/range, local recording, subtitle-template and provider drafts.

Creation and slicing share the submission form; required-input validation reveals the relevant section. The desktop drawer sits beside the preview and scrolls independently; narrow windows use a right overlay. Progress, task errors, recovery and live stop remain in the workspace. Existing recognition, translation, clipping, styles/templates, ASS, burning and ArcTime file-handoff call contracts remain.

The installed version is **0.1.8 build15**, at `~/Applications/Nyaru Clipper.app`. The UI update reused build14's native launcher, frozen backend, tools and model, replaced built frontend resources and the build number, and reapplied local signing; the backend was not refrozen. Strict signature verification passed and referenced HTML/JS/CSS SHA256 hashes match the production build. The previous bundle is preserved at:

`~/Library/Application Support/Nyaru Clipper/app-backups/2026-10-16-before-toolbar-build15/Nyaru Clipper.app`

## Verification and boundaries

- Immediately before these commits, each worktree passed **5 Companion frontend files / 47 tests** and TypeScript/Vite production builds; coverage overlaps and must not be added. Whitespace and staged-scope checks passed.
- The preceding implementation phase drove the production UI with local HTTP/video fixtures through all entries, drafts, file selection, validation, Escape focus, drawer scrolling, continuous playback, empty/recording states and widths 1440/1920/390. Both system appearance preferences were exercised; the product retains its fixed light palette.
- In the installed native window, all six triggers opened/closed correctly, URL drafts survived switches and Escape dismissed the drawer. Task counts stayed 20 across installation, with no active task during the update. This Git-publication phase did not reprocess media, invoke models or change authorization.
- Private evidence is under the macOS worktree's `.omo/evidence/toolbar-drawer-2026-10-16/`: `browser-qa.json`, `native-qa.json`, `install-assets.json` and captures. Runtime data, media, credentials and private screenshots are excluded from Git.

See [UI acceptance](toolbar-drawer-acceptance-2026-10-16.md). Real download, ASR, translation, recording, burning, export and native-save permission acceptance were not repeated. Developer ID, notarization, public distribution, new-machine setup, Intel/older-macOS compatibility and actual token-expiry/revocation scenarios remain unaccepted. The build targets arm64 and macOS 27.0 or later.

## Preserved real-task observations

The 15 October handoff recorded these processing/translation states as completed. Media processing and full hash recomputation were not repeated here:

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

The authorized scope is development-branch publication and handoff updates. Full translation/cut proofreading, subtitle/ArcTime feedback, more platform validation, signing/notarization, public distribution and branch merges require a separate scope.

Preserved snapshots: [before this publication](project-handoff-history-2026-10-16-before-toolbar-publish.md), [before the 15 October delivery refresh](project-handoff-history-2026-10-15-before-delivery-refresh.md), [15 October](project-handoff-history-2026-10-15.md) and [14 October](project-handoff-history-2026-10-14.md). Historical uncommitted/unpushed statements, build14 and old branch heads apply only to their observation time.
