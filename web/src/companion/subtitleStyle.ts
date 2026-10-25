export interface TextStyle { font: string; size: number; color: string; outline_color: string; outline: number; background_color: string; background_opacity: number; position: 'top' | 'bottom'; margin: number;
  bold?: boolean; italic?: boolean; underline?: boolean; opacity?: number; spacing?: number; line_height?: number;
  align?: number; x?: number | null; y?: number | null; rotation?: number; scale_x?: number; scale_y?: number;
  shadow?: number; shadow_color?: string; padding?: number; max_width?: number; hidden?: boolean;
  margin_left?: number; margin_right?: number;
  outline_layers?: readonly {readonly color: string; readonly width: number}[];
}
export interface SubtitleStyle { version: 1; original: TextStyle; translation: TextStyle }
export interface StyleTemplate { revision?: number; streamer?: string; workflow?: import('./studioModel').StudioWorkflow; id: string; name: string; style: SubtitleStyle; arctime_template_id: string | null; builtin: boolean }
export interface ProjectTemplate { id: string; name: string; sha256: string; size: number }
export interface SubtitleSettings { style: SubtitleStyle; templates: StyleTemplate[]; arctime_templates: ProjectTemplate[]; burn_available: boolean; native_handoff_available: boolean }
export interface CueSegment { start_seconds: number; end_seconds: number; text: string }
const original: TextStyle = { font:'Arial',size:48,color:'#FFFFFF',outline_color:'#000000',outline:2,background_color:'#000000',background_opacity:0,position:'bottom',margin:96 };
export const defaultStyle: SubtitleStyle = {version:1,original,translation:{...original,size:40,color:'#FFFF00',margin:40}};
export const graphemeSegmenter = new Intl.Segmenter('und', { granularity: 'grapheme' });
export function wrapText(text: string, size: number, width: number): string {
  return wrapStyledText(text, {...original, size}, width);
}
export function wrapStyledText(text: string, style: TextStyle, width: number): string {
  const available = Math.max(1, width * (style.max_width ?? 100) / 100 - (style.margin_left ?? 20) - (style.margin_right ?? 20) - 2 * (style.padding ?? 0));
  let used = 0; let result = '';
  for (const { segment: char } of graphemeSegmenter.segment(text.replace(/\r\n?/g,'\n'))) {
    if (char === '\n') { result += char; used = 0; continue; }
    const advance = Array.from(char).reduce((sum, point) => sum + (/\p{M}/u.test(point) ? 0 : Math.max(0, style.size * 1.2 + (style.spacing ?? 0)) * (style.scale_x ?? 100) / 100), 0);
    if (used && used + advance > available) { result += '\n'; used = 0; }
    result += char; used += advance;
  }
  return result;
}
export function activeCue(input: {segments: CueSegment[]; bilingual: CueSegment[]; time: number; offset: number}) {
  const time = input.time + input.offset;
  const index = input.segments.findIndex(cue => cue.start_seconds <= time && time < cue.end_seconds);
  if (index < 0) return null;
  const original = input.segments[index].text;
  const combined = input.bilingual[index]?.text;
  return { original, translation: combined?.startsWith(`${original}\n`) ? combined.slice(original.length + 1) : '' };
}
export function layoutCue(cue: {original: string; translation: string}, style: SubtitleStyle, width: number) {
  const original = {text:wrapStyledText(cue.original,style.original,width),margin:style.original.margin};
  const translation = {text:wrapStyledText(cue.translation,style.translation,width),margin:style.translation.margin};
  const visible = ([['original', original], ['translation', translation]] as const).filter(([key, value]) => value.text && !style[key].hidden);
  const layout = automaticLayout(visible.map(([key, value]) => ({count:value.text.split('\n').length, style:style[key], textWidth:Math.max(...value.text.split('\n').map(line => Array.from(line).filter(char => !/\p{M}/u.test(char)).length * Math.max(0, style[key].size * 1.2 + (style[key].spacing ?? 0)) * (style[key].scale_x ?? 100) / 100))})), width);
  visible.forEach(([key, value], index) => { value.margin = effectiveAlignment(style[key]) >= 7 ? layout.anchors[index] : 1080 - layout.anchors[index]; });
  const fits = layout.fits;
  return { original,translation,fits };
}
export function effectiveAlignment(style: TextStyle): number {
  return style.position === 'top' && (style.align ?? 2) === 2 && style.x == null && style.y == null ? 8 : style.align ?? 2;
}
export function automaticLayout(items: readonly {readonly count: number; readonly style: TextStyle; readonly textWidth?: number}[], width = 1920) {
  const heights = items.map(({count, style}) => ((count - 1) * (style.line_height ?? 1.2) + Math.max(1.2, style.line_height ?? 1.2)) * style.size * (style.scale_y ?? 100) / 100);
  const rows = items.map(({style}) => Math.floor((effectiveAlignment(style) - 1) / 3));
  const margins = items.map(({style}) => style.margin), centers = items.map(() => 540);
  if (items.length === 2) items.forEach(({style}, index) => {
    const other = 1 - index;
    if (style.x != null || style.y != null) return;
    if (rows[index] === 1 && rows[other] === 1) centers[index] += (index === 0 ? -1 : 1) * (heights[other] + 8) / 2;
    else if (rows[index] === rows[other] && ((rows[index] === 0 && index === 0) || (rows[index] === 2 && index === 1))) margins[index] = Math.max(margins[index], margins[other] + heights[other] + 8);
  });
  const anchors = items.map((_, i) => rows[i] === 2 ? margins[i] : rows[i] === 1 ? centers[i] : 1080 - margins[i]);
  const fits = items.every(({style, textWidth = 0}, i) => {
    if (style.x != null || style.y != null || style.hidden) return true;
    const border = Math.max(style.outline, ...(style.outline_layers ?? []).map(layer => layer.width));
    const extent = heights[i] + border + (style.padding ?? 0) + (style.shadow ?? 0);
    const column = (effectiveAlignment(style) - 1) % 3;
    const x = column === 0 ? style.margin_left ?? 20 : column === 1 ? (width + (style.margin_left ?? 20) - (style.margin_right ?? 20)) / 2 : width - (style.margin_right ?? 20);
    const left = -textWidth * column / 2;
    const edge = border + (style.padding ?? 0) + (style.shadow ?? 0);
    if ((style.rotation ?? 0) % 360) {
      const top = -heights[i] * (2 - rows[i]) / 2, angle = (style.rotation ?? 0) * Math.PI / 180;
      return [left - edge, left + textWidth + edge].every(dx => [top - edge, top + heights[i] + edge].every(dy => {
        const px = x + dx * Math.cos(angle) + dy * Math.sin(angle), py = anchors[i] - dx * Math.sin(angle) + dy * Math.cos(angle);
        return px >= 0 && px <= width && py >= 20 && py <= 1060;
      }));
    }
    if (x + left - edge < 0 || x + left + textWidth + edge > width) return false;
    return rows[i] === 2 ? anchors[i] + extent <= 1060 : rows[i] === 0 ? anchors[i] - extent >= 20 : anchors[i] - extent / 2 >= 20 && anchors[i] + extent / 2 <= 1060;
  });
  return {anchors, fits};
}
export async function subtitleApi<T>(path: string, body?: object | File): Promise<T> {
  const response = await fetch(`/companion-api${path}`, body === undefined ? undefined : {method:'POST',headers:{'Content-Type':body instanceof File ? 'application/octet-stream' : 'application/json'},body:body instanceof File ? body : JSON.stringify(body)});
  const result = await response.json();
  if (!response.ok) throw new Error(typeof result.detail === 'string' ? result.detail : '字幕操作失败，请检查输入或本地服务');
  return result;
}
