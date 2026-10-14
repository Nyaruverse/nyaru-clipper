export interface TextStyle { font: string; size: number; color: string; outline_color: string; outline: number; background_color: string; background_opacity: number; position: 'top' | 'bottom'; margin: number }
export interface SubtitleStyle { version: 1; original: TextStyle; translation: TextStyle }
export interface StyleTemplate { id: string; name: string; style: SubtitleStyle; arctime_template_id: string | null; builtin: boolean }
export interface ProjectTemplate { id: string; name: string; sha256: string; size: number }
export interface SubtitleSettings { style: SubtitleStyle; templates: StyleTemplate[]; arctime_templates: ProjectTemplate[]; burn_available: boolean; native_handoff_available: boolean }
export interface CueSegment { start_seconds: number; end_seconds: number; text: string }
const original: TextStyle = { font:'Arial',size:48,color:'#FFFFFF',outline_color:'#000000',outline:2,background_color:'#000000',background_opacity:0,position:'bottom',margin:96 };
export const defaultStyle: SubtitleStyle = {version:1,original,translation:{...original,size:40,color:'#FFFF00',margin:40}};
export function wrapText(text: string, size: number, width: number): string {
  let used = 0; let result = '';
  for (const char of text.replace(/\r\n?/g,'\n')) {
    if (char === '\n') { result += char; used = 0; continue; }
    const advance = /\p{M}/u.test(char) ? 0 : size * 1.2;
    if (used && used + advance > width - 40) { result += '\n'; used = 0; }
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
  const original = {text:wrapText(cue.original,style.original.size,width),margin:style.original.margin};
  const translation = {text:wrapText(cue.translation,style.translation.size,width),margin:style.translation.margin};
  if (translation.text && style.original.position === style.translation.position) {
    if (style.original.position === 'bottom') original.margin = Math.max(original.margin,translation.margin + translation.text.split('\n').length * style.translation.size * 1.2 + 8);
    else translation.margin = Math.max(translation.margin,original.margin + original.text.split('\n').length * style.original.size * 1.2 + 8);
  }
  const fits = ([['original',original],['translation',translation]] as const).every(([key, value]) => !value.text || value.margin + value.text.split('\n').length * style[key].size * 1.2 + style[key].outline <= 1060);
  return { original,translation,fits };
}
export async function subtitleApi<T>(path: string, body?: object | File): Promise<T> {
  const response = await fetch(`/companion-api${path}`, body === undefined ? undefined : {method:'POST',headers:{'Content-Type':body instanceof File ? 'application/octet-stream' : 'application/json'},body:body instanceof File ? body : JSON.stringify(body)});
  const result = await response.json();
  if (!response.ok) throw new Error(typeof result.detail === 'string' ? result.detail : '字幕操作失败，请检查输入或本地服务');
  return result;
}
