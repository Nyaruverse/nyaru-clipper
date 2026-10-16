import type { SubtitleStyle, TextStyle } from './subtitleStyle';

export type Language = 'original' | 'translation';
export interface Emphasis { readonly start: number; readonly end: number; readonly color: string; readonly bold: boolean }
export interface EditableCue {
  readonly id: string; readonly start_seconds: number; readonly end_seconds: number;
  readonly text: string; readonly translation: string;
  readonly original_style: TextStyle | null; readonly translation_style: TextStyle | null;
  readonly original_emphasis: readonly Emphasis[]; readonly translation_emphasis: readonly Emphasis[];
}
export interface SubtitleDocument {
  readonly version: 1; readonly source_fingerprint: string; readonly revision: number;
  readonly style: SubtitleStyle; readonly cues: readonly EditableCue[];
  readonly width: number; readonly height: number; readonly duration: number; readonly fps: number;
}
export const advancedDefaults = {
  bold: false, italic: false, underline: false, opacity: 1, spacing: 0, line_height: 1.2,
  align: 2, x: null, y: null, rotation: 0, scale_x: 100, scale_y: 100, shadow: 0,
  shadow_color: '#000000', padding: 0, max_width: 100, hidden: false,
} as const;

function record(value: unknown): value is Record<string, unknown> { return typeof value === 'object' && value !== null; }
function finite(value: unknown): value is number { return typeof value === 'number' && Number.isFinite(value); }
function textStyle(value: unknown): value is TextStyle {
  if (!record(value)) return false;
  return typeof value.font === 'string' && finite(value.size) && finite(value.outline) && finite(value.margin)
    && typeof value.color === 'string' && typeof value.outline_color === 'string' && typeof value.background_color === 'string'
    && finite(value.background_opacity) && (value.position === 'top' || value.position === 'bottom');
}
function emphasis(value: unknown): value is readonly Emphasis[] {
  return Array.isArray(value) && value.every((span: unknown) => record(span) && Number.isInteger(span.start) && Number.isInteger(span.end) && typeof span.color === 'string' && typeof span.bold === 'boolean');
}
function editableCue(value: unknown): value is EditableCue {
  return record(value) && typeof value.id === 'string' && finite(value.start_seconds) && finite(value.end_seconds)
    && typeof value.text === 'string' && typeof value.translation === 'string'
    && (value.original_style === null || textStyle(value.original_style)) && (value.translation_style === null || textStyle(value.translation_style))
    && emphasis(value.original_emphasis) && emphasis(value.translation_emphasis);
}
function subtitleDocument(value: unknown): value is SubtitleDocument {
  return record(value) && value.version === 1 && typeof value.source_fingerprint === 'string' && /^[a-f0-9]{64}$/.test(value.source_fingerprint)
    && finite(value.revision) && Number.isInteger(value.revision) && value.revision >= 0
    && finite(value.width) && value.width > 0 && finite(value.height) && value.height > 0
    && finite(value.duration) && value.duration > 0 && finite(value.fps) && value.fps > 0
    && record(value.style) && value.style.version === 1 && textStyle(value.style.original) && textStyle(value.style.translation)
    && Array.isArray(value.cues) && value.cues.every(editableCue);
}
export function parseDocument(value: unknown): SubtitleDocument {
  if (!subtitleDocument(value)) throw new Error('字幕编辑稿格式无效，请检查本地服务版本后重新载入');
  return value;
}

export function assCentiseconds(value: number): number {
  const [mantissa, exponent = '0'] = String(value).split('e');
  return Math.round(Number(`${mantissa}e${Number(exponent) + 2}`));
}
export function activeDocumentCues(doc: SubtitleDocument, time: number): readonly EditableCue[] {
  return doc.cues.filter(cue => assCentiseconds(cue.start_seconds) <= time * 100 && time * 100 < assCentiseconds(cue.end_seconds));
}

export function resolveStyle(doc: SubtitleDocument, cue: EditableCue, language: Language): TextStyle {
  const inherited = doc.style[language];
  const override = cue[`${language}_style`];
  const style = { ...advancedDefaults, ...inherited, ...override };
  const align = override?.align ?? inherited.align ?? (style.position === 'top' ? 8 : 2);
  return { ...style, align: style.position === 'top' && align === 2 && style.x === null && style.y === null ? 8 : align };
}

export function patchCues(doc: SubtitleDocument, ids: readonly string[], update: (cue: EditableCue) => EditableCue): SubtitleDocument {
  const selected = new Set(ids);
  return { ...doc, cues: doc.cues.map(cue => selected.has(cue.id) ? update(cue) : cue) };
}

