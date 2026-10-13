# macOS App failed-task recovery

2026-10-14, Asia/Shanghai. Task `7fe886d15999` completed through the installed native App: 4878.27225 seconds of video, 17 ASR chunks, 1448 cues and four MP4/SRT highlight pairs. The interface showed completion; clip 1's native player showed 10 seconds elapsed out of 48 seconds.

Chunk 9 ended with a 299–301-second cue in a 300-second chunk, exceeding the previous 0.25-second allowance. The fix admits at most two seconds and clips the end to the actual boundary, retaining rejection of gross overruns. The first retry reused eight chunks and saved chunks 9–13, then chunk 14 failed on a 58.760–58.760-second fragment. Local ASR parsing now merges its text into the contiguous preceding cue, retaining all text and existing intervals. Default parsing remains strict; isolated zero duration, reversed timing and blank text still fail. A second native Resume reused 13 chunks and completed all exports.

Source clip intervals are 498–546, 584–630, 898–945 and 1172.92–1221.28 seconds. Transcript and clip checksums match the manifest; bundled ffprobe verified all four durations. SHA-256 comparisons preserved 58 files: the source, the first eight cache chunks and files from earlier tasks.

94 selected backend tests passed; independent code review approved the fix. An existing Starlette/httpx deprecation warning remains. Both independent worktrees passed 48 subtitle/ASR tests each. Interface build, Python freeze, Swift compilation, strict signature verification and ZIP integrity checks passed.

Changes affect `backend/app/arctime/local_asr.py`, `media.py` and the two related test files. The original checkout and both independent worktrees contain corresponding uncommitted changes; no commit or push was made. The installed App is `/Users/drm/Applications/Nyaru Clipper.app`. Updated build/ZIP are in the original checkout's `dist/`; previous packages and installations remain in `dist/macos-build/`. The version field remains 0.1.0. Earlier artifacts in the independent worktrees were not rebuilt.

Results are in `~/Library/Application Support/Nyaru Clipper/runs/7fe886d15999/`. Both failed logs, pre-repair hashes, recovery verification script and result are in original-checkout `.omo/evidence/2026-10-14-asr-boundary/`; review is in `.omo/evidence/asr-boundary-code-review.md`.

This establishes the real long-video technical pipeline. Japanese recognition, synchronization and highlight quality were not manually reviewed. Other machines/macOS versions were not tested.
