# macOS local companion

Approved scope: package the current downloader, local transcription/timestamps,
manual or highlight clips, progress, preview and export. Reuse the existing React
interface in an AppKit/WKWebView window. A frozen Python helper owns a private
ephemeral loopback service; closing the app terminates its process group. Bundle
yt-dlp, FFmpeg/ffprobe, whisper.cpp, native dependency closure and the multilingual
small model. No runtime terminal, Homebrew, Python installation or paid ArcTime API.

Keep models and runs under `~/Library/Application Support/Nyaru Clipper`, outside
the application. Copy the bundled model atomically on first launch; never overwrite
an existing model or run. Export links open a native save panel. Preserve the
standalone CLI and localhost GUI. Build for arm64, ad-hoc sign locally and declare
the actual minimum macOS version of bundled native tools (currently 27.0).

Acceptance: relocate the app, restrict its PATH, run real URL/range and highlight
jobs, observe native progress and video preview, save an exported file, reopen
history and check that quitting leaves no helper/tool processes. Intel, older
macOS and Developer ID/notarized distribution are outside this first build.

Platform references: [WKWebView](https://developer.apple.com/documentation/webkit/wkwebview),
[WKDownloadDelegate](https://developer.apple.com/documentation/webkit/wkdownloaddelegate),
[PyInstaller macOS notes](https://pyinstaller.org/en/stable/feature-notes.html).
