# DeepSeek Japanese-to-Chinese companion integration

The user authorized DeepSeek translation and reuse of existing downloads/timestamps. Implement in the shared companion worktree and propagate only these changes to the macOS worktree. No download, ASR, MP4 encoding, or change to existing job manifests is needed for translation.

## Design

Use the existing httpx dependency and bilingual SRT renderer. A separate translation module calls the official HTTPS chat-completions endpoint using deepseek-flash, non-thinking JSON output. Batch source text with stable numeric IDs; accept exactly one nonempty translation per input ID. Use original cue timings unchanged. Save validated batches in a separate translation.json checkpoint bound to the source subtitle checksum, model and prompt version. Publish subtitles.ja-zh.srt plus clip-NNN.ja-zh.srt; preserve all original artifacts and job.json. Translation errors remain separate from completed video processing, and retries reuse verified batches.

Add a password field and session-only API Key setting to the existing GUI. Never persist or return the key or raw provider errors. Completed tasks expose a Generate bilingual subtitles button, translation progress, original/bilingual preview selector and download links. New tasks can use the same button after ASR completes. No automatic charge for creating a task.

## Execution and acceptance

- [ ] Write provider/checkpoint tests: JSON validation, missing/reordered/empty rows, truncated output, safe errors, restart recovery, corrupted cache/output rejection, unchanged originals/timestamps and clip offsets. Observe failing tests before implementation.
- [ ] Implement backend module plus session configuration and translation endpoints; test single active job, completed base task on translation failure and managed-file allowlist.
- [ ] Write failing GUI test for password entry, translation-only POST, progress, preview and export; implement using existing controls and query polling.
- [ ] Run selected companion backend tests, frontend tests and TypeScript/build. Review the diff independently.
- [ ] Build/install macOS 0.1.2 build 3, preserve old bundle. Verify the real password-entry surface and wait for user key entry. Run translation on completed task 40c0c9a8e93e and then 7fe886d15999 using its existing timing. Compare original file hashes and ASR cache hashes before/after; validate every translated cue and clip offset. Never replace real-provider acceptance with fake translations.
- [ ] Deliver bilingual files and paired usage documentation. Record verified progress, pending real-provider checks and limits accurately. No commit/push or release is implied.