function splitEmphasis(spans: readonly Emphasis[], start: number, end: number): Emphasis[] {
  return spans.filter(span => span.end > start && span.start < end).map(span => ({ ...span,
    start: Math.max(start, span.start) - start, end: Math.min(end, span.end) - start }));
}

export function splitCue(doc: SubtitleDocument, id: string, at: number, newId: string, textIndex?: number): SubtitleDocument {
  const cue = doc.cues.find(item => item.id === id);
  if (!cue || at <= cue.start_seconds || at >= cue.end_seconds) throw new Error('请将播放头移到所选字幕的起止时间之间再拆分');
  const ratio = (at - cue.start_seconds) / (cue.end_seconds - cue.start_seconds);
  const source = Array.from(cue.text), target = Array.from(cue.translation);
  const cut = textIndex ?? Math.round(source.length * ratio), targetCut = Math.round(target.length * ratio);
  const first = { ...cue, end_seconds: at, text: source.slice(0, cut).join(''), translation: target.slice(0, targetCut).join(''),
    original_emphasis: splitEmphasis(cue.original_emphasis, 0, cut), translation_emphasis: splitEmphasis(cue.translation_emphasis, 0, targetCut) };
  const second = { ...cue, id: newId, start_seconds: at, text: source.slice(cut).join(''), translation: target.slice(targetCut).join(''),
    original_emphasis: splitEmphasis(cue.original_emphasis, cut, source.length), translation_emphasis: splitEmphasis(cue.translation_emphasis, targetCut, target.length) };
  return { ...doc, cues: doc.cues.flatMap(item => item.id === id ? [first, second] : [item]) };
}

export function mergeCues(doc: SubtitleDocument, ids: readonly string[]): SubtitleDocument {
  const chosen = doc.cues.filter(cue => ids.includes(cue.id));
  const first = chosen[0], last = chosen[chosen.length - 1];
  if (!first || !last || chosen.length < 2) throw new Error('请至少选择两条相邻字幕');
  if (doc.cues.indexOf(last) - doc.cues.indexOf(first) + 1 !== chosen.length) throw new Error('只能合并相邻字幕');
  let sourceOffset = 0, targetOffset = 0;
  const sourceSpans: Emphasis[] = [], targetSpans: Emphasis[] = [];
  for (const cue of chosen) {
    sourceSpans.push(...cue.original_emphasis.map(span => ({ ...span, start: span.start + sourceOffset, end: span.end + sourceOffset })));
    targetSpans.push(...cue.translation_emphasis.map(span => ({ ...span, start: span.start + targetOffset, end: span.end + targetOffset })));
    sourceOffset += Array.from(cue.text).length + 1;
    targetOffset += Array.from(cue.translation).length + 1;
  }
  const merged = { ...first, end_seconds: Math.max(...chosen.map(cue => cue.end_seconds)),
    text: chosen.map(cue => cue.text).join('\n'), translation: chosen.map(cue => cue.translation).join('\n'),
    original_emphasis: sourceSpans, translation_emphasis: targetSpans };
  return { ...doc, cues: doc.cues.flatMap(cue => cue.id === first.id ? [merged] : ids.includes(cue.id) ? [] : [cue]) };
}

function effectiveAlignment(style: TextStyle): number {
  return style.position === 'top' && (style.align ?? 2) === 2 && style.x == null && style.y == null ? 8 : style.align ?? (style.position === 'top' ? 8 : 2);
}

export function anchorPosition(style: TextStyle, width: number, height: number): { x: number; y: number } {
  const align = effectiveAlignment(style);
  const column = (align - 1) % 3, row = Math.floor((align - 1) / 3);
  const margin = style.margin * height / 1080;
  return { x: style.x ?? (column === 0 ? 20 * height / 1080 : column === 1 ? width / 2 : width - 20 * height / 1080),
    y: style.y ?? (row === 0 ? height - margin : row === 1 ? height / 2 : margin) };
}

export function nudgeStyle(style: TextStyle, dx: number, dy: number, width: number, height: number): TextStyle {
  const point = anchorPosition(style, width, height);
  return { ...style, align: effectiveAlignment(style), x: Math.round((point.x + dx) * 100) / 100, y: Math.round((point.y + dy) * 100) / 100 };
}

function wrappedLineCount(text: string, style: TextStyle, width: number): number {
  const available = Math.max(1, width * (style.max_width ?? 100) / 100 - 40 - 2 * (style.padding ?? 0));
  let lines = 1, used = 0;
  for (const char of text.replace(/\r\n?/g, '\n')) {
    if (char === '\n') { lines++; used = 0; continue; }
    const advance = /\p{M}/u.test(char) ? 0 : Math.max(0, style.size * 1.2 + (style.spacing ?? 0)) * (style.scale_x ?? 100) / 100;
    if (used && used + advance > available) { lines++; used = 0; }
    used += advance;
  }
  return lines;
}

