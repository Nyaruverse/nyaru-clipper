# Local video companion

The standalone browser GUI and CLI download one video URL, generate original-language text and sentence timestamps locally, and export explicit ranges or automatically ranked highlights. macOS/Linux are supported first. They do not launch ArcTime or call its cloud services, translation, or DeepSeek proofreading. The SRT can be opened in a subtitle editor for review.

## Browser GUI

For the double-click package with bundled tools and model, see [macOS app](macos-app.md).

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

## Native Windows (PowerShell, no Docker)

This path runs the standalone Companion on an NVIDIA GPU using CUDA-enabled whisper.cpp. It does not start the separate GPU workstation API/worker stack. Install the NVIDIA driver, Python 3.11 (or let uv obtain it), uv, Node.js 20+ and Corepack first. See the [Windows deployment commands](deployment-windows.zh-CN.md). From the repository root:

```powershell
uv venv --python 3.11 .venv
uv pip install --python .venv/Scripts/python.exe 'pydantic-settings>=2.6,<3' 'sqlmodel>=0.0.22,<1' 'anyio>=4,<5' 'httpx>=0.28,<1' 'PyJWT[crypto]>=2.10,<3' yt-dlp 'fastapi>=0.115,<1' 'uvicorn>=0.32,<1'
Set-Location web
corepack pnpm install --frozen-lockfile
corepack pnpm build
Set-Location ..
```

Install Windows FFmpeg/FFprobe from a [build linked by FFmpeg](https://ffmpeg.org/download.html), and the `whisper-cublas-12.4.0-bin-x64.zip` package from the [whisper.cpp v1.9.2 release](https://github.com/ggml-org/whisper.cpp/releases/tag/v1.9.2). Put the executables on PATH, or copy them into the ignored repository `.bin/` directory. Keep all matching DLLs, including the CUDA backend and runtime libraries, beside `whisper-cli.exe`; copying just the executable is insufficient.

Download the multilingual model once:

```powershell
New-Item -ItemType Directory -Force data/model-cache/whispercpp | Out-Null
Invoke-WebRequest 'https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-small.bin' -OutFile data/model-cache/whispercpp/ggml-small.bin
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/dev_companion.ps1 -Command doctor
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/dev_companion.ps1
```

Open <http://127.0.0.1:8787> and keep the terminal running; Ctrl+C stops the service. The launcher enables UTF-8, adds the virtual environment and `.bin/` to the process PATH, and uses repository-relative defaults even when launched from another directory. `-Python`, `-Model`, `-OutputDir`, `-Port` and `-Threads` override those defaults.

Local-file recognition and explicit-range export have been verified on Windows with the multilingual `small` model and the upstream JFK audio sample. CUDA inference and the application's unchanged ASR adapter have also been verified on an RTX 4070 Laptop GPU. ChatGPT sign-in is unavailable on Windows until the credential store has Windows permission protection; it reports this explicitly without writing tokens. DeepSeek remains a separate optional configuration, and its existing local configuration file inherits Windows directory permissions. Live capture, online video downloads and provider calls require separate real-task validation.

These instructions retain the standalone Companion workflow. Unified migration, independent recovery and Windows AMF qualification remain pending.

## Artifacts and recovery

Every job gets `data/local-runs/<id>/` containing `source.mp4`, full `subtitles.srt`, `transcript.txt`, structured `transcript.json`, MP4/SRT clip pairs, persistent `clip-*.log` export diagnostics, `job.json`, and `asr/chunk-*.json`/logs. The GUI adds `gui.json` for messages/errors without persisting the source URL. Clip subtitle timestamps start at zero. Subtitles are sidecars, not burned into video in this iteration.

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
