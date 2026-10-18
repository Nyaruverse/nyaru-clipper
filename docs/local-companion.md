# Local video companion

The standalone browser GUI and CLI download one video URL, generate original-language text and sentence timestamps locally, and export explicit ranges or automatically ranked highlights. The GUI also supports optional DeepSeek bilingual translation and [subtitle styles, both template types, ASS, burning and ArcTime handoff](subtitle-styles.md). Recognition/clipping remain local; ArcTime integration uses files without cloud transcription.

## Browser GUI

The top New task / Slicing / Subtitle style / AI settings / Task history / Export entries open a right drawer. Click the active entry again, use its close button, or press Escape to dismiss it. Drafts and local-file selections survive switches; progress and live stop remain in the workspace. See the [UI verification](toolbar-drawer-acceptance-2026-10-16.md).

For the double-click package with bundled tools and model, see the [macOS app guide on the macOS branch](https://github.com/Nyaruverse/nyaru-clipper/blob/codex/local-companion-macos/docs/macos-app.md).

From the repository root, build the frontend once with Node.js 20+ and the project's pinned pnpm. Corepack uses the version in `web/package.json`.

```bash
cd web
corepack pnpm install --frozen-lockfile
corepack pnpm build
cd ..
~/.cache/nyaru-clipper/companion-venv/bin/python scripts/local_companion.py gui
```

Open the [local video workstation](http://127.0.0.1:8787). Dependencies and the build are already prepared on this development machine. Rebuild after frontend source changes. The original database/GPU workstation does not need to run.

1. Under New task, choose 实时录播 (live capture), 下载视频 (download), or 本地视频 (local video). Enter a Bilibili room number, BV identifier, or choose a local file respectively. Enter identifiers directly; the application generates their URLs. Each source retains its draft when switching.
2. Downloads and local videos share explicit ranges, automatic highlights and saozi choices under Slicing. Live capture always uses saozi and requires AI configuration; switching back restores the previous video slicing choice. Local import creates a separate copy without modifying the original. Ranges and highlights do not require AI authorization.
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
uv pip install --python ~/.cache/nyaru-clipper/companion-venv/bin/python 'pydantic-settings>=2.6,<3' 'sqlmodel>=0.0.22,<1' 'anyio>=4,<5' 'httpx>=0.28,<1' 'PyJWT[crypto]>=2.10,<3' yt-dlp 'fastapi>=0.115,<1' 'uvicorn>=0.32,<1'
```

On macOS:

```bash
HOMEBREW_NO_AUTO_UPDATE=1 brew install ffmpeg whisper-cpp
mkdir -p ~/.cache/nyaru-clipper/models
curl -fL --retry 2 -o ~/.cache/nyaru-clipper/models/ggml-small.bin https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-small.bin
```

On Linux, install FFmpeg and install/build `whisper-cli` following the [upstream instructions](https://github.com/ggml-org/whisper.cpp), then add it to PATH. Model downloads are a setup step, never an inference step. Use a multilingual model for Chinese, not an English-only `.en` model.

## Native Windows (PowerShell, no Docker)

This path runs the standalone Companion on CPU, using Python and whisper.cpp. It does not start the separate GPU workstation API/worker stack. Install Python 3.11 (or let uv obtain it), uv, Node.js 20+ and Corepack first. From the repository root:

```powershell
uv venv --python 3.11 .venv
uv pip install --python .venv/Scripts/python.exe 'pydantic-settings>=2.6,<3' 'sqlmodel>=0.0.22,<1' 'anyio>=4,<5' 'httpx>=0.28,<1' 'PyJWT[crypto]>=2.10,<3' yt-dlp 'fastapi>=0.115,<1' 'uvicorn>=0.32,<1'
Set-Location web
corepack pnpm install --frozen-lockfile
corepack pnpm build
Set-Location ..
```

Install Windows FFmpeg/FFprobe from a [build linked by FFmpeg](https://ffmpeg.org/download.html), and `whisper-cli.exe` from the [whisper.cpp Windows releases](https://github.com/ggml-org/whisper.cpp/releases). Put the executables on PATH, or copy them into the ignored repository `.bin/` directory. Keep the whisper.cpp DLLs beside `whisper-cli.exe`; copying just the executable is insufficient. The CPU `whisper-bin-x64.zip` build is sufficient; CUDA is optional and has not been validated by this path.

Download the multilingual model once:

```powershell
New-Item -ItemType Directory -Force data/model-cache/whispercpp | Out-Null
Invoke-WebRequest 'https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-small.bin' -OutFile data/model-cache/whispercpp/ggml-small.bin
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/dev_companion.ps1 -Command doctor
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/dev_companion.ps1
```

Open <http://127.0.0.1:8787> and keep the terminal running; Ctrl+C stops the service. The launcher enables UTF-8, adds the virtual environment and `.bin/` to the process PATH, and uses repository-relative defaults even when launched from another directory. `-Python`, `-Model`, `-OutputDir`, `-Port` and `-Threads` override those defaults.

Local-file recognition and explicit-range export have been verified on Windows with the multilingual `small` model and the upstream JFK audio sample. ChatGPT sign-in is unavailable on Windows until the credential store has Windows permission protection; it reports this explicitly without writing tokens. DeepSeek remains a separate optional configuration, and its existing local configuration file inherits Windows directory permissions. Live capture, online video downloads, provider calls and GPU acceleration require separate real-task validation.

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
