# Unified runtime candidate guide

Date: 2026-10-22. See [Chinese](unified-runtime-guide.zh-CN.md), [execution evidence](unified-architecture-execution-2026-10-22.md), and [acceptance design](superpowers/specs/2026-10-22-unified-architecture-design.md). These are implemented candidate entries; production cutover, App replacement, and retirement still require the plan's gates.

On 23 October, interrupted-recovery fixes entered the [new candidate App and independent recovery packages](candidate-package-2026-10-23.md), verified through frozen entries and actual isolated native workflows. Use that document's exact paths/hashes. Older epoch pins remain unchanged.

## 1. Initialize and run

Run from the repository root in an environment with the required engine installed. Replace the example absolute paths with the independent directories in the current inventory. Every newly created output directory must be absent. `credentials` references existing authorization and must remain outside the new data, protected source, and recovery bundle domains.

```bash
export PYTHONPATH="$PWD/backend"
backend/.venv/bin/python -m app.arctime.unified_cli init \
  --data /absolute/candidate --credentials /absolute/credentials \
  --model /absolute/ggml-small.bin --threads 4
backend/.venv/bin/python -m app.arctime.unified_cli serve \
  --runtime /absolute/candidate/runtime.json --port 0 --ready /absolute/ready.json
```

The runtime separates `db/tasks/settings/guard/registry/packages`; its queue starts paused. Browser creation registers tasks before they wait for queue admission. Browser, native, and CLI use the same SQLite state and executor. Only loopback or an explicit private LAN address is supported; `--host` rejects wildcard and public addresses. The existing trusted, single-user LAN boundary still applies.

Installation includes pinned yt-dlp. WhisperX also needs explicitly provisioned main/alignment models and NLTK punkt_tab. Set `APP_WHISPERX_MODEL_NAME/APP_WHISPERX_ALIGNMENT_MODEL_NAME` to local model directories and `NLTK_DATA` to a local data root containing `tokenizers/punkt_tab/english/`; verify inventory hashes before offline use. Qualification settings/download hashes are in execution section 8.4. On a WhisperX-only workstation, select WhisperX explicitly when creating tasks; CPP warnings describe the other engine. Engines are never silently replaced during execution; changed fonts/FFmpeg need separate qualification receipts.

```bash
backend/.venv/bin/python -m app.arctime.unified_cli queue --runtime /absolute/candidate/runtime.json
backend/.venv/bin/python -m app.arctime.unified_cli start --runtime /absolute/candidate/runtime.json
backend/.venv/bin/python -m app.arctime.unified_cli pause --runtime /absolute/candidate/runtime.json
```

`enqueue --request /absolute/request.json` uses the same discriminated request as `/api/v2/operations`: `process_recording/process_live/translate/export`. The server freezes the engine, public configuration, template/project bodies, input hashes, and document version. Browser configuration cannot replace this snapshot. Retrying an external call with an unknown potentially billed outcome requires explicit acknowledgement; it is never silently resent.

Build and run a macOS candidate:

```bash
backend/.venv/bin/python scripts/build_macos_app.py --unified-candidate --output-dir /absolute/build
"/absolute/build/Nyaru Clipper.app/Contents/MacOS/Nyaru Clipper" \
  --unified-runtime /absolute/candidate/runtime.json
```

The frozen backend also accepts `--unified-cli` and `--migration-cli`. Retain `--unified-runtime` during tests and relaunches: omitting it still enters the compatible desktop default path. Quit ends SSE before draining the executor and process groups. The native timeout offers continued waiting or explicit force quit; a forced exit requires recovery checks on reopening.

## 2. Register, prepare, and take ownership

Obtain the source UUID from external registration; never regenerate it from a path. Workstation roots include absolute `tasks/settings/database`, plus `media` for external references and `database_name` for the database filename. Relocation keeps the UUID and uses `register --mode relocate --expected-generation GENERATION` with new roots; aliases derive from the prior registration. Read-only Companion discovery never automatically turns unregistered directories into tasks.

Capture a complete public configuration with the old host's corresponding `APP_*` environment and an explicit runtime. Check all public Settings, provider/model choices, CPP model path, and threads. Private authorization stays a read-only reference; API keys, cookie contents, and OAuth tokens never enter the public package.

