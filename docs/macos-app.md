# macOS app

**Nyaru Clipper.app 0.1.8 build14** includes URL download, offline transcription with
sentence timestamps, range/highlight clipping, progress, preview and export.
It also adds [custom subtitle styles, both template types, ASS, burned clips and ArcTime handoff](subtitle-styles.md).
Python, yt-dlp, libass-capable FFmpeg, whisper.cpp and the multilingual small model are bundled.
Runtime use requires no terminal, Homebrew or paid ArcTime service.

The installed build also includes [Saozi](saozi.md) for replay/local recordings and
Bilibili live slicing, automatic bilingual subtitles and the
[ChatGPT subscription provider](openai-subscription.md). Select DeepSeek Flash or
ChatGPT in AI provider settings; DeepSeek Pro is disabled. Browser verification
and its network-retry boundary are recorded in the [Web acceptance](web-app-acceptance-2026-10-15.md).

DeepSeek Japanese-to-Chinese translation reuses completed tasks and their existing
timelines, with bilingual full/clip SRT files, progress, preview and export. The
API Key is saved through the GUI to `runs/config.json` and loaded on restart; translation requires network/API credit.
See the [bilingual subtitle guide](deepseek-bilingual.md).

0.1.1 handles terminal ASR overruns and contiguous zero-duration text fragments.
Terminal cues are clipped to actual audio bounds; the accepted tail window is at
most 30 seconds, or half the duration for short chunks. Overruns outside that
terminal region or beyond the window remain invalid. Ordinary subtitle parsing
retains strict validation.

## Use

Current installation: verified0.1.8 build14 at `~/Applications/Nyaru Clipper.app`;
see the [subscription acceptance](openai-subscription-acceptance-2026-10-15.md).
The following0.1.5 installation receipt is historical:
On15October2026, verified0.1.5 build9 was installed and launched at `~/Applications/Nyaru Clipper.app`.
Previous0.1.4 build5 is preserved at `~/Library/Application Support/Nyaru Clipper/app-backups/2026-10-15-0.1.4-build5/Nyaru Clipper.app`; task data and models remain intact.
All1498 copied file SHA256 hashes match the verified build, and strict signature verification passed. The running app loads seven historical tasks, three style templates and one ArcTime template.
The archive remains `dist/Nyaru-Clipper-0.1.5-build9-macOS-arm64.zip`. See the [feature verification record](subtitle-styles-acceptance-2026-10-14.md).

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
dist/build-venv/bin/python scripts/build_macos_app.py --output-dir dist/new-build
```

FFmpeg defaults to Homebrew `ffmpeg@7`; SDL3 is explicitly bundled when SDL2 compatibility loads it dynamically. Both host and frozen subtitle filters are checked; an unrunnable frozen tool fails the build.

The default model is `~/.cache/nyaru-clipper/models/ggml-small.bin`; override with
`--model /path/to/model`. Move an existing `dist/Nyaru Clipper.app` aside before
rebuilding: the builder preserves it. Dependency licenses and
`Contents/Resources/build-info.json` are included.

See the [acceptance record](macos-app-acceptance-2026-10-13.md).
