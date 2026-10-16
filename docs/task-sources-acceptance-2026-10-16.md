# Task sources and build17 acceptance

Verified on 16 October 2026, Asia/Shanghai. This page records evidence and limits; see the [current handoff](project-handoff.md) for branch commits and local backups.

## Behavior

- New Task directly exposes live capture, download and local video. Enter a numeric Bilibili room ID or BV ID; the GUI requests identifiers only and the backend constructs canonical URLs. Existing HTTP(S) API clients remain compatible.
- Each source retains its draft. Inactive fields are disabled so they cannot block validation. Live always uses existing real-time saozi; returning to video restores the previous slicing choice.
- Downloads and local videos share ranges, highlights and saozi. Ranges/highlights need no AI configuration. Local import streams a task-owned copy and preserves the original.
- `POST /companion-api/jobs/upload` reuses upload handling, the one-job limit, disk checks and cleanup; `/saozi/upload` remains available. Invalid slicing is rejected before reservation; an empty upload releases the reservation for retry.

## Automated verification and build

| Scope | Evidence |
| --- | --- |
| Web Companion frontend | 10 files / 72 tests passed; TypeScript/Vite production build passed |
| macOS Companion frontend | The same 72 tests and production build passed; duplicate coverage is not additive |
| Related backend and macOS packaging | 115 tests passed, including three packaging checks; one Starlette/httpx dependency deprecation warning |
| Package | 0.1.9 build17; freshly frozen backend, tools, model and frontend, compiled Swift window, strict local signature verification passed |

Backend files are `test_saozi_inputs.py`, `test_companion_gui.py`, `test_saozi_api.py`, `test_saozi_live.py`, `test_arctime_workflow.py`, `test_saozi_workflow.py`, `test_companion_translation.py`, `test_local_asr.py` and `test_macos_subtitle_build.py`. The packaging checks exist only in the macOS worktree.

In each worktree's `web/`:

```bash
corepack pnpm exec vitest run src/companion
corepack pnpm build
```

## Observed workflows

A real browser imported an 11.2-second synthetic video into an isolated directory and performed real local ASR and a 1–4 second export. The final frozen backend repeated import, ASR and export successfully, producing three transcript segments. ffprobe confirmed a 3.000000-second clip with audio and video; source-copy hashes matched. Existing task data and external AI were not used.

All three sources were observed in the installed native App. BV and room identifiers were entered, then sample values cleared, without starting real download/capture tasks. All 20 historical task IDs, provider/authorization status and existing data-directory files matched. Backup and hash counts are in the handoff.

## Visual checks and limits

The initial matrix covered ten source/slicing states at 390/1440/1920 CSS widths, with drawer top/end captures: 60 images. A selected-source hover background overrode its ink surface and reduced contrast; selector specificity was corrected. After the user required identifier-only fields, fresh live/BV forms were captured at 1440/390 and the final native window was observed.

The browser tool supplies CSS viewport overrides, not full touch/mobile emulation. Paired appearance modes, full mobile devices and independent strict visual certification were not completed. The existing light paper theme remains. LSP servers were unavailable and were not installed; compilation and the tests above passed.

Real Bilibili downloads/long live captures, external AI renewal/revocation, every video format and additional machines were not revalidated. This remains arm64, macOS 27.0 minimum, locally signed and unnotarized. Source publication does not establish public distribution or acceptance of every workflow.

## Local evidence and protection

Web captures and initial records stay in the Web worktree at `.omo/evidence/task-sources-2026-10-16/`. Final native, package, installation and publication receipts stay in the macOS worktree at `.omo/evidence/task-sources-build17-2026-10-16/`. These directories are excluded from Git. Installation backups contain authorization configuration and remain private on this machine; do not share full manifests, logs or raw task data.
