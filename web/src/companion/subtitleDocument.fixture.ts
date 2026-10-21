import { defaultStyle } from './subtitleStyle';
import type { SubtitleDocument } from './subtitleDocument';

export const documentFixture = (): SubtitleDocument => ({
  version: 1, revision: 0, source_fingerprint: 'a'.repeat(64), width: 1280, height: 720, duration: 10, fps: 25,
  style: defaultStyle,
  cues: [
    { id: 'cue-000001', start_seconds: 1, end_seconds: 5, text: '你好😀世界', translation: 'こんにちは世界', original_style: null, translation_style: null,
      original_emphasis: [{ start: 2, end: 4, color: '#FF0000', bold: true }], translation_emphasis: [] },
    { id: 'cue-000002', start_seconds: 6, end_seconds: 8, text: '第二句', translation: '二番目', original_style: null, translation_style: null, original_emphasis: [], translation_emphasis: [] },
  ],
});
