import { expect, it } from 'vitest';
import { defaultStyle, layoutCue, activeCue, wrapText } from './subtitleStyle';
import samples from '../../../backend/tests/fixtures/grapheme-wrap.json';

it.each([{width:1920, align:1, margin_left:2000}, {width:540, scale_x:400}, {width:180}])('rejects automatic horizontal overflow: %j', ({width, ...values}) => {
  const style = {...defaultStyle, original:{...defaultStyle.original, size:200, ...values}};
  expect(layoutCue({original:'W', translation:''},style,width).fits).toBe(false);
  expect(layoutCue({original:'W', translation:''},{...style,original:{...style.original,x:40}},width).fits).toBe(true);
});

it.each(samples)('wraps whole graphemes: $text', ({ text, lines }) => {
  expect(wrapText(text, 20, 64).split('\n')).toEqual(lines);
  expect(wrapText(text, 20, 41).split('\n')).toEqual(lines);
});
it('wraps Unicode without dropping spaces or combining marks', () => {
  expect(wrapText('ab c\néf', 10, 64)).toBe('ab\n c\néf');
});
it('rebases clip time, excludes end, and preserves multiline originals', () => {
  const segments = [{start_seconds: 10, end_seconds: 13, text: 'a\nb'}];
  const bilingual = [{...segments[0], text:'a\nb\n译文'}];
  expect(activeCue({segments,bilingual,time:1,offset:10})).toEqual({original:'a\nb',translation:'译文'});
  expect(activeCue({segments,bilingual,time:3,offset:10})).toBeNull();
});
it('stacks bilingual lines and warns when canvas cannot fit', () => {
  expect(layoutCue({original:'a',translation:'b\nc'}, defaultStyle,1920).original.margin).toBe(144);
  expect(layoutCue({original:'a',translation:''},{...defaultStyle,original:{...defaultStyle.original,margin:1050}},1920).fits).toBe(false);
});
it('counts advanced line height and excludes hidden text from automatic fit', () => {
  const cue = {original: 'line\n'.repeat(7) + 'line', translation: ''};
  expect(layoutCue(cue, {...defaultStyle, original: {...defaultStyle.original, size:64, line_height:3}}, 1920).fits).toBe(false);
  expect(layoutCue(cue, {...defaultStyle, original: {...defaultStyle.original, size:120, hidden:true}}, 1920).fits).toBe(true);
});
it('reserves full glyph height at tight spacing and checks rotated bounds', () => {
  expect(layoutCue({original:'A', translation:''}, {...defaultStyle, original:{...defaultStyle.original, size:200, line_height:.5, margin:850}},1920).fits).toBe(false);
  const style = {...defaultStyle, original:{...defaultStyle.original, size:120, align:5, rotation:90}};
  expect(layoutCue({original:'ABCDEFGHIJKLM', translation:''},style,1920).fits).toBe(false);
  expect(layoutCue({original:'AB', translation:''},style,1920).fits).toBe(true);
});
