import { expect, it } from 'vitest';
import { defaultStyle, layoutCue, activeCue, wrapText } from './subtitleStyle';
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
