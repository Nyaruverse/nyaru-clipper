# DeepSeek bilingual subtitle implementation checkpoint

Date: 2026-10-14 (Asia/Shanghai). Scope: Japanese-to-simplified-Chinese translation, bilingual subtitle preview/export, and reuse of existing companion task timestamps.

## Completed

- Translation batches use existing httpx and bilingual rendering, bind caches to the source checksum/model/prompt, validate ordered row identities and resume completed batches.
- The GUI adds a session-only password field, translation action, cue progress/errors, original/bilingual preview and full/clip subtitle downloads.
- macOS App 0.1.2 build 3 built, passed strict signature verification, was installed and started its backend. Original-checkout App/ZIP artifacts were updated with old versions preserved; ZIP integrity passed.
- Selected macOS backend tests: 111 passed. Shared web frontend tests: 155 passed; TypeScript/Vite build passed. Independent review approved and separately ran 31 backend and 6 companion UI tests.
- Tests explicitly forbid download, ASR and video encoding during translation and verify unchanged originals/manifests, identical cue timing and zero-based clip offsets.
- SHA256 snapshots of 86 original files across the two completed tasks were taken and rechecked unchanged after installation, including media, subtitles, manifests and ASR caches.
- The installed backend's local GUI shows seven existing tasks, 658 cues in the current task and the Key panel. No Key is configured and no real API calls have run.

## Pending

The user chose to configure the Key later. Real DeepSeek translation and semantic quality remain unaccepted; simulated provider responses are not real translation output. After session Key entry, translate the existing 658-cue and 1448-cue tasks without rerunning media stages. The local evidence script checks all 86 originals, bilingual counts/source text/timings, six clip offsets and output checksums.

The native observation tool failed with a screen-capture error after startup. This checkpoint confirms the installed backend and corresponding local GUI, not native bilingual playback/save acceptance. Real bilingual files do not exist yet. This feature is uncommitted, unpushed and unpublished; other macOS hosts and new billing/login flows were not tested.

See the [user guide](deepseek-bilingual.md). Private local verification evidence is under `.omo/evidence/2026-10-14-deepseek-bilingual/` in the original checkout; do not upload media, original transcripts or secrets.
