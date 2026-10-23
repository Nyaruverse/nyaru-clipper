# Issue #1 recurrence repair and downloaded-video retest

2026-10-14, Asia/Shanghai. Failed task `40c0c9a8e93e` completed in the native App using its existing downloaded source, without downloading again.

The 3275.299-second video used automatic language detection and a maximum of 30 highlights. Chunk 4 ended with 297.960–302.040 seconds in a 300-second chunk, exceeding the earlier two-second cap and demonstrating that the first repair was incomplete.

The replacement validates a terminal window of `min(30 seconds, chunk length / 2)`. An overrun is accepted only if its start is in that terminal region and its end is within one window after the audio boundary; accepted ends are clipped. Nonterminal and excessive overruns remain errors, while cache validation requires positive cues strictly within actual audio bounds. The installed whisper.cpp 1.9.5 defines [WHISPER_CHUNK_SIZE](https://github.com/ggml-org/whisper.cpp/blob/v1.9.5/include/whisper.h) as 30; the half-length short-chunk guard is this project's conservative policy, not a guarantee covering every model anomaly. Existing contiguous zero-duration merging and strict ordinary subtitle parsing remain active.

Three new regression cases failed before the fix. Web passed 95 selected tests and macOS passed 99; independent review found no blockers. One existing Starlette/httpx deprecation warning remains.

The macOS worktree completed interface build, Python freeze, Swift compilation and signing. Installed App is **0.1.1, build 2**. Original-checkout build/ZIP were refreshed; strict signatures and ZIP integrity passed, and older packages remain preserved. Shared source changes exist in the web/macOS worktrees and original checkout, without commit/push or public release.

Recovery reused the first three chunks and produced **11 chunks, 658 cues and two MP4/SRT pairs**. Source intervals are 1335–1383 and 1423.7–1471.1 seconds, durations 48 and 47.4 seconds. Thirty is an upper limit; two candidates met the scoring threshold. Native completion was visible, and clip 2 showed playback at 23 seconds of approximately 47 seconds with recognized subtitles.

Positive/global subtitle bounds, transcript/export manifest hashes and bundled ffprobe durations passed. Pre/post hashes preserved **109 files**, including the source, first three cached chunks and earlier tasks. Failed logs, snapshot, verifier, result and review are in original-checkout `.omo/evidence/2026-10-14-issue1-recurrence/`.

Recognition accuracy, synchronization and highlight quality were not manually reviewed; other hosts/macOS versions remain untested. The separate historical failed-download task was unchanged. This establishes technical recovery of the currently requested downloaded-video task.