```bash
backend/.venv/bin/python -m app.arctime.migration_cli --runtime /absolute/candidate/runtime.json \
  capture-public --output /absolute/public-settings.json
backend/.venv/bin/python -m app.arctime.migration_cli --runtime /absolute/candidate/runtime.json \
  register --source SOURCE_UUID --origin companion --roots /absolute/source-roots.json \
  --public-settings /absolute/public-settings.json
backend/.venv/bin/python -m app.arctime.migration_cli --runtime /absolute/candidate/runtime.json \
  prepare --source SOURCE_UUID --legacy-id LEGACY_ID
backend/.venv/bin/python -m app.arctime.migration_cli --runtime /absolute/candidate/runtime.json \
  verify --batch BATCH_ID
```

`prepare` copies independent candidates, global packages, and history; `verify` validates them. Neither starts models or network calls, grants execution rights, or automatically starts legacy queued tasks. Saved subtitle revisions/words, titles/tags/archive state, and global templates/projects are preserved. Differing saved documents at multiple historical locations require explicit resolution.

Before takeover, freeze an independent recovery bundle and pin its `bundle.json` hash:

```bash
backend/.venv/bin/python scripts/build_unified_recovery.py --output /absolute/reader \
  --legacy-helper --tools-root /absolute/frozen-tools
backend/.venv/bin/python -m app.arctime.migration_cli --runtime /absolute/candidate/runtime.json \
  pin-recovery --bundle /absolute/reader/bundle.json --sha256 BUNDLE_SHA256
```

`frozen-tools` must contain verified ffmpeg/ffprobe and all required shared libraries, using the candidate App's collected tools or an equally complete directory. Use the `runtime-recovery-*.json` returned by `pin-recovery`. The bundle includes independent CPython, exact format readers, an archived UI helper, and media tools; it must not reference candidate sources or their virtualenv. The guard JSON contains `group_id/domains/locks/guard_root`, covering every old task/settings/database/external-media domain and old-entry lock; its control directory belongs to the new runtime's guard root.

```bash
backend/.venv/bin/python -m app.arctime.migration_cli --runtime /absolute/PINNED_RUNTIME.json \
  takeover --guard /absolute/guard.json --batch BATCH_A --batch BATCH_B --port 0
```

One Supervisor holds old locks, installs durable protection, rechecks source generation, atomically switches batch references, and continuously hosts the API. Do not release the Supervisor before starting execution. Record rejected old-write probes, all lock inodes, source hashes, reader/helper hashes, and the paused queue. Reopen through `serve-guarded` or native `--migration-guard` with the same pinned runtime/guard. macOS uses immutable flags. Linux requires a separately qualified read-only mount profile; chmod is insufficient, and a successful native ROCm installation does not qualify migration protection.

## 3. R0/R1/R2 and an unstartable candidate

| Category | Conditions | Allowed action |
| --- | --- | --- |
| R0 | The whole group was never activated and has no unified writes; queue paused and all execution rights released | Withdraw the whole group before restoring old permissions |
| R1 | The whole group was activated but has no unified writes or external dependencies; all execution rights released | With the same bundle and guard, commit whole-group withdrawal before restoring old permissions |
| R2 | Any unified task/subtitle/template/default/project write exists | Keep protection; make a consistent multi-root snapshot for read-only export or edit an independent legacy working copy |

Cancelling batch B never removes batch A's R2. A global-only template change also enters R2. Missing members, unknown schemas, missing/changed guard or bundle, live owners/groups, or unverifiable original lock inodes all prohibit thaw. Never replace a new database with an old schema or overwrite newer subtitles/exports.

While the candidate is available, export independent recovery recipes:

```bash
backend/.venv/bin/python -m app.arctime.migration_cli --runtime /absolute/PINNED_RUNTIME.json \
  recovery-recipes --guard /absolute/guard.json --output-root /absolute/recipes
```

Keep recipes, the pinned bundle, and hashes outside all data/authorization/source roots. When the candidate cannot start, use frozen Python directly. Do not start the candidate to repair schemas, recreate locks, or rediscover roots:

```bash
/absolute/reader/runtime/bin/python3.11 -I -S -B /absolute/reader/reader.py \
  --mode snapshot --manifest /absolute/recipes/snapshot.json \
  --output-root /absolute/snapshot --install-seal
/absolute/reader/runtime/bin/python3.11 -I -S -B /absolute/reader/reader.py \
  --mode read-only --manifest /absolute/snapshot/complete.json \
  --bundle /absolute/reader/bundle.json --output-root /absolute/recovered
```

