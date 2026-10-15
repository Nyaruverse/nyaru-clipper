# Saozi: continuous semantic clips

Saozi divides a video into consecutive clips of about one to two minutes. It reuses the saved DeepSeek key and model to analyze transcript paragraphs. Video, ASR and encoding stay local; transcript text, candidate boundaries and timing information are sent to DeepSeek and consume API credit.

## Use

Select **臊子** under the clipping mode, then choose an input:

- **Replay link**: an HTTP(S) link to a finished video.
- **Local recording**: choose a video file. The task keeps a separate copy and preserves the original.
- **Bilibili live**: a currently live numeric room URL such as `https://live.bilibili.com/12345`. Other live platforms are unsupported.

Choose a language and start. Live recording and recognition run concurrently; published clips can be previewed and downloaded immediately. **停止直播并导出剩余内容** stops capture, then drains the backlog and final tail. Closing the App interrupts processing; **恢复处理** processes saved recording data without reconnecting to the live room automatically.

Normal clips are 60–120 seconds. Short videos and final tails remain intact even below 60 seconds. DeepSeek chooses from locally supplied sentence/topic boundaries. When a long utterance has no suitable boundary, the 120-second limit takes precedence and the result is marked as constrained. Silent intervals use timed cuts with an explicit label. Semantic completeness is not absolute and depends on ASR and model quality.

Results include a topic and cut reasons. Each clip keeps MP4 and zero-based original SRT output, and automatically gains a bilingual SRT (clip-NNN.ja-zh.srt): Japanese source with Chinese translation, or Chinese source with Japanese translation. Available bilingual subtitles are previewed by default. Live tasks publish bilingual files during recording; translation may follow the video, and links appear only after validation. Existing subtitle styles, ASS, burn-in and ArcTime handoff remain available.

## Progress and failures

The first live clip needs about 140 seconds of buffered content plus recognition, API and encoding time. Slow processing retains the recording and reports a backlog; output is not promised within the first 120 seconds. Network failures have bounded reconnect attempts. Separate connection sessions preserve their own tails and expose unrecoverable gaps in the UI.

API timeouts, invalid keys, insufficient balance and malformed responses fail visibly. Recognized transcripts, completed decisions and published clips remain recoverable. Recovery binds the original model and checkpoints; changing the default model does not recut published output. Do not edit manifests or overwrite output files.

Bilingual translation failure does not stop original recording or delete clips. After capture finishes, use the bilingual retry button or CLI resume; completed translation batches are reused. A process exiting between global bilingual publication and checkpoint update preserves files and reports an integrity error for inspection, avoiding overwrite of possible user edits.

## CLI

Save DeepSeek settings using the GUI with the same output root, then run:

```bash
python scripts/local_companion.py run https://example.org/replay --saozi --output-dir data/local-runs
python scripts/local_companion.py run /absolute/video.mp4 --saozi --local --output-dir data/local-runs
python scripts/local_companion.py run https://live.bilibili.com/12345 --saozi --live --output-dir data/local-runs
python scripts/local_companion.py resume data/local-runs/TASK_ID
```

In live CLI mode, Ctrl+C stops capture and drains the tail. Only one service may own the output root. Keep the private configuration, credentials and original recordings out of Git.
