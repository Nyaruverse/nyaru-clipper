# Local Companion Implementation Plan

**Goal:** URL -> local timed transcript -> explicit/highlight MP4 and SRT clips, with no ArcTime paid calls.

**Architecture:** Keep existing `app/arctime/media.py` helpers; replace the companion workflow's cloud stage with a local whisper.cpp adapter. Expose `scripts/local_companion.py` and `app.arctime.cli`. No worker, database or frontend contract change.

**Constraints:** Preserve unrelated dirty files. No commit/push. Python 3.11. macOS/Linux first. Local model setup separated from inference. Reject legacy cloud manifests. Use argument lists, no shell interpolation. No model downloads in regression tests.

- [x] Local ASR adapter (`backend/app/arctime/local_asr.py`, `backend/tests/test_local_asr.py`): write failing chunk-rebase, empty/invalid cue, cache identity and process-error tests; implement bounded FFmpeg/whisper.cpp subprocesses, validated local model settings and cached chunk reuse; rerun tests.
- [x] Local workflow (`backend/app/arctime/workflow.py`, `backend/tests/test_arctime_workflow.py`): replace cloud tests with local-only requirements, observe failures, implement version-2 jobs and local transcription recovery. Publish SRT/TXT/JSON, validate clip pairs on recovery and reject cloud jobs. Run media/workflow tests plus existing subtitle/highlight/export regressions.
- [x] Entrypoint (`backend/app/arctime/cli.py`, `scripts/local_companion.py`, `backend/tests/test_local_companion_cli.py`): test run/resume/doctor parser and nonzero failures; implement model/language/root/range/highlight options, sanitized errors, progress and recovery directory output.
- [x] Documentation and acceptance (`docs/local-companion.md`, `.zh-CN.md`, both docs indexes): document setup and executable commands, run CLI doctor/help and real localhost HTTP download -> local recognition -> both clip modes. Probe durations, streams and rebased subtitles; save evidence without URLs or credentials.