Use the actual returned receipt path; an output directory alone does not establish completion. Snapshot holds existing GUI/heavy/guard locks and includes database/WAL, tasks, settings, packages, registry, and guard; authorization is only referenced. The reader emits the last registered JSON/SRT/ASS document, complete committed artifact sets, and task/publication/global-history indexes. It never reruns models, AI, or encoders. Unsaved client drafts are outside database recovery.

**If R0/R1 already took a sealed snapshot**, copy `thaw.json` to a new action recipe and add:

```json
{"sealed_snapshot":{"path":"/absolute/snapshot/complete.json","sha256":"COMPLETE_SHA256"}}
```

Retain all other original fields. Under the writer barrier, thaw temporarily restores only the new DB/guard control area's original permissions, commits whole-group withdrawal, restores old permissions, and reseals controls. New tasks/settings/media remain read-only. R2 is rejected before controls are restored.

```bash
/absolute/reader/runtime/bin/python3.11 -I -S -B /absolute/reader/reader.py \
  --mode thaw --manifest /absolute/thaw-sealed.json --bundle /absolute/reader/bundle.json \
  --output-root /absolute/thaw-receipt
```

**Resume after failure:** if snapshot sealing was interrupted, retain the first `source-protection.json`; use a new output directory and its pinned `protection_record/protection_sha256`, then repeat snapshot. Never infer original modes from already sealed permissions. If thaw committed withdrawal but failed while restoring old permissions, retain `controls-resealed.json`, obtain a fresh complete snapshot without `--install-seal`, update `sealed_snapshot` in a new thaw recipe, and add `controls_protection={path,sha256}` referencing that reseal journal. Continue with a new output directory after checking `withdrawing`, no activated bindings, and no new writes. Missing journals or changed bytes/inodes stop recovery.

**Resume after SIGKILL/process death (new 23 October bundles):** a kill bypasses finally, so `controls-resealed.json` may not exist. Preserve `<previous output>/thaw-intent.json`, fsynced before unsealing, its hash and the complete original recipe. Add only:

```json
{"interrupted_thaw":{"path":"/absolute/previous-output/thaw-intent.json","sha256":"INTENT_SHA256"}}
```

Do not change original `sealed_snapshot`, `controls_protection` (if present), bundle, guard or other fields. Use the same pinned reader, `--mode thaw` and a new `--output-root`. Original permission journals/inodes are checked inside the lock barrier; changed non-control roots or old original bytes are rejected. Only expected SQLite/guard control differences are permitted. The current DB must still have no R2 or execution ownership and must match the complete group withdrawal. A `thawed` group missing its final receipt only gets that receipt after original permissions and DB/guard proofs match; unified mappings are never regranted. Missing intent, mismatched pins or corrupt states stop recovery without guessing permissions or overwriting new data.

Per-file restoration is not atomic: parts of the old roots may become writable, and a kill after full restoration releases old locks. Group withdrawal has already committed before that point. If an old entry creates new bytes, subsequent recovery must refuse and preserve them. This is not continuous write denial throughout restoration. [Qualified boundaries](unified-architecture-execution-2026-10-22.md#9-2026-10-23-additional-m03m24-takeover-and-crash-recovery-qualification) do not replace actual reboot/every-timing/cross-platform qualification.

The fix applies only to newly frozen bundles. The pinned build-04 sample bundle and build-05 App do not contain it; do not modify their files or rebind an existing ownership bundle hash. Their original snapshots/read-only recovery remain retained. If an old bundle encounters an unqualified thaw interruption, preserve the scene; new-bundle evidence cannot qualify that old epoch retroactively.

The old UI only receives a verified old-format snapshot working copy. `legacy-browser` requires authorization-free `legacy={snapshot,files}` in the snapshot recipe and exact hashes/helper ABI. The helper uses a loopback dynamic port, blocks login, online processing and models, and reaps its process on exit. Never pass a new unified task root directly to an old-format entry.

## 4. Acceptance and remaining boundaries

Track M01-M28 in the [execution ledger](unified-architecture-execution-2026-10-22.md), separating implementation, tests, and platform acceptance. Linux CUDA, WSL ROCm, real live capture, AMF, actual old-entry/reboot protection, and production installation/cutover require their own evidence. server-194 is an additional native Linux ROCm qualification host; it cannot replace the two target GPU receipts.

P6 retirement still requires every mandatory P5 gate, zero remaining old-write callers, and a separately reviewed deletion scope. Old entries, compatible readers, old artifacts, unknown directories, and failed evidence are retained.
