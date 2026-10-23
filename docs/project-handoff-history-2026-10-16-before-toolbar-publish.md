# Nyaru-Clipper project handoff

## 16 October 2026 · Top toolbar and right drawer

The approved six-entry top toolbar is implemented: click to open the right drawer, click the same entry again to close, or use the close control / Escape. Drafts and local-file selections survive switches. Progress, task failures and live stop remain in the workspace.

The installed app is now **0.1.8 build15**. This local update reuses build14's launcher, frozen backend, tools and model, updating only the built frontend and build number before local signing. Strict signature and referenced frontend hash checks passed. All six native entries were opened/closed; task counts remain 20 before and after. build14 is retained at `~/Library/Application Support/Nyaru Clipper/app-backups/2026-10-16-before-toolbar-build15/Nyaru Clipper.app`.

Both development worktrees passed 47 frontend tests and TypeScript/Vite builds; coverage overlaps and is not additive. These changes remain local, uncommitted and unpushed, with branch HEADs unchanged and previous handoff edits preserved. No real processing or provider invocation was repeated. See [UI acceptance](toolbar-drawer-acceptance-2026-10-16.md). The 15 October text below is the preceding snapshot; this section supersedes its installed-version and toolbar state.

This checkout holds the earlier workstation source, designs and aggregate documentation. Current Companion feature source is in the two worktrees below; it has not been merged here.

Verified **15October2026, Asia/Shanghai**. This is the current handoff. Earlier versions, unpushed states and test counts remain in the linked historical snapshots, not as current status.

## Repository transfer and development access (verified 15 October 2026)

