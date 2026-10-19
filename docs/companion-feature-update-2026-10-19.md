# Companion Feature Update (2026-10-19)

Full overview of the local companion web UI features, plus this round's improvements to topic clipping, slicing modes, and subtitle quality.

## Subtitle styling

Visual subtitle-style editor for burned-in output. Changes reflect in the video preview immediately (600ms debounced auto-save).

- Independent source / translation styles: font (full system font list), size, text color, background color, background opacity, multi-layer outline, position, and alignment.
- Font picker lists all system fonts (previously truncated); supports pinning commonly used fonts.
- Style templates: save current settings as a template, apply or delete templates; live streams can choose a template to apply automatically.
- Renders via ASS styling on video burn/clip export.

## Glossary

Unifies translations of names, titles, and proper nouns so they stay consistent across the video.

- Manage terms: add, edit, delete, search (up to 500 terms).
- Bulk import TXT: one line per entry as `# original=translation`, deduplicated automatically.
- Candidate collection: after translation, the LLM reviews the subtitles and suggests names/titles that appear but are not in the glossary; accept or ignore each candidate (up to 100).

## Shapes

Overlay rectangles on the video frame for decoration or censoring; rendered together with video/clip exports.

- Up to 20 rectangles with configurable corner radius.
- Position (X/Y %), size (W/H %), and radius via sliders.
- Fill color + opacity; outline color + thickness (0 = no outline).
- Live preview updates instantly (250ms debounced auto-save).

## Topic clips & summaries

- **Talk-only curation**: DeepSeek reads all subtitles and drops intros/outros, singing/performance, silence, and segments without real conversation, keeping only talk/chat/comment-reading segments. Gaps between segments are allowed; short suspect fragments (<10s) are discarded.
- **Segment length**: 30–600 seconds each; highly related adjacent topics may merge into longer segments.
- **Range & count controls** (optional): analysis start / end time (seconds, `MM:SS`, or `HH:MM:SS`; blank = full video) and max segment count (1–100, default 100). Fill either field alone to start from a point or generate everything up to an end point.
- **Combined video follows selection order**: clips are concatenated in the order you check them, and each segment opens with its selection-order number (01, 02, ...). Card badges show the live selection order.
- **Max segments** raised from 50 to **100**.

## Slicing modes

- New fourth mode **Full video** (alongside ranges / highlights / saozi): generates original + bilingual subtitles for the entire video and **finishes right after transcription**, no clipping.
- **Range mode now transcribes only the selected range** via ASR offset seeking, cutting processing time.

## Subtitle quality

- **Whisper hallucination filter**: repeated template lines over background music (e.g. "1/2 cwm fawr.") are removed via blacklist plus density detection (≥5 normalized repeats with median gap ≤15s); real speech with sparse repeats is kept. Cache version bumped to v2.
- **Line length caps**: full-width ≤20 chars, half-width (ASCII) ≤28 chars, mixed lines judged by weighted width. Overlong Japanese lines are split at punctuation (or by width), with duration divided proportionally; the translation prompt enforces concise Chinese within the same caps.
- Fixes: font picker now lists all system fonts; editing and saving a translation no longer fails; task directory resolving unified to eliminate sporadic 500 errors.

## Scope

- **New tasks** automatically get all improvements.
- **Existing tasks**: to apply hallucination filtering and line splitting, re-transcribe (cached, fast) and re-translate; topic clips can be regenerated with new parameters at any time.
