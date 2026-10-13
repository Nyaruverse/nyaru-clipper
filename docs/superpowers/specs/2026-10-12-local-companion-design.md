# Local video companion

The user approved local processing on 2026-10-12. This supersedes the cloud transcription route in `2026-10-12-arctime-companion-design.md`.

## Workflow and scope

A standalone Python CLI accepts one HTTP(S) video URL, downloads it using yt-dlp, transcribes locally using whisper.cpp, and exports timed SRT, plain text, structured JSON and MP4/SRT clip pairs. Repeatable explicit ranges and automatic highlight selection are mutually exclusive. Highlights reuse the current subtitle-density, punctuation, laughter and excitement scoring; this is heuristic ranking, not semantic understanding. No qualifying highlights produces zero clips and a visible explanation.

The first release runs on macOS/Linux, independently of ArcTime, the backend database, translation and proofreading services. No ArcTime desktop or cloud adapter is imported by the local entrypoint. Model setup is separate from job execution: inference never downloads models or calls a cloud API. The existing desktop adapter remains dormant historical work.

## Local speech recognition

Use an installed whisper.cpp CLI and a configured local multilingual GGML model. FFmpeg extracts mono 16 kHz PCM audio in five-minute chunks. Each chunk is transcribed with original-language recognition and sentence timestamps, then rebased to the source timeline. Word-level alignment and speaker separation are outside this iteration. Engine failures, missing models, empty speech and invalid timestamps must not publish a successful transcript.

## Persistence and recovery

New jobs use version 2 manifests and private run directories. Record source and model fingerprints, language, engine and completed output identities. Do not store the URL or downloader output. Resume validates the source, cached chunks and published artifacts before reuse. A per-job lock prevents concurrent writers. Safe local ASR retries have no chargeable submission boundary. Reject old cloud jobs without launching ArcTime.

Export into temporary files and publish without overwriting final files. Recover published clip pairs after an interrupted manifest update by comparing the expected clipped subtitles and video duration; preserve completed clips. Leave failures and run directories available for inspection.

## Acceptance

Regression tests cover local-only orchestration, source/model changes, chunk rebasing, failed/empty ASR, range validation, ranking, lock contention, resumable partial exports and CLI errors. Manual acceptance uses a video served over local HTTP and real yt-dlp, whisper.cpp and FFmpeg. Both range and high-confidence highlight selection must produce actual playable clips with rebased SRT. Provider-specific public websites remain dependent on yt-dlp support and access permissions.
