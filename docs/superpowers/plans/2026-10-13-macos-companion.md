# macOS Companion Implementation Plan

> Execute inline in the existing feature checkout, with observable checkpoints.

**Goal:** Deliver a self-contained macOS app for the approved local companion.

**Architecture:** AppKit/WebKit wraps the existing companion interface. A bundled
one-directory Python helper serves an ephemeral loopback port; native libraries,
downloaders and model are included. Data persists outside the application.

**Tech Stack:** Swift/AppKit/WebKit, Python 3.11/PyInstaller 6, existing FastAPI/React,
FFmpeg, yt-dlp and whisper.cpp.

## Global constraints

- arm64; minimum macOS 27.0 for currently installed native dependencies.
- Preserve existing dirty files, runs, model and CLI behavior.
- Runtime PATH must not require Homebrew or developer virtual environments.
- Keep generated outputs under ignored `dist/`; no commits or remote publication.

### 1. Frozen helper and resource resolution

Files: `backend/app/arctime/macos.py`, `media.py`,
`scripts/macos_companion.py`, `backend/tests/test_macos_companion.py`.
Interfaces: `prepare_model(resources: Path, data: Path) -> Path`;
`main(argv: list[str] | None = None) -> int`; frozen media resolves tools from
`sys._MEIPASS`, downloader re-enters the helper with `--yt-dlp`.

- [x] Write tests for bundle priority/missing tools, checksum failure preservation
  and first-launch atomic model provisioning.
- [x] Run `PYTHONPATH=backend ~/.cache/nyaru-clipper/companion-venv/bin/python -m pytest backend/tests/test_macos_companion.py` and observe missing-module failure.
- [x] Implement the helper, port-zero socket, readiness JSON and parent/process
  group cleanup; rerun new tests and the existing local companion regressions.

### 2. Native window and relocatable package

Files: `desktop/macos/App.swift`, `scripts/build_macos_app.py`.
Interface: helper takes `--data`, `--ready`, `--parent-pid`; readiness is
`{"url": "http://127.0.0.1:<port>", "pid": <helper pid>}`.

- [x] Build React with `corepack pnpm build` in `web/`.
- [x] Freeze minimal Python environment, native executable/library closure and
  GGML runtime backends; include dependency license files.
- [x] Compile Swift window, startup/error status, native save panel and standard
  edit/quit menus. Sign nested binaries and the final app ad hoc.
- [x] Relocate `dist/Nyaru Clipper.app`; inspect non-system load paths and run its
  bundled helper/tools with PATH `/usr/bin:/bin`.

### 3. Real surface acceptance and delivery

Files: `docs/macos-app.md`, `docs/macos-app.zh-CN.md`,
`docs/macos-app-acceptance-2026-10-13.md`, `.omo/evidence/macos-*`.

- [x] Open the native app, run actual URL range/highlight workflows, preview a
  clip and save video/subtitles through the native panel.
- [x] Reopen history and quit; inspect process group and port cleanup.
- [x] Request an independent read-only review and resolve material findings.
- [x] Prepare local app/ZIP links with tested platform and signing limits; record
  verified durable progress only in permitted project maintenance notes.
