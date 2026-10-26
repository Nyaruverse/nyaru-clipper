import {useEffect, useState} from 'react';
import {useMutation, useQuery, useQueryClient} from '@tanstack/react-query';
import {Play, Sparkles} from 'lucide-react';
import {createPortal} from 'react-dom';
import {api, parseTime, time} from './companionApi';
import type {SubtitleDocument} from './subtitleDocument';
import {TopicRangeEditor} from './TopicRangeEditor';
import {TopicSelection} from './TopicSelection';
import {useTopicDraft, type TopicRange} from './useTopicDraft';

interface Topic extends TopicRange {
  readonly index: number; readonly title: string; readonly summary: string;
  readonly score?: number | null; readonly dm_count?: number | null;
  readonly loudness_db?: number | null; readonly hot_words?: readonly string[]; readonly risk_terms?: readonly string[];
}
interface Topics {
  readonly state: string; readonly operation_id?: string; readonly document_revision?: number | null; readonly created_at?: number;
  readonly segments?: readonly Topic[]; readonly vocabulary?: readonly string[]; readonly quotes?: readonly {readonly text: string; readonly start?: number}[];
  readonly total_cues?: number; readonly covered_cues?: number; readonly truncated?: boolean;
  readonly error?: string | null; readonly audio_state?: 'available' | 'truncated' | 'unavailable'; readonly streamer?: string | null;
}
interface Clips {
  readonly state: string; readonly error?: string | null;
  readonly items?: readonly {readonly index: number; readonly state: string; readonly error?: string | null; readonly url?: string}[];
  readonly combined?: {readonly url?: string} | null;
}
export interface TopicOutput {readonly url: string; readonly title: string}
export interface TopicPreview extends TopicRange {readonly title: string}
interface Props {
  readonly jobId: string; readonly documentRevision: number; readonly prepare: () => Promise<string | null>; readonly onSeek: (seconds: number) => void;
  readonly duration?: number; readonly document?: SubtitleDocument | null; readonly sourceLanguage?: string;
  readonly onPreview?: (preview: TopicPreview | null) => void; readonly onQueue?: () => void;
  readonly rangeTarget?: HTMLElement | null; readonly onOutput?: (output: TopicOutput) => void;
}
const working = (state?: string) => state === 'queued' || state === 'running' || state === 'paused';
const states: Readonly<Record<string, string>> = {not_started: '尚未分析', queued: '已加入队列', running: '正在处理',
  paused: '已暂停', completed: '已完成', stale: '需要重新分析', failed: '处理失败', interrupted: '处理已中断', cancelled: '已取消'};

