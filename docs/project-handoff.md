# Browser companion handoff

**Remote synchronization addendum (2026-10-14)**: Current source and documentation were committed and pushed to three `origin` development branches: `feat/arctime-pro-plugin` (original workstation edits and complete development history), `codex/local-companion-web`, and `codex/local-companion-macos`. Verified remote feature commits were `d4f28f9`, `5baf166`, and `1366686`; use `git log -1` / `git ls-remote origin` for the latest subsequent handoff commit. Uncommitted/unpushed statements, older HEADs and dirty-original-checkout notes below describe earlier snapshots; this addendum supersedes their current Git status. The app retains shared browser fixes; `master` was unchanged.

Before synchronization, the original checkout passed 143 selected backend tests, 137 frontend tests, seven browser E2E tests and the frontend build. Browser passed 95 backend tests; app passed 99. Strict signing of the 0.1.1 package and legacy adapter Swift compilation passed. Original executable permissions were restored on 16 scripts and shell syntax checks passed. Models, media, app builds, private configuration and temporary automation evidence stay local. Real media/native-button acceptance was not repeated; notarization and a public release remain incomplete.

Updated: 2026-10-14. Development is split into two local branches:

| Branch | Scope |
| --- | --- |
| `codex/local-companion-web` | Local CLI and browser interface; URL download, offline text/sentence timestamps, range/highlight clipping, progress, preview, export and recovery |
| `codex/local-companion-macos` | Inherits the browser core; adds AppKit/WKWebView, native save, process cleanup, bundled tools/model and self-contained app build |

Both start from the original `0bcd8d5` base; the app branch inherits the browser commit. Fix shared behavior on the browser branch first, then synchronize it into the app branch. No paid ArcTime calls are made. The original `feat/arctime-pro-plugin` checkout and its earlier workstation edits are preserved. Models, media, tasks, configuration and builds are not committed. This is a local Git split; nothing has been pushed.

## Run and source map

Install the independent Python environment, FFmpeg, yt-dlp, whisper.cpp and multilingual small model using the [local guide](local-companion.md). From this branch's root:

```bash
cd web
corepack pnpm install --frozen-lockfile
corepack pnpm build
cd ..
~/.cache/nyaru-clipper/companion-venv/bin/python scripts/local_companion.py doctor
~/.cache/nyaru-clipper/companion-venv/bin/python scripts/local_companion.py gui
```

Open `http://127.0.0.1:8787/`. The local service serves the separate `companion.html` build; the old workstation need not run. Default history is this checkout's `data/local-runs/`; existing checkout/app history is not automatically migrated. Use `gui --output-dir /existing/run/root` to select existing history; do not run two services writing the same job.

```mermaid
flowchart LR
    U[Video URL] --> D[yt-dlp download]
    D --> A[FFmpeg audio preparation]
    A --> W[whisper.cpp recognition]
    W --> T[Full transcript and sentence timestamps]
    T --> R[Ranges or subtitle-rule highlights]
    R --> E[MP4 and rebased SRT]
    E --> P[Browser preview and download]
```

The entrypoint is `scripts/local_companion.py`; the core is `backend/app/arctime/{cli,workflow,local_asr,media,gui}.py`; the UI is `web/src/companion/`. `arctime` is a retained directory name. Early desktop adapters are excluded. Existing subtitle/highlight/CPU export services are reused; new workstation edits and app-specific sources are excluded.

## Validation and limits

On 2026-10-14 in this branch's independent checkout: **84 selected backend tests passed**, **154 frontend tests passed (21 files)**, TypeScript/dual-entry Vite build succeeded and CLI `doctor` returned ready. The frontend count differs from historical reports because earlier dirty workstation edits were excluded. A Starlette/httpx deprecation warning did not fail tests. Reproduce with:

```bash
PYTHONPATH=backend ~/.cache/nyaru-clipper/companion-venv/bin/python -m pytest \
  backend/tests/test_arctime_media.py backend/tests/test_arctime_workflow.py \
  backend/tests/test_local_asr.py backend/tests/test_local_companion_cli.py \
  backend/tests/test_companion_gui.py -q
cd web
corepack pnpm test --run
corepack pnpm build
```

[CLI acceptance](local-companion-acceptance-2026-10-12.md) and [GUI acceptance](local-companion-gui-acceptance-2026-10-13.md) retain historical branches, test selections and observation dates. They do not establish fresh real-media acceptance on this branch. Historical `.omo/evidence/`, models and jobs live in the original development checkout and are not distributed through Git.

Resubmit the URL after download failure; later ASR/export interruption is resumable. Preserve models, manifests, outputs and failed-run logs. Highlights use subtitle rules and ASR provides sentence timestamps. Word alignment, diarization, visual/LLM highlights, restricted public-site access, real long videos, Linux and cross-machine performance remain unaccepted. Do not restore paid ArcTime calls, edit runtime data or expose the service publicly.
