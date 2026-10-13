# macOS app

**Nyaru Clipper.app 0.1.1** includes URL download, offline transcription with
sentence timestamps, range/highlight clipping, progress, preview and export.
Python, yt-dlp, FFmpeg, whisper.cpp and the multilingual small model are bundled.
Runtime use requires no terminal, Homebrew or paid ArcTime service.

0.1.1 handles terminal ASR overruns and contiguous zero-duration text fragments.
Terminal cues are clipped to actual audio bounds; the accepted tail window is at
most 30 seconds, or half the duration for short chunks. Overruns outside that
terminal region or beyond the window remain invalid. Ordinary subtitle parsing
retains strict validation.

## Use

Double-click `~/Applications/Nyaru Clipper.app`. The local archive is
`dist/Nyaru-Clipper-macOS-arm64.zip`.

1. Enter an accessible URL and select a language or automatic detection.
2. Choose explicit ranges or highlights and the maximum clip count.
3. Start processing and follow actual stages; one task runs at a time.
4. Preview video/clips, seek using transcript timestamps and save MP4/SRT pairs
   or full SRT/TXT through the native save panel.

Confirmed overwrites publish only after download finishes; cancellation preserves
the existing file. First launch copies and verifies the bundled model. Persistent
data lives in `~/Library/Application Support/Nyaru Clipper/`: `models/`, `runs/`
and `app.log`. Updating the app keeps models and runs. Do not edit manifests.
CLI history in `data/local-runs/` is not automatically imported.

Closing the window or Cmd-Q stops the helper/tools. Reopen to resume interrupted
runs whose source is downloaded; incomplete downloads require resubmitting the
URL. Resume recognition from the original app installation path with the same
model to avoid an ASR identity mismatch. Site access requirements still apply;
there is no login/cookie configuration in this interface.

## Platform and build

This build targets **Apple Silicon / arm64, macOS 27.0 minimum**, tested on macOS
27.0.1. The minimum follows the bundled native tools. Local ad-hoc signing is
verified; Developer ID signing and notarization are not included.

Development builds require Python 3.11, uv, Corepack, frontend dependencies,
FFmpeg/ffprobe, whisper.cpp and the verified model.

```bash
uv venv --python 3.11 dist/build-venv
uv pip install --python dist/build-venv/bin/python -r desktop/macos/requirements-build.txt
cd web
corepack pnpm install --frozen-lockfile
cd ..
dist/build-venv/bin/python scripts/build_macos_app.py
```

The default model is `~/.cache/nyaru-clipper/models/ggml-small.bin`; override with
`--model /path/to/model`. Move an existing `dist/Nyaru Clipper.app` aside before
rebuilding: the builder preserves it. Dependency licenses and
`Contents/Resources/build-info.json` are included.

See the [acceptance record](macos-app-acceptance-2026-10-13.md).
