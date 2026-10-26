# Watch Workbench — 2026-10-26

The user selected the **看片工作台** prototype. The unified Companion daily workspace now places the actual video beside actual highlight candidates. Analysis inputs, scoring details, task history, subtitle editing, template design and settings remain available through explicit controls.

## Behavior

- Clicking a candidate seeks its source range. Looping repeats that range; disabling looping stops at the endpoint. Start/end edits change the actual queued export, with local and server validation against source duration.
- Checked candidates retain selection order. The fixed footer shows selected count/duration. Generation opens a confirmation with reorder controls, separate/combined output, and subtitle language independent of preview language.
- Draft analysis inputs, selection and reviewed ranges are cached per task in the current UI session. Task/settings/template round trips retain drafts. A new analysis clears old selection/ranges and synchronizes the current preview. Reloading or restarting the UI starts a new session; this change adds no disk draft persistence.
- Partial/unknown coverage, unavailable scores, empty results, failures and stale subtitle revisions remain explicit. Saved subtitle changes still require reanalysis before export. Missing translations are checked over the reviewed range; original-language export remains available.
- Desktop uses two independently scrolling regions; <=640px uses a compact player above candidates with the generation footer visible. Phone users enter subtitle editing through Subtitle Correction.

## Verification

Both candidate source trees pass 346 frontend tests and TypeScript. The Web build and self-contained macOS candidate build pass. The backend range/highlight suites pass 37 tests. Generated OpenAPI/types reproduce identically.

Parent-operated browser QA covered 390×844, 960×760, 1440×1000 and 1920×1080, video seeking, loop/stop, reviewed ranges, reverse selection/reordering, independent original-language export, settings round-trip preservation, keyboard Tab/Escape/focus return, partial/empty/failed states, and a real subtitle save causing stale analysis followed by UI reanalysis. Partial/empty/failed response variants were deliberately injected by the isolated QA server; ordinary analysis/export used its actual local API and queue with synthetic provider responses and real FFmpeg.

Web and native exports preserved order [2, 0], with ranges 42–48 s and 0–20 s: 6 s and 20 s clips plus a 26.023 s combined video. The final native package was also checked against a fresh 43–45 s export. Evidence is under `.omo/evidence/watch-workbench-20261026/`; the final review is the parent session's inline self-review, as required by the Codex-specific review-work rule for this request.

## Candidate and boundaries

Final candidate: `/Users/drm/.cache/nyaru-clipper/watch-workbench-macos-20261026-04/Nyaru Clipper.app`.

It was launched explicitly with the independent fixture manifest `/Users/drm/.cache/nyaru-clipper/watch-workbench-native-20261026-01/runtime.json`. Reopen using the executable and `--unified-runtime` with that manifest; do not assume a direct double-click selects the test runtime. The candidate was not installed or copied over the formal App. Formal data, model installations and credentials were not changed. No external AI provider call, commit, push or publication occurred.

The theme remains explicitly light. A separate OS appearance toggle was not performed. Live platforms, real-stream highlight quality, GPU/WSL behavior, external-provider authorization and notarization are outside this frontend acceptance. Source revisions and the four pre-existing dirty handoff/integration files were preserved; see the preservation manifest for hashes. No new dependency was installed.
