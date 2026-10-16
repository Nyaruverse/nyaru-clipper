import { useRef, useState } from 'react';
import { TextStyleFields, type FontCatalog } from './TextStyleFields';
import { effectiveAnchor, cueWarnings, mergeCues, nudgeCueStyle, patchCues, resolveStyle, splitCue, type EditableCue, type Language, type SubtitleDocument } from './subtitleDocument';
import type { TextStyle } from './subtitleStyle';
import { time } from './companionApi';

interface Props {
  readonly document: SubtitleDocument; readonly selected: readonly string[]; readonly onSelect: (ids: string[]) => void;
  readonly change: (update: (doc: SubtitleDocument) => SubtitleDocument) => void;
  readonly language: Language; readonly onLanguage: (language: Language) => void;
  readonly currentTime: number; readonly onSeek: (time: number) => void;
  readonly undo: () => void; readonly redo: () => void; readonly canUndo: boolean; readonly canRedo: boolean;
  readonly linked?: boolean; readonly onLinked?: (linked: boolean) => void;
  readonly fonts?: FontCatalog;
  readonly bilingual?: boolean;
}

export function CueEditor({ document: doc, selected, onSelect, change, language, onLanguage, currentTime, onSeek, undo, redo, canUndo, canRedo, linked = false, onLinked, fonts, bilingual = true }: Props) {
  const [query, setQuery] = useState('');
  const [page, setPage] = useState(0);
  const [tab, setTab] = useState('content');
  const [error, setError] = useState('');
  const [shift, setShift] = useState(0.1);
  const [emphasisColor, setEmphasisColor] = useState('#FFAA00');
  const [clipboard, setClipboard] = useState<TextStyle | null>(null);
  const textArea = useRef<HTMLTextAreaElement>(null);
  const cue = doc.cues.find(item => selected.includes(item.id));
  const filtered = doc.cues.filter(item => `${item.text}\n${item.translation}`.toLowerCase().includes(query.toLowerCase()));
  const style = cue ? resolveStyle(doc, cue, language) : doc.style[language];
  const point = cue ? effectiveAnchor(doc, cue, language, bilingual) : { x: doc.width / 2, y: doc.height / 2 };
  const update = (action: (cue: EditableCue) => EditableCue) => change(current => patchCues(current, selected, action));
  const stylePatch = (patch: Partial<TextStyle>) => change(current => patchCues(current, selected, item => ({ ...item,
    [`${language}_style`]: { ...resolveStyle(current, item, language), ...patch },
    ...(linked ? { [`${language === 'original' ? 'translation' : 'original'}_style`]: { ...resolveStyle(current, item, language === 'original' ? 'translation' : 'original'), ...patch } } : {}),
  })));
  const nudge = (dx: number, dy: number) => change(current => patchCues(current, selected, item => ({ ...item,
    [`${language}_style`]: nudgeCueStyle(current, item, language, dx, dy, bilingual),
    ...(linked ? { [`${language === 'original' ? 'translation' : 'original'}_style`]: nudgeCueStyle(current, item, language === 'original' ? 'translation' : 'original', dx, dy, bilingual) } : {}),
  })));
  const positionPatch = (patch: { x?: number; y?: number; align?: number }) => change(current => patchCues(current, selected, item => {
    const before = effectiveAnchor(current, item, language, bilingual);
    const next = { x: patch.x ?? before.x, y: patch.y ?? before.y };
    const other: Language = language === 'original' ? 'translation' : 'original';
    const otherPoint = effectiveAnchor(current, item, other, bilingual);
    return { ...item, [`${language}_style`]: { ...nudgeCueStyle(current, item, language, 0, 0, bilingual), ...next, ...(patch.align !== undefined ? { align: patch.align } : {}) },
      ...(linked ? { [`${other}_style`]: { ...nudgeCueStyle(current, item, other, 0, 0, bilingual), x: otherPoint.x + next.x - before.x, y: otherPoint.y + next.y - before.y, ...(patch.align !== undefined ? { align: patch.align } : {}) } } : {}) };
  }));
  const attempt = (action: () => void) => { try { action(); setError(''); } catch (failure) { setError(failure instanceof Error ? failure.message : '操作失败，请检查选择'); } };
  const selectCue = (item: EditableCue) => { onSelect([item.id]); onSeek(item.start_seconds); };
  return <section className="cue-editor" aria-label="逐条字幕编辑">
    <div className="cue-heading"><h3>逐条字幕编辑</h3><span>{doc.cues.length} 条 · 已选 {selected.length}</span></div>
    <div className="companion-downloads"><button className="ny-button" disabled={!canUndo} onClick={undo}>撤销</button><button className="ny-button" disabled={!canRedo} onClick={redo}>重做</button><button className="ny-button" onClick={() => onSelect(filtered.map(item => item.id))}>选择筛选结果</button><button className="ny-button" onClick={() => onSelect([])}>取消选择</button></div>
    <label className="ny-field">查找字幕<input className="ny-input" type="search" value={query} onChange={event => { setQuery(event.target.value); setPage(0); }} /></label>
    <div className="cue-list">{filtered.slice(page * 20, (page + 1) * 20).map(item => <div key={item.id} className={`cue-row ${selected.includes(item.id) ? 'is-selected' : ''}`}>
      <input type="checkbox" aria-label={`选择字幕 ${doc.cues.indexOf(item) + 1}`} checked={selected.includes(item.id)} onChange={event => onSelect(event.target.checked ? [...selected, item.id] : selected.filter(id => id !== item.id))} />
      <button type="button" aria-pressed={selected.includes(item.id)} onClick={() => selectCue(item)}><time>{time(item.start_seconds)} — {time(item.end_seconds)}</time><span>{item.text || '（空原文）'}</span>{item.translation && <small>{item.translation}</small>}</button>
    </div>)}</div>
    {filtered.length > 20 && <div className="companion-downloads"><button className="ny-button" disabled={page === 0} onClick={() => setPage(page - 1)}>上一页</button><span>{page + 1} / {Math.ceil(filtered.length / 20)}</span><button className="ny-button" disabled={(page + 1) * 20 >= filtered.length} onClick={() => setPage(page + 1)}>下一页</button></div>}
    {cue ? <>
      <div className="cue-tabs" role="group" aria-label="字幕编辑分类">{[{ id: 'content', label: '内容' }, { id: 'position', label: '位置' }, { id: 'style', label: '样式' }, { id: 'timing', label: '时间' }].map(item => <button className="ny-button" aria-pressed={tab === item.id} key={item.id} onClick={() => setTab(item.id)}>{item.label}</button>)}</div>
      <label className="ny-field">设置对象<select className="ny-input" value={language} onChange={event => onLanguage(event.target.value === 'original' ? 'original' : 'translation')}><option value="original">原文</option><option value="translation">译文</option></select></label>
      {onLinked && <label className="cue-toggle"><input type="checkbox" checked={linked} onChange={event => onLinked(event.target.checked)} />中日文联动（样式与位移）</label>}
      <p className="companion-footnote">{cue[`${language}_style`] ? '当前语言使用本条独立样式' : '当前语言继承全局样式'}；位置和样式操作应用于全部已选字幕。</p>
      {tab === 'content' && <>
        <label className="ny-field">本条原文<textarea className="ny-input" rows={3} value={cue.text} onChange={event => { const text = event.target.value; change(current => patchCues(current, [cue.id], item => ({ ...item, text, original_emphasis: [] }))); }} /></label>
        <label className="ny-field">本条译文<textarea className="ny-input" rows={3} value={cue.translation} onChange={event => { const translation = event.target.value; change(current => patchCues(current, [cue.id], item => ({ ...item, translation, translation_emphasis: [] }))); }} /></label>
        <details><summary>局部文字强调</summary><p className="companion-footnote">在下框选中文字后应用；改变正文会清除该语言旧的强调范围。</p><label className="ny-field">选择强调文字<textarea ref={textArea} className="ny-input" readOnly rows={3} value={language === 'original' ? cue.text : cue.translation} /></label>
          <label className="ny-field">强调颜色<input className="ny-input" type="color" value={emphasisColor} onChange={event => setEmphasisColor(event.target.value)} /></label>
          <button className="ny-button" onClick={() => attempt(() => {
            const area = textArea.current;
            if (!area || area.selectionStart === area.selectionEnd) throw new Error('请先在强调文字框中选中文字');
            const start = Array.from(area.value.slice(0, area.selectionStart)).length, end = Array.from(area.value.slice(0, area.selectionEnd)).length;
            change(current => patchCues(current, [cue.id], item => ({ ...item, [`${language}_emphasis`]: [...item[`${language}_emphasis`].filter(span => span.end <= start || span.start >= end), { start, end, color: emphasisColor, bold: true }].sort((a, b) => a.start - b.start) })));
          })}>应用颜色和加粗</button><button className="ny-button" onClick={() => update(item => ({ ...item, [`${language}_emphasis`]: [] }))}>清除所选强调</button>
        </details>
      </>}
      {tab === 'position' && <>
        <p className="companion-muted">坐标单位为输出视频像素（{doc.width} × {doc.height}）。画面中的锚点可拖动；聚焦锚点后用方向键微调，Shift 为 10 像素。</p>
        <div className="cue-style-fields">{(['x', 'y'] as const).map(axis => <label className="ny-field" key={axis}>{axis.toUpperCase()} 坐标<input className="ny-input" type="number" step={0.1} value={point[axis]} onChange={event => { if (Number.isFinite(event.target.valueAsNumber)) positionPatch({ [axis]: event.target.valueAsNumber }); }} /></label>)}</div>
        <div className="cue-anchor-grid" aria-label="九宫格锚点">{[7, 8, 9, 4, 5, 6, 1, 2, 3].map((align, index) => <button className="ny-button" aria-label={`锚点 ${['左上', '上中', '右上', '左中', '中心', '右中', '左下', '下中', '右下'][index]}`} aria-pressed={(style.align ?? (style.position === 'top' ? 8 : 2)) === align} key={align} onClick={() => positionPatch({ align })}>{['↖', '↑', '↗', '←', '·', '→', '↙', '↓', '↘'][index]}</button>)}</div>
        <div className="companion-downloads">{[{ label: '向左 1 像素', dx: -1, dy: 0 }, { label: '向右 1 像素', dx: 1, dy: 0 }, { label: '向上 1 像素', dx: 0, dy: -1 }, { label: '向下 1 像素', dx: 0, dy: 1 }].map(item => <button className="ny-button" aria-label={item.label} key={item.label} onClick={() => nudge(item.dx, item.dy)}>{item.label}</button>)}</div>
        <div className="companion-downloads"><button className="ny-button" onClick={() => positionPatch({ x: doc.width / 2, align: Math.floor(((style.align ?? 2) - 1) / 3) * 3 + 2 })}>水平居中</button><button className="ny-button" onClick={() => stylePatch({ x: null, y: null })}>恢复自动位置</button></div>
      </>}
      {tab === 'style' && <TextStyleFields style={style} onChange={stylePatch} fonts={fonts} />}
      {tab === 'timing' && <>
        <div className="cue-style-fields">{(['start_seconds', 'end_seconds'] as const).map(key => <label className="ny-field" key={key}>{key === 'start_seconds' ? '开始秒数' : '结束秒数'}<input className="ny-input" type="number" step={0.001} min={0} max={doc.duration} value={cue[key]} onChange={event => { const value = event.target.valueAsNumber; if (Number.isFinite(value)) change(current => patchCues(current, [cue.id], item => ({ ...item, [key]: value }))); }} /></label>)}</div>
        <div className="companion-downloads"><button className="ny-button" onClick={() => update(item => ({ ...item, start_seconds: Math.max(0, item.start_seconds - 1 / doc.fps), end_seconds: item.end_seconds - 1 / doc.fps }))}>提前一帧</button><button className="ny-button" onClick={() => update(item => ({ ...item, start_seconds: item.start_seconds + 1 / doc.fps, end_seconds: item.end_seconds + 1 / doc.fps }))}>延后一帧</button></div>
        <label className="ny-field">批量平移秒数（负数提前）<input className="ny-input" type="number" step={0.01} value={shift} onChange={event => { if (Number.isFinite(event.target.valueAsNumber)) setShift(event.target.valueAsNumber); }} /></label><button className="ny-button" onClick={() => update(item => ({ ...item, start_seconds: item.start_seconds + shift, end_seconds: item.end_seconds + shift }))}>平移所选时间</button>
        <div className="companion-downloads"><button className="ny-button" disabled={selected.length !== 1} onClick={() => attempt(() => { const next = splitCue(doc, cue.id, currentTime, `edit-${crypto.randomUUID()}`); change(() => next); })}>在播放头拆分</button><button className="ny-button" disabled={selected.length < 2} onClick={() => attempt(() => { const next = mergeCues(doc, selected); change(() => next); onSelect([next.cues.find(item => selected.includes(item.id))?.id ?? cue.id]); })}>合并所选字幕</button></div>
        <p className="companion-footnote">合并保留第一条的独立样式。重叠可保留，超出视频或无效起止时间必须修正后才能保存。</p>
      </>}
      <div className="companion-downloads"><button className="ny-button" onClick={() => setClipboard(style)}>复制样式</button><button className="ny-button" disabled={!clipboard} onClick={() => { if (clipboard) stylePatch(clipboard); }}>粘贴样式</button><button className="ny-button" disabled={!clipboard} onClick={() => { if (clipboard) stylePatch({ x: clipboard.x ?? null, y: clipboard.y ?? null, align: clipboard.align, position: clipboard.position, margin: clipboard.margin }); }}>只粘贴位置</button><button className="ny-button" onClick={() => update(item => ({ ...item, [`${language}_style`]: null, ...(linked ? { original_style: null, translation_style: null } : {}) }))}>恢复所选继承</button></div>
      <button className="ny-button" onClick={() => stylePatch(doc.style[language])}>应用当前全局模板到所选</button>
      {cueWarnings(doc, cue).map(warning => <p key={warning} role="status" className="companion-muted">{warning}</p>)}
    </> : <p className="companion-muted">选择一条或多条字幕，开始调整。</p>}
    {error && <p role="alert" className="companion-error">{error}</p>}
  </section>;
}