export function effectiveAnchor(doc: SubtitleDocument, cue: EditableCue, language: Language, bilingual: boolean): { x: number; y: number } {
  const original = resolveStyle(doc, cue, 'original'), translation = resolveStyle(doc, cue, 'translation');
  const style = language === 'original' ? original : translation;
  let margin = style.margin;
  let center = doc.height / 2;
  if (bilingual && cue.text && cue.translation && !original.hidden && !translation.hidden && style.x == null && style.y == null) {
    const width = doc.width / (doc.height / 1080);
    const originalHeight = wrappedLineCount(cue.text, original, width) * original.size * (original.line_height ?? 1.2) * (original.scale_y ?? 100) / 100 + 8;
    const translationHeight = wrappedLineCount(cue.translation, translation, width) * translation.size * (translation.line_height ?? 1.2) * (translation.scale_y ?? 100) / 100 + 8;
    if (original.position === translation.position) {
      if (language === 'original' && style.position === 'bottom') margin = Math.max(margin, translation.margin + translationHeight);
      if (language === 'translation' && style.position === 'top') margin = Math.max(margin, original.margin + originalHeight);
    }
    if (Math.floor((effectiveAlignment(original) - 1) / 3) === 1 && Math.floor((effectiveAlignment(translation) - 1) / 3) === 1) center += (language === 'original' ? -translationHeight : originalHeight) * doc.height / 1080 / 2;
  }
  const point = anchorPosition({ ...style, margin }, doc.width, doc.height);
  return style.y == null && Math.floor((effectiveAlignment(style) - 1) / 3) === 1 ? { ...point, y: center } : point;
}

export function nudgeCueStyle(doc: SubtitleDocument, cue: EditableCue, language: Language, dx: number, dy: number, bilingual: boolean): TextStyle {
  const point = effectiveAnchor(doc, cue, language, bilingual);
  const style = resolveStyle(doc, cue, language);
  return nudgeStyle({ ...style, align: effectiveAlignment(style), x: point.x, y: point.y }, dx, dy, doc.width, doc.height);
}

export function cueWarnings(doc: SubtitleDocument, cue: EditableCue): string[] {
  const warnings: string[] = [], duration = cue.end_seconds - cue.start_seconds;
  if (duration <= 0 || cue.start_seconds < 0 || cue.end_seconds > doc.duration) warnings.push('时间超出视频或结束早于开始，保存前请修正');
  if (Math.max(Array.from(cue.text).length, Array.from(cue.translation).length) / duration > 20) warnings.push('阅读速度较快，建议延长显示时间或缩短文字');
  if (doc.cues.some(other => other.id !== cue.id && other.start_seconds < cue.end_seconds && other.end_seconds > cue.start_seconds)) warnings.push('与其他字幕时间重叠，请核对是否需要同时显示');
  for (const language of ['original', 'translation'] as const) {
    const style = resolveStyle(doc, cue, language), point = anchorPosition(style, doc.width, doc.height);
    if (point.x < 0 || point.x > doc.width || point.y < 0 || point.y > doc.height) warnings.push(`${language === 'original' ? '原文' : '译文'}锚点超出画面`);
  }
  return warnings;
}

export function documentProblem(doc: SubtitleDocument): string | null {
  for (const cue of doc.cues) {
    if (!Number.isFinite(cue.start_seconds) || !Number.isFinite(cue.end_seconds) || cue.start_seconds < 0 || cue.end_seconds <= cue.start_seconds || cue.end_seconds > doc.duration) return '请修正字幕起止时间后保存';
    if (/[\x00-\x09\x0b\x0c\x0e-\x1f\x7f-\x9f]/.test(cue.text + cue.translation)) return '字幕含制表符或控制字符，请替换为空格后保存';
  }
  for (const style of [doc.style.original, doc.style.translation, ...doc.cues.flatMap(cue => [cue.original_style, cue.translation_style]).filter((style): style is TextStyle => style !== null)]) {
    if (!style.font.trim()) return '请填写字体名称后保存';
    if ((style.x !== null && style.x !== undefined && (!Number.isFinite(style.x) || style.x < 0 || style.x > doc.width)) || (style.y !== null && style.y !== undefined && (!Number.isFinite(style.y) || style.y < 0 || style.y > doc.height))) return '字幕坐标超出画面，请修正后保存';
  }
  return null;
}
