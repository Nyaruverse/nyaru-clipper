# ChatGPT subscription acceptance, 2026-10-15

Installed0.1.8 build14 passed signature/install-hash checks, restart/login persistence, current model catalog, native bilingual playback and system saving. Real new local/live processing passed onbuild13; build14 only corrects the active-live translation label and does not change capture, ASR, provider requests or exports.

| Scenario | Observed result | Evidence |
| --- | --- | --- |
| Provider selection | Native DeepSeek Flash/ChatGPT subscription selection; ChatGPT/GPT-6-Luna survives restart | Native action record, `openai-native/local-bilingual-preview.png` |
| Official authorization | System browser opened the app-specific official login; user granted access, JWT verification and plan scope succeeded,7account models returned | `openai-subscription-progress.md` |
| Real semantic call | Public Responses returned a validated JSON cut ending the current topic at73seconds | `openai-response-diagnostic.json`, `openai-real-cut-receipt.md` |
| New local recording | `73fbcd311737`:150.033333seconds,73/77.033333second clips,21/21translations,3pairedSRTs | `openai-online-local.json` |
| Bilibili live | Room545068, `68faca68e130`:181.105seconds,107.705/73.4second clips,40/40translations,3pairedSRTs | `openai-online-live.json` |
| Publication before stop | First bilingual SRT downloadable while recording; observer stopped capture at180.37seconds and the remaining tail completed | Same receipt, early_bilingual |
| Files and timing | Original/paired cue counts and intervals match; clip timings are local; HTTP downloads match task bytes | Both online receipts |
| Native playback | Build13local0to23seconds; finalbuild14live0to7seconds with Chinese/Japanese text | Native screenshot above; openai-native/final-build14-live-preview.png |
| Native system save | Build14saved local/live first paired SRTs through NSSavePanel into project evidence; bytes/SHA256match originals | openai-native-final.json |
| Original protection |56original40c0c9files and113existing35clip-target files retain their hashes | `openai-install-hashes.json` |
| Regression |382related backend tests passed after final status correction;41UI tests and production build passed | Tool receipts, execution ledger |

Evidence is in this repository's `.omo/evidence/`. Shared implementation is `/Users/drm/.codex/worktrees/local-companion-web/nyaru-clipper`; native packaging is `/Users/drm/.codex/worktrees/local-companion-macos/nyaru-clipper`.

The initial real task35b20d192dcc remains as failure evidence: completed response.output was empty while output_item.done held complete JSON. The corrected parser requires a completed terminal event plus validated completed items; cutoffs/failures stay rejected. Captured-fixture tests and actual inference passed. Legacy tasks without provider identity retain Flash; saved/checkpointed identity wins, new defaults affect new tasks, provider caches are isolated, and no fallback or Pro call occurred.

Credentials remain separate, owner-only and atomic, with PKCE/JWT/refresh/revocation regression coverage. No tokens are present in frontend, jobs, exports or evidence. Actual expiry refresh and revocation of the active grant were not exercised. The old Downloads prompt was not visible to the user and the save subsequently failed with Cannot create file; no permission was granted. Finalbuild14saved both local/live paired SRTs through the system save panel into project evidence. Downloads-folder saving remains unaccepted; project-folder saving passed. Translation was sampled, not exhaustively reviewed; recognition of names/game terms remains imperfect. Apple Silicon local acceptance does not establish notarization, public release, Intel/older macOS or Linux GPU acceptance. No commits/pushes; original media/history retained.