// Algorithm and ordered selection adapted from collaborator commit 69d3fa0.
export function TopicSegmentsPanel({jobId, documentRevision, prepare, onSeek, duration, document, sourceLanguage, onPreview, onQueue, rangeTarget, onOutput}: Props) {
  const client = useQueryClient(), key = ['companion', 'topics', jobId];
  const topics = useQuery({queryKey: [...key, documentRevision], queryFn: () => api<Topics>(`/jobs/${jobId}/topic-segments`), refetchInterval: query => working(query.state.data?.state) ? 1000 : false});
  const clips = useQuery({queryKey: [...key, 'clips'], queryFn: () => api<Clips>(`/jobs/${jobId}/topic-clips`), refetchInterval: query => working(query.state.data?.state) ? 1000 : false});
  const danmaku = useQuery({queryKey: [...key, 'danmaku'], queryFn: () => api<{count: number}>(`/jobs/${jobId}/danmaku`)});
  const {draft, update, persistenceError} = useTopicDraft(jobId);
  const [notice, setNotice] = useState(''), [confirmation, setConfirmation] = useState(false);
  const store = topics.data, segments = store?.segments ?? [];
  useEffect(() => {
    if (!store?.operation_id && store?.created_at === undefined) return;
    if (store.state !== 'completed' && store.state !== 'stale') return;
    const analysisKey = `${store.operation_id ?? ''}/${store.created_at ?? ''}`;
    if (draft.analysisKey !== analysisKey) update(draft.analysisKey === null ? {analysisKey} : {analysisKey, selected: [], ranges: {}, current: null});
  }, [store?.operation_id, store?.created_at, store?.state, draft.analysisKey]);
  const refresh = () => {void client.invalidateQueries({queryKey: key});void client.invalidateQueries({queryKey: ['workstation', 'operations']});};
  const analyze = useMutation({mutationFn: async () => {
    const error = await prepare();if (error) throw new Error(error);
    return api(`/jobs/${jobId}/topic-segments`, {start_seconds: draft.start.trim() ? parseTime(draft.start) : undefined,
      end_seconds: draft.end.trim() ? parseTime(draft.end) : undefined, max_segments: draft.limit});
  }, onSuccess: () => {setNotice('分析已加入统一队列；队列暂停时需要手动启动。');refresh();}});
  const generate = useMutation({mutationFn: async () => {
    const error = await prepare();if (error) throw new Error(error);
    const ranges = draft.selected.flatMap(index => draft.ranges[index] ? [{index, ...draft.ranges[index]}] : []);
    return api(`/jobs/${jobId}/topic-clips`, {indices: draft.selected, mode: draft.mode, variant: draft.variant, ...(ranges.length ? {ranges} : {})});
  }, onSuccess: () => {setConfirmation(false);setNotice('视频生成已加入统一队列，完成后在这里下载。');refresh();}});
  const upload = useMutation({mutationFn: async (file: File) => {
    if (file.size > 4 * 1024 * 1024) throw new Error('请选择不超过 4 MiB 的 XML 或 ASS 弹幕文件。');
    return api(`/jobs/${jobId}/danmaku`, {content: await file.text(), streamer: draft.streamer.trim() || undefined});
  }, onSuccess: () => {setNotice('弹幕已导入，请重新分析以更新评分。');refresh();}});
  const pending = analyze.isPending || generate.isPending || upload.isPending || working(store?.state) || working(clips.data?.state);
  const stale = store?.state === 'stale' || (store?.state === 'completed' && store.document_revision != null && store.document_revision !== documentRevision);
  const sorted = draft.sort === 'score' ? [...segments].sort((a, b) => (b.score ?? -1) - (a.score ?? -1) || a.index - b.index) : segments;
  const selected = draft.selected.flatMap(index => {const segment = segments.find(row => row.index === index);return segment ? [{...segment, ...draft.ranges[index]}] : [];});
  const current = segments.find(row => row.index === draft.current);
  const currentRange = current && (draft.ranges[current.index] ?? current);
  useEffect(() => {
    onPreview?.(current && currentRange ? {...currentRange, title: current.title} : null);
  }, [current?.index, current?.title, currentRange?.start_seconds, currentRange?.end_seconds, onPreview]);
  const error = topics.error ?? clips.error ?? danmaku.error ?? analyze.error ?? generate.error ?? upload.error;
  const missingTranslation = document && draft.variant !== 'original' && !(draft.variant === 'zh' && sourceLanguage === 'zh') && selected.some(segment => document.cues.some(cue => cue.end_seconds > segment.start_seconds && cue.start_seconds < segment.end_seconds && !cue.translation.trim()));
  function preview(segment: Topic, range: TopicRange = draft.ranges[segment.index] ?? segment) {
    update({current: segment.index});onSeek(range.start_seconds);
  }
  const rangeEditor = current && duration !== undefined ? <TopicRangeEditor key={current.index} range={draft.ranges[current.index] ?? current} duration={duration} disabled={pending || stale} onChange={range => {update(previous => ({ranges: {...previous.ranges, [current.index]: range}}));preview(current, range);}}/> : null;
  return <section className="topic-workbench" aria-label="高光分析与切片">
    <header className="topic-pane-heading"><h2><Sparkles size={18}/>高光候选 <span>{segments.length}</span></h2>{onQueue && <button className="ny-button ny-button--quiet" onClick={onQueue}>任务队列</button>}</header>
    <div className="topic-pane-body">
      <details className="topic-analysis-options" open={draft.optionsOpen} onToggle={event => {if (event.currentTarget.open !== draft.optionsOpen) update({optionsOpen: event.currentTarget.open});}}><summary>分析选项</summary>
        <p className="companion-footnote">根据已保存字幕分析，会使用当前 AI 额度。评分仅用于本场比较，仍需看片确认。</p>
        <form className="cue-style-fields" onSubmit={event => {event.preventDefault();analyze.mutate();}}>
          <label className="ny-field">分析开始<input className="ny-input" placeholder="00:00 或秒数" value={draft.start} onChange={event => update({start: event.target.value})}/></label>
          <label className="ny-field">分析结束<input className="ny-input" placeholder="留空至结尾" value={draft.end} onChange={event => update({end: event.target.value})}/></label>
          <label className="ny-field">最多话题数<input className="ny-input" type="number" min={1} max={100} required value={draft.limit} onChange={event => update({limit: event.target.valueAsNumber})}/></label>
          <button className="ny-button ny-button--primary" disabled={pending} type="submit">分析高光话题</button>
        </form>
        <details><summary>弹幕与评分输入 · {danmaku.data?.count ?? 0} 条</summary><p className="companion-footnote">导入 XML／ASS 弹幕可补充互动评分。音频兴奋度仅供参考。</p>
          <label className="ny-field">主播／系列名称（选填）<input className="ny-input" maxLength={128} value={draft.streamer} onChange={event => update({streamer: event.target.value})}/></label>
          <label className="ny-field">导入弹幕<input type="file" accept=".xml,.ass" disabled={pending} onChange={event => {const file = event.target.files?.[0];if (file) upload.mutate(file);event.target.value = '';}}/></label>
        </details>
      </details>
      {store && <p role="status" className="topic-analysis-status">分析：{states[store.state] ?? store.state}{store.document_revision != null && ` · 编辑稿 v${store.document_revision}`}</p>}
      {store?.truncated ? <p role="status" className="topic-coverage-warning">仅覆盖 {store.covered_cues ?? '—'}/{store.total_cues ?? '—'} 条字幕，尚未分析完整范围。请调整范围继续分析。</p>
        : store?.state === 'completed' && <p className="companion-footnote">{store.total_cues !== undefined && store.covered_cues === store.total_cues ? `已覆盖所选范围 · ${store.total_cues} 条字幕` : '分析覆盖范围未报告，请结合所选范围核对。'}</p>}
      {stale && <p role="alert" className="companion-error">字幕已修改，请重新分析。现有候选和勾选保留，重新分析前不能生成。</p>}
      {(error || store?.error) && <p role="alert" className="companion-error">{error?.message ?? store?.error}</p>}
      {!!segments.length && <div className="topic-list-toolbar"><span>勾选保留 · 点击标题预览</span><label>排序<select className="ny-input" aria-label="话题排序" value={draft.sort} onChange={event => update({sort: event.target.value === 'score' ? 'score' : 'time'})}><option value="time">时间顺序</option><option value="score" disabled={segments.every(segment => segment.score == null)}>评分从高到低</option></select></label></div>}
      <div className="topic-results">{sorted.map(segment => {const range = draft.ranges[segment.index] ?? segment, position = draft.selected.indexOf(segment.index);return <article className={`topic-result ${draft.current === segment.index ? 'is-current' : ''}`} key={segment.index}>
        <label className="topic-selection-hit"><input type="checkbox" checked={position >= 0} disabled={pending} aria-label={`选择${segment.title}`} onChange={() => update(previous => ({selected: previous.selected.includes(segment.index) ? previous.selected.filter(index => index !== segment.index) : [...previous.selected, segment.index]}))}/></label>
        <button type="button" className="topic-candidate-preview" aria-label={`预览${segment.title}`} aria-pressed={draft.current === segment.index} onClick={() => preview(segment)}><strong>{position >= 0 && <span className="topic-order-number">{position + 1}</span>}{segment.title}</strong><time>{time(range.start_seconds)} — {time(range.end_seconds)} · {time(range.end_seconds - range.start_seconds)}</time><span className="topic-candidate-summary">{segment.summary}</span></button>
        <span className="topic-relative-score" aria-label={segment.score == null ? '评分不可用' : `相对评分 ${segment.score}`}>{segment.score ?? '—'}</span>
        {!!segment.risk_terms?.length && <p className="topic-review-terms">需复核：{segment.risk_terms.join('、')}</p>}
      </article>;})}</div>
      {store?.state === 'completed' && !segments.length && <div className="topic-empty"><h3>没有找到高光候选</h3><p>可调整分析范围或检查字幕内容，再发起分析。</p><button className="ny-button" onClick={() => update({optionsOpen: true})}>调整分析选项</button></div>}
      {(!store || store.state === 'not_started') && <div className="topic-empty"><Play size={24}/><h3>从这段视频中找出值得留下的瞬间</h3><p>先确认分析范围，再开始分析高光。</p><button className="ny-button ny-button--primary" onClick={() => update({optionsOpen: true})}>设置高光分析</button></div>}
      {rangeTarget ? createPortal(rangeEditor, rangeTarget) : rangeEditor}
      {!!segments.length && <details className="topic-signal-details"><summary>评分依据与本场热词</summary><p className="companion-footnote">{segments.every(segment => segment.score == null) ? '缺少互动评分数据，当前不提供评分排序。' : '分数是本场相对排序，不代表高光概率。'}音频：{store?.audio_state === 'available' ? '可用' : store?.audio_state === 'truncated' ? '仅分析前 12 小时' : '不可用'}。</p>{store?.vocabulary?.length ? <p>{store.vocabulary.join(' · ')}</p> : null}{store?.quotes?.map((quote, index) => <button className="ny-button ny-button--quiet" key={index} disabled={quote.start === undefined} onClick={() => {if (quote.start !== undefined) onSeek(quote.start);}}>金句：{quote.text}</button>)}</details>}
      {persistenceError && <p role="status" className="companion-error">{persistenceError}</p>}
      {notice && <p role="status" className="topic-notice">{notice}</p>}
      {clips.data && clips.data.state !== 'not_started' && <section className="topic-produced"><h3>成片结果</h3><p role="status">{states[clips.data.state] ?? clips.data.state}</p>{clips.data.error && <p role="alert">{clips.data.error}</p>}{clips.data.items?.map(item => item.url ? <div key={item.index} className="topic-produced-actions">{onOutput && <button className="ny-button" onClick={() => {if (item.url) onOutput({url: item.url, title: segments.find(segment => segment.index === item.index)?.title ?? `话题 ${item.index + 1}`});}}>播放话题 {item.index + 1}</button>}<a className="ny-button" href={item.url} download>下载话题 {item.index + 1}</a></div> : item.error ? <p role="alert" key={item.index}>{item.error}</p> : null)}{clips.data.combined?.url && <div className="topic-produced-actions">{onOutput && <button className="ny-button" onClick={() => {const url = clips.data?.combined?.url;if (url) onOutput({url, title: "组合视频"});}}>播放组合视频</button>}<a className="ny-button" href={clips.data.combined.url} download>下载组合视频</a></div>}</section>}
    </div>
    <TopicSelection draft={draft} items={selected} disabled={pending || stale || store?.state !== 'completed'} pending={generate.isPending} open={confirmation} onOpen={setConfirmation} update={update} onGenerate={() => generate.mutate()} problem={missingTranslation ? '所选范围缺少翻译字幕。请先补齐翻译，或选择原文字幕。' : null}/>
  </section>;
}
