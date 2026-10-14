# Local video companion

The standalone browser GUI and CLI download one video URL, generate original-language text and sentence timestamps locally, and export explicit ranges or automatically ranked highlights. The GUI also supports optional DeepSeek bilingual translation and [subtitle styles, both template types, ASS, burning and ArcTime handoff](subtitle-styles.md). Recognition/clipping remain local; ArcTime integration uses files without cloud transcription.

## Browser GUI

The double-click macOS package is maintained on `codex/local-companion-macos`; this branch is `codex/local-companion-web`.

From the repository root, build the frontend once with Node.js 20+ and the project's pinned pnpm. Corepack uses the version in `web/package.json`.

```bash
cd web
corepack pnpm install --frozen-lockfile
corepack pnpm build
cd ..
~/.cache/nyaru-clipper/companion-venv/bin/python scripts/local_companion.py gui
```

Open the [local video workstation](http://127.0.0.1:8787). Dependencies and the build are already prepared on this development machine. Rebuild after frontend source changes. The original database/GPU workstation does not need to run.

1. Enter a video URL and language.
2. Choose one or more explicit time ranges, or automatic highlights with a maximum clip count.
3. Start processing and follow environment checks, download, transcription and per-clip export. Progress reports actual stages, without estimated percentages. One task runs at a time.
4. Preview the source after download and clips as they finish. The player supports recognized subtitles; click transcript timestamps to seek the original video or click the clip timeline to switch previews.
5. Download full SRT/TXT or individual MP4/SRT pairs. History survives page refreshes and service restarts.

Use the recovery button for recognition/export failures. Failed downloads require a new submission. Closing the page does not stop processing; keep the launch terminal open. `gui --port 8788` changes the port; `--output-dir`, `--model`, and `--threads` select the output root, model and thread count. The service binds only to loopback.

## Run on the development machine

From the repository root, use the prepared independent environment and multilingual `small` model:

```bash
~/.cache/nyaru-clipper/companion-venv/bin/python scripts/local_companion.py doctor
~/.cache/nyaru-clipper/companion-venv/bin/python scripts/local_companion.py run 'VIDEO_URL' --language zh --range 00:01:20 00:02:00 --range 180 210
~/.cache/nyaru-clipper/companion-venv/bin/python scripts/local_companion.py run 'VIDEO_URL' --language zh --highlights 3
~/.cache/nyaru-clipper/companion-venv/bin/python scripts/local_companion.py resume 'data/local-runs/RUN_ID'
```

Repeated `--range` accepts seconds, MM:SS or HH:MM:SS.mmm. Ranges and highlights are mutually exclusive; ranges must fit the media duration. `--output-dir` selects the job root, `--model` selects a local GGML file, `--language` defaults to `auto` (or use `zh`, `en`, `ja`, etc.), and `--threads` defaults to 4.

## Install on another machine

Use Python 3.11, uv, FFmpeg, yt-dlp and whisper.cpp's `whisper-cli`. No backend database or GPU workstation is required.

```bash
uv venv --python 3.11 ~/.cache/nyaru-clipper/companion-venv
uv pip install --python ~/.cache/nyaru-clipper/companion-venv/bin/python 'pydantic-settings>=2.6,<3' 'sqlmodel>=0.0.22,<1' 'anyio>=4,<5' yt-dlp 'fastapi>=0.115,<1' 'uvicorn>=0.32,<1'
```

On macOS:

```bash
HOMEBREW_NO_AUTO_UPDATE=1 brew install ffmpeg whisper-cpp
mkdir -p ~/.cache/nyaru-clipper/models
curl -fL --retry 2 -o ~/.cache/nyaru-clipper/models/ggml-small.bin https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-small.bin
```

On Linux, install FFmpeg and install/build `whisper-cli` following the [upstream instructions](https://github.com/ggml-org/whisper.cpp), then add it to PATH. Model downloads are a setup step, never an inference step. Use a multilingual model for Chinese, not an English-only `.en` model.

## Artifacts and recovery

Every job gets `data/local-runs/<id>/` containing `source.mp4`, full `subtitles.srt`, `transcript.txt`, structured `transcript.json`, MP4/SRT clip pairs, persistent `clip-*.log` export diagnostics, `job.json`, and `asr/chunk-*.json`/logs. The GUI adds `gui.json` for messages/errors without persisting the source URL. Clip subtitle timestamps start at zero. The GUI can additionally export `styled-*.mp4` burned copies while preserving the original clip.

After download, failures or Ctrl+C can be recovered with `resume`. Valid ASR chunks and completed clip pairs are reused. Changed source/model settings or modified outputs are rejected. Resuming a completed job verifies artifacts without retranscription. Failed downloads require a new run with the original URL, which is not persisted. Legacy ArcTime cloud jobs are rejected.

## Limits

Highlights use subtitle-gap windows and the existing density, punctuation, laughter and excitement rules with a 0.55 threshold, selecting up to N non-overlapping windows. This is especially suited to Chinese stream speech; it does not analyze game visuals or use a semantic LLM. Zero qualifying candidates retains the transcript and reports zero clips.

ASR uses five-minute chunks and sentence timestamps. Word-level forced alignment, speaker separation and continuous context across chunk boundaries are outside this iteration. Review recognition quality manually. URL coverage and access depend on yt-dlp; authenticated, restricted, live or protected sources are not guaranteed. Credentials are not requested automatically.

## Verification

Regression tests use external-tool stubs and do not download weights:

```bash
cd backend
python -m pytest tests/test_companion_gui.py tests/test_local_asr.py tests/test_arctime_workflow.py tests/test_arctime_media.py tests/test_local_companion_cli.py tests/test_highlights.py tests/test_export_encoding.py
```

Separately run the real CLI and inspect media streams, durations and rebased subtitles. Unit tests do not establish website access or real ASR acceptance.
