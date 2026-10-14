# Subtitle feature delivery and verification

2026-10-14 Asia/Shanghai. Nyaru Clipper 0.1.5, build 9.

Build directory: `/Users/drm/.codex/worktrees/local-companion-macos/nyaru-clipper`. Distribution and native evidence paths below are relative to that directory.

Custom styles, style JSON and native ATPJ templates, ASS export, burned clips and editable ArcTime ZIP handoff are implemented. Selected automated checks and the workflows below passed. The [15October native-preview follow-up](arctime-native-preview-2026-10-15.md) also passes bilingual/style preview; no lossless visual roundtrip or all-platform acceptance is claimed.

Deliverables are `dist/subtitle-style-0.1.5-upload-verified/Nyaru Clipper.app` and `dist/Nyaru-Clipper-0.1.5-build9-macOS-arm64.zip`. Previous builds/installation/data remain intact. See the [usage guide](subtitle-styles.md). Shared source is in the local-companion-web checkout and synchronized to this macOS checkout; feature commits were pushed to the browser/App development branches on15October2026; primary/master remain unmerged.

## Observed checks

- Selected backend suite: 187 passed; after final package-instruction edits, 16 API cases passed. Final frontend: 22 passed and TypeScript/Vite build passed. These are bounded suites, not whole-repository coverage.
- Real browser style/opacity editing, text-sized backgrounds, source/clip switching, bilingual seeking and wrapper fullscreen/exit were exercised. Captured 390/1440/1920 layouts have no horizontal overflow. Existing light presentation is retained, including under dark system preference; a dark theme was not added.
- Actual native ASS/MP4/ZIP buttons and Save sheets worked. Shared build 8 logic exported the edited size64/opacity0.4 style, a 48.033-second burned bilingual clip, actual-resolution 1280×720 ASS and a checksum-verified ZIP. Build 9 changes only native open-panel wiring; shared backend/frontend bytes match.
- Build 9 native Open panel cancellation, JSON import, native ATPJ registration, selection and saved association worked. App-generated ZIP contains byte-identical native template; its API download also matches. Stored templates load through a new store object.
- The 17 original user-task files retained SHA256 hashes. No recognition, translation-provider call or key edit occurred.
- ArcTime Pro 4.5 imported synthetic media and nine ASS events; text and timing were edited and saved to ATPJ. A second fresh project imported ten matching native style definitions without old subtitle blocks.
- Initial ArcTime roundtrip exposed reference-canvas positions leaving the frame. Actual-resolution ASS conversion fixed it: saved 640×360 output retains nine events/text/times with in-bounds anchors. Real libass frames at 1/3/5.5 seconds show white Japanese/green Chinese, background, multiline and literal special characters.
- Missing WKWebView open-panel wiring was repaired and independently typechecked. Missing dynamically loaded SDL3 was included; the packager now checks frozen FFmpeg's libass filters. Strict ad-hoc signature verification passed.

## Limits and evidence

The14October black captures remain historical evidence. On15October, ArcTime's independent mpv window and actual display passed native playback, bilingual multiline/style preview and timeline seeking. Java-only window capture omits the player and shows a black placeholder. QA capture was corrected; the earlier full-region black symptom did not reproduce, and player/system settings were not changed. ArcTime rounds font sizes, adds fades and changes layers; same-name project styles can overwrite converted sizes. UI/ZIP/docs advise importing project styles before ASS and inspecting target resolution/groups/layout. Opaque ATPJ bytes can retain old media paths and user identifiers.

This is an Apple Silicon/macOS27+ local ad-hoc build. Intel, Linux packages, clean-machine behavior, all fonts and speaker playback were not checked. No Developer ID signing, notarization or public binary release occurred. Source commits were pushed on15October2026.

Mac evidence: `.omo/evidence/final-native-runtime-verification.json`, `final-native-upload-verification.json`, `final-package-verification.json`, `native-saves/final-burned-frame.png`, `subtitle-native-upload-review.md`. Browser checkout evidence: `.omo/evidence/subtitle-final-review.md` (APPROVE, no blockers), interrupted red/green logs, ArcTime native report/matrix, template-package verification and responsive captures. Synthetic media/native templates remain private local evidence, not public source or release attachments.
