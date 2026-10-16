import { describe, expect, it } from 'vitest';
import { mergeCues, splitCue, patchCues, resolveStyle, nudgeStyle, cueWarnings, parseDocument, activeDocumentCues, effectiveAnchor, nudgeCueStyle } from './subtitleDocument';
import { documentFixture } from './subtitleDocument.fixture';

describe('subtitle editing document', () => {
  it('keeps imported ASS horizontal margins when nudging an automatic anchor',()=>{
    const base=documentFixture();
    const doc={...base,style:{...base.style,original:{...base.style.original,align:7,position:'top' as const,margin_left:90,margin_right:60}}};
    const anchor=effectiveAnchor(doc,doc.cues[0],'original',false);
    expect(anchor.x).toBe(90*doc.height/1080);
    expect(nudgeCueStyle(doc,doc.cues[0],'original',1,0,false).x).toBeCloseTo(anchor.x+1);
  });
  it('retains the effective top alignment when an automatic cue becomes explicit', () => {
    const doc = { ...documentFixture(), width: 640, height: 360 };
    doc.style = { ...doc.style, original: { ...doc.style.original, position: 'top', align: 2 }, translation: { ...doc.style.translation, position: 'top', align: 2 } };
    expect(effectiveAnchor(doc, doc.cues[0], 'original', true)).toEqual({ x: 320, y: 32 });
    expect(nudgeCueStyle(doc, doc.cues[0], 'original', 1, 0, true)).toMatchObject({ x: 321, y: 32, align: 8 });
  });
  it('retains both centered language anchors when one becomes explicit', () => {
    const doc = { ...documentFixture(), width: 640, height: 360 };
    doc.style = { ...doc.style, original: { ...doc.style.original, align: 5 }, translation: { ...doc.style.translation, align: 5 } };
    const cue = { ...doc.cues[0], translation: 'line1\nline2' };
    expect(effectiveAnchor(doc, cue, 'original', true).y).toBeCloseTo(162.6666667);
    expect(nudgeCueStyle(doc, cue, 'original', 1, 0, true)).toMatchObject({ x: 321, y: 162.67, align: 5 });
    const explicit = { ...cue, original_style: nudgeCueStyle(doc, cue, 'original', 1, 0, true) };
    expect(effectiveAnchor(doc, explicit, 'translation', true).y).toBeCloseTo(190.9333333);
  });
  it('preserves the actual stacked Y when a multiline bilingual cue is nudged horizontally', () => {
    const doc = { ...documentFixture(), width: 640, height: 360 };
    const cue = { ...doc.cues[0], translation: 'line1\nline2' };
    expect(effectiveAnchor(doc, cue, 'original', true).y).toBe(312);
    expect(nudgeCueStyle(doc, cue, 'original', 1, 0, true)).toMatchObject({ x: 321, y: 312 });
    expect(effectiveAnchor(doc, cue, 'original', false).y).toBe(328);
    const translated = { ...cue, translation_style: { ...doc.style.translation, x: 123, y: 200 } };
    expect(effectiveAnchor(doc, translated, 'original', true).y).toBe(312);
  });
  it('uses ASS centiseconds for scene selection including half-up decimal boundaries', () => {
    const doc = documentFixture();
    const cue = { ...doc.cues[0], start_seconds: 1.005, end_seconds: 1.026 };
    expect(activeDocumentCues({ ...doc, cues: [cue] }, 1.007)).toEqual([]);
    expect(activeDocumentCues({ ...doc, cues: [cue] }, 1.01)).toEqual([cue]);
    expect(activeDocumentCues({ ...doc, cues: [cue] }, 1.029)).toEqual([cue]);
    expect(activeDocumentCues({ ...doc, cues: [cue] }, 1.03)).toEqual([]);
  });
  it('rejects malformed API payloads before rendering', () => {
    expect(() => parseDocument({})).toThrow();
    expect(() => parseDocument({ ...documentFixture(), cues: undefined })).toThrow();
    expect(parseDocument(documentFixture())).toEqual(documentFixture());
  });
  it('changes selected cues without mutating originals or neighbours', () => {
    const doc = documentFixture();
    const next = patchCues(doc, ['cue-000001'], cue => ({ ...cue, text: '新内容' }));
    expect(next.cues[0].text).toBe('新内容');
    expect(next.cues[1]).toBe(doc.cues[1]);
    expect(doc.cues[0].text).toBe('你好😀世界');
  });

  it('splits Unicode codepoints and emphasis, preserving absolute source times', () => {
    const next = splitCue(documentFixture(), 'cue-000001', 3.4, 'edit-test', 3);
    expect(next.cues.slice(0, 2).map(c => c.text)).toEqual(['你好😀', '世界']);
    expect(next.cues[0].end_seconds).toBe(3.4);
    expect(next.cues[1].start_seconds).toBe(3.4);
    expect(next.cues[0].original_emphasis).toEqual([{ start: 2, end: 3, color: '#FF0000', bold: true }]);
    expect(next.cues[1].original_emphasis).toEqual([{ start: 0, end: 1, color: '#FF0000', bold: true }]);
  });

  it('merges adjacent cues and offsets emphasis across the newline', () => {
    const doc = documentFixture();
    const next = mergeCues(doc, doc.cues.map(c => c.id));
    expect(next.cues).toHaveLength(1);
    expect(next.cues[0].text).toBe('你好😀世界\n第二句');
    expect(next.cues[0].start_seconds).toBe(1);
    expect(next.cues[0].end_seconds).toBe(8);
    expect(next.cues[0].original_emphasis).toEqual(doc.cues[0].original_emphasis);
  });

  it('rejects a split on the boundary and non-adjacent merge', () => {
    const doc = documentFixture();
    expect(() => splitCue(doc, doc.cues[0].id, 1, 'edit-test')).toThrow();
    const middle = { ...doc.cues[1], id: 'middle' };
    expect(() => mergeCues({ ...doc, cues: [doc.cues[0], middle, doc.cues[1]] }, doc.cues.map(c => c.id))).toThrow();
  });

  it('nudges in actual video pixels independently of display size', () => {
    const doc = documentFixture();
    const style = resolveStyle(doc, doc.cues[0], 'original');
    const moved = nudgeStyle(style, 1, -10, doc.width, doc.height);
    expect(moved.x).toBe(641);
    expect(moved.y).toBeCloseTo(646);
    expect(moved.align).toBe(2);
  });

  it('warns about fast reading, overlaps and out-of-frame anchors', () => {
    const doc = documentFixture();
    const cue = { ...doc.cues[0], text: '很长的字幕'.repeat(30), end_seconds: 7,
      original_style: { ...doc.style.original, x: -3, y: 200 } };
    const warnings = cueWarnings({ ...doc, cues: [cue, doc.cues[1]] }, cue);
    expect(warnings.join(' ')).toMatch(/阅读/);
    expect(warnings.join(' ')).toMatch(/重叠/);
    expect(warnings.join(' ')).toMatch(/画面/);
  });
});
