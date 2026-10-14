# Real DeepSeek translation acceptance with existing subtitles

Date: 2026-10-14 (Asia/Shanghai). The user configured the Key in the App and authorized bilingual translation of existing subtitles/timestamps in 40c0c9 and 7fe886. Installed App: 0.1.4 build 5; selected model: `deepseek-flash`.

| Task | Full bilingual cues | Clip bilingual SRTs | Status |
| --- | ---: | ---: | --- |
| 40c0c9a8e93e | 658 | 2 | completed, no error |
| 7fe886d15999 | 1448 | 4 | completed, no error |

Sequential real API processing produced 2106 translations in 54 validated batches. The first task was started through the installed backend translation endpoint; the second through the native App button. No media download, recognition or video encoding was repeated.

## Verification

- Every full cue retains Japanese source text, a nonempty Chinese translation and exactly the original start/end timestamps.
- All six clip subtitle files match recalculated original selections with zero-based timing. All eight outputs match their manifest SHA256 checksums.
- All 86 original files match the preexisting snapshot before and after translation, including media, original subtitles, manifests and ASR caches.
- All eight SRT HTTP downloads match output checksums and all eight VTT previews return successfully. Translation checkpoints remain inaccessible through downloads.
- Native App completion counters showed 658/658 and 1448/1448. Full-video and clip playback displayed Japanese/Chinese captions with bilingual mode selected.
- Native save-panel exports of the first full SRT (104230 bytes) and second task clip 1 SRT (1524 bytes) match task outputs by SHA256.

Outputs are under `~/Library/Application Support/Nyaru Clipper/runs/<task ID>/subtitles.ja-zh.srt` and `clip-NNN.ja-zh.srt`, available through App preview/export. Local receipts, original hashes, native exports and UI evidence remain in `.omo/evidence/2026-10-14-deepseek-bilingual/`; do not upload media, subtitles, configuration or credentials.

## Quality boundary

Twenty-four cues were sampled across beginnings, middles, endings and the six clip neighborhoods. Most sampled translations correspond to the text; existing recognition errors, ambiguous phrases and names can produce awkward or inferred translations. For example, the first task's `プライベントメッセージ` became a birthday-message interpretation; its meaning requires checking the original audio. Technical/timing acceptance does not establish sentence-by-sentence proofreading of all 2106 cues. Japanese source text and burned-in source subtitles were not edited. Speaker output, other hosts and real V4 Pro translation remain untested.

No product code, build, installation, commit or push changed in this run. Earlier pending-Key/provider statements remain historical snapshots; this record establishes the current two-task technical acceptance.
