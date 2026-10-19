# Companion Feature Update (2026-10-19)

This update covers the current feature set of the local companion web UI, plus this round's improvements to topic clipping, slicing modes, and subtitle quality.

## Topic clips & summaries

- **Talk-only curation**: DeepSeek reads all subtitles and drops intros/outros, singing/performance, silence, and segments without real conversation, keeping only talk/chat/comment-reading segments. Gaps between segments are allowed; short suspect fragments (<10s) are discarded.
- **Segment length**: 30–600 seconds each; highly related adjacent topics may merge into longer segments.
- **Range & count controls** (optional inputs): analysis start / end time (seconds, `MM:SS`, or `HH:MM:SS`; blank = full video) and max segment count (1–100, default 100). Fill either field alone to start from a point or generate everything up to an end point.
- **Combined video follows selection order** (fix): clips are concatenated in the order you check them, and each segment opens with its selection-order number (01, 02, ...). Card badges show the live selection order.
- **Max segments** raised from 50 to **100**.

## Slicing modes

- New fourth mode **Full video** (alongside ranges / highlights / saozi): generates original + bilingual subtitles for the entire video and **finishes right after transcription**, no clipping.
- **Range mode now transcribes only the selected range** via ASR offset seeking, cutting processing time; downstream clipping and validation are unchanged.

## Subtitle quality

- **Whisper hallucination filter**: repeated template lines over background music (e.g. "1/2 cwm fawr.") are removed via blacklist plus density detection (≥5 normalized repeats with median gap ≤15s); real speech with sparse repeats is kept. Cache version bumped to v2 — existing caches still work, splitting/filtering applies at load time.
- **Line length caps**: full-width ≤20 chars, half-width (ASCII) ≤28 chars, mixed lines judged by weighted width. Overlong Japanese lines are split at punctuation (or by width), with duration divided proportionally; the translation prompt enforces concise Chinese within the same caps.
- Fixes: font picker now lists all system fonts (was truncated); editing and saving a translation no longer fails.