The repository transfer from `damin93381` to [Nyaruverse/nyaru-clipper](https://github.com/Nyaruverse/nyaru-clipper) was accepted and is complete. GitHub repository ID remains `1220984295`; `master` and the three development branch HEADs below match their pre-transfer values. This update did not change commit history, the GPL-3.0-only license or the existing `Copyright (c) 2026 damin93381` notice.

- The development account remains `damin93381`. GitHub reports the **write** role with `pull: true`, `push: true` and `admin: false`: development and pushing remain available, but repository administration does not. The new owner controls collaborator access and may revoke it.
- The primary checkout, Web worktree and macOS worktree now use `https://github.com/Nyaruverse/nyaru-clipper.git` for both fetch and push through `origin`. They share the primary repository's Git configuration, so other linked worktrees inherit the URL as well.
- Each of the three checkouts passed `git push --dry-run origin HEAD:refs/heads/<current-branch>` with `Everything up-to-date`. These were push previews; no commit was created or actually pushed.

This update covers only Git remote configuration and the transfer record. Handoff documents in all three checkouts remain local and uncommitted. App, provider, real-task and test results below are earlier acceptance records and were not rerun here.


## Current result

Installed **Nyaru Clipper0.1.8 build14** supports URL download, local whisper.cpp ASR, ranges/rule highlights, subtitle styles/templates, ASS/burn/ArcTime file handoff, plus **Saozi** semantic slicing of replay/local recordings and Bilibili live input. Saozi covers the content in approximately60–120-second slices and retains a shorter final tail; bilingual SRT output is automatic.

The provider selector offers **DeepSeek Flash / ChatGPT subscription**. Official ChatGPT authorization was completed by the user; safe configuration inspection currently confirms connected/sharing, default `gpt-6-luna` and backend ready. **DeepSeek Pro is disabled and must not be used.** New defaults apply to new tasks; task/checkpoint provider/model identity is retained on retry, with no automatic provider fallback.

## Commits and checkout ownership

The following local commits matched fresh `git ls-remote` results during this documentation update.

| Branch | Local and remote HEAD | Checkout |
| --- | --- | --- |
| `codex/local-companion-web` | `df66540a352328aeaf2a644bb3272210ecb60c85` | `/Users/drm/.codex/worktrees/local-companion-web/nyaru-clipper` |
| `codex/local-companion-macos` | `fbb81ff1ca22db06180051e741beef6c1ddcee8b` | `/Users/drm/.codex/worktrees/local-companion-macos/nyaru-clipper` |
| `feat/arctime-pro-plugin` | `e8ea71085cf5c6ff6f671499872f5c166d31f89b` | `/Users/drm/project/nyaru-clipper` |

Web/App implementation, tests and acceptance documents are **committed and pushed**. Remote `master` remains `0bcd8d503ac33f89c8e1cd526de5d7a44f6668b6`; no merge or public release occurred. Both feature worktrees were clean before the earlier functional handoff refresh; all three checkouts now contain uncommitted handoff updates, and the aggregate checkout retains earlier documentation/design changes. **The handoff refresh, transfer record and snapshots remain local, uncommitted documentation changes.** Do not reset or clean other work.

Commits: [Web df66540](https://github.com/Nyaruverse/nyaru-clipper/commit/df66540a352328aeaf2a644bb3272210ecb60c85), [App fbb81ff](https://github.com/Nyaruverse/nyaru-clipper/commit/fbb81ff1ca22db06180051e741beef6c1ddcee8b).

## Real tasks and acceptance

The current helper returned completed processing and completed translation for every task below. Media/hash/cue checks are prior acceptance receipts; this documentation run re-read terminal API status without rerunning processing or all hashes.

| Scenario | Task | Duration / clips | Translation and result |
| --- | --- | --- | --- |
| Original full Saozi | `1bd089ad75b3` | 3275.299s /35 | Flash,658/658; existing translations originally reused from40c0c9; original task preserved |
| Requested OpenAI rerun | `3a01f1263649` | 3275.299s /34 | ChatGPT GPT-6-Luna,658/658; new semantic decisions and translations, no reuse of Flash decision/translation caches |
| New local input | `73fbcd311737` | 150.033333s /2 | ChatGPT,21/21;73/77.033333s clips |
| Real Bilibili live | `68faca68e130` | 181.105s /2 | ChatGPT,40/40;107.705/73.4s clips, first bilingual output available before capture stopped |
| Browser-created local task | `472c1adbd0d1` | 150.033333s /2 | ChatGPT,21/21;114s clip and36.033333s retained tail |

The OpenAI rerun has34original and34bilingual clip SRTs plus the full bilingual SRT. Slices are64–118.4s, contiguous over the full source. Prior ffprobe checks found maximum duration deviation0.059675s; all150original task files retained their hashes. Translation stopped once at120cues and resumed the same task. The native App displayed34clips and658/658completed.

Browser QA exercised provider save/restore, file chooser/local upload, ASR/semantic slicing, network-failure continuation, bilingual playback, SRT download and reload persistence against the installed helper. The browser task initially failed at0/21, then completed after one UI retry; playback advanced and downloaded SRT SHA256 matched. This proves recovery, not uninterrupted provider availability. The model catalog also recovered after reload. The browser console had no warning/error entries at final inspection.

Native build14 playback and project-folder NSSavePanel exports passed. **WKWebView Downloads access was not granted after the user clicked the wrong option; the user explicitly accepted that portion without further testing.** Do not describe Downloads permission as granted or technically passed. The separate browser SRT download passed.

## Verification evidence and limits

- Latest feature checks: App selected backend **382passed**; Web selected backend **375passed**; Companion frontend **41passed across5files**; TypeScript/Vite production build passed. Backend selections overlap and must not be summed.
- Pre-commit staged checks passed and excluded runtime state, credentials, media and private screenshots. One existing Starlette HTTPX deprecation warning remains.
- Installed Info.plist was re-read as0.1.8/build14 and the existing helper was ready during this update. Strict signature/installation hashes, retained login and native saves belong to the recorded feature acceptance; they were not rerun here.
- No tests, new provider calls, live capture, media exports or App build ran during this documentation-only refresh. No new Git commit/push occurred.
- Translation and cut quality were sampled, not exhaustively proofread. Existing ASR/name/game-term errors may remain. Earlier Flash503/timeouts remain recorded; Flash availability was not retested. Never use Pro as a workaround.
- No Developer ID/notarization/public distribution, Intel/older-macOS acceptance, mobile/other-browser acceptance or independent fresh-machine setup acceptance. Expired-token renewal and remote revocation were not tested by waiting for expiry or revoking the user's grant.

[Web acceptance](web-app-acceptance-2026-10-15.md), [ChatGPT acceptance](openai-subscription-acceptance-2026-10-15.md), [Saozi acceptance](saozi-acceptance-2026-10-15.md), [bilingual acceptance](saozi-bilingual-acceptance-2026-10-15.md).

Private rerun receipts: `/Users/drm/project/nyaru-clipper/.omo/evidence/rerun-1bd089-openai-result.md` and `rerun-1bd089-openai.json`. Other private receipts include `openai-native-final.json`, `openai-install-hashes.json`, `openai-online-local.json`, `openai-online-live.json` and `web-release-2026-10-15/`. They remain local and must not be committed.

## Runtime and protected data

| Item | Location / rule |
| --- | --- |
| Installed App | `~/Applications/Nyaru Clipper.app`,0.1.8 build14 |
| Tasks/models/log | `~/Library/Application Support/Nyaru Clipper/`: `runs/`, `models/`, `app.log` |
| DeepSeek/provider configuration | `runs/config.json`; private values never returned in API/docs/logs |
| ChatGPT authorization store | `runs/.chatgpt/`; owner-only directory0700/files0600; do not read/copy/share credentials |
| Templates | `runs/templates/styles/`, `runs/templates/projects/`, `runs/templates/defaults.json` |
| Outputs | Per-task MP4, original SRT and `subtitles.ja-zh.srt` / `clip-NNN.ja-zh.srt` |
| Browser/CLI runs | Explicit output directory, usually checkout `data/local-runs/`; not automatically imported into App |

App ports change after restart; obtain the current loopback URL from the running App/startup state. Do not start another writer against its task root. Preserve models, task/translation manifests, original media, older outputs and failed-job evidence, including35b20d's fixed SSE parsing failure and earlier Issue#1 recovery. Never expose the helper publicly, add multiple workers, submit credentials/media/private evidence, or re-enable paid ArcTime calls.

## Source and next steps

Shared code is under `backend/app/arctime/`: `saozi*.py`, `live_capture.py`, `live_state.py`, `companion_*.py`, `translation.py`, `chatgpt_*.py`; UI is `web/src/companion/`. App-only source is `desktop/macos/`, `macos.py` and `scripts/build_macos_app.py`. The primary `backend/app/main.py`/worker remains the older workstation entry. Do not overwrite App `media.py` with the browser version.

Use [Saozi](saozi.md), [ChatGPT subscription](openai-subscription.md) and [local Companion](local-companion.md) guides. Run UI checks from `web/`: `corepack pnpm exec vitest run src/companion`, then `corepack pnpm build`. Shared backend checks use Python3.11 with `PYTHONPATH=backend`; include `test_chatgpt*`, `test_companion*`, `test_saozi*`, `test_live_capture.py`, `test_arctime*`, `test_local_companion_cli.py` and `test_subtitle*`; App also includes `test_macos*`.

No requested implementation remains blocked. Future work requires its own scope: sentence/cut quality review, user style/ArcTime feedback, wider host/platform testing, signing/notarization or merging development branches. These are pending, not accepted. The current App build targets arm64/macOS27.0+; do not claim older support by only changing Info.plist.

Previous handoff before this refresh: [snapshot](project-handoff-history-2026-10-15-before-delivery-refresh.md). Older pre-update records remain in the [14October](project-handoff-history-2026-10-14.md) and [15October](project-handoff-history-2026-10-15.md) snapshots. Their unpushed/version/Pro statements are historical.
