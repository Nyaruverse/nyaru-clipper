import {useEffect, useState} from 'react';
import {useMutation, useQuery, useQueryClient} from '@tanstack/react-query';
import {api, parseTime, time} from './companionApi';

interface Topic {
  index: number; start_seconds: number; end_seconds: number; title: string; summary: string;
  score?: number | null; grade?: string | null; dm_count?: number | null;
  loudness_db?: number | null; laugh_rate?: number | null; hot_words?: string[]; risk_terms?: string[];
}
interface Topics {
  state: string; operation_id?: string; document_revision?: number; created_at?: number;
  segments?: Topic[]; vocabulary?: string[]; quotes?: {text: string; start?: number}[];
  error?: string | null;
  audio_state?: 'available' | 'truncated' | 'unavailable';
  streamer?: string | null;
}
interface Clips {
  state: string; error?: string | null;
  items?: {index: number; file?: string | null; state: string; error?: string | null; url?: string}[];
  combined?: {file?: string; url?: string} | null;
}
const working = (state?: string) => state === 'queued' || state === 'running' || state === 'paused';
const states: Record<string, string> = {not_started: '尚未生成', queued: '已加入队列', running: '正在处理',
  paused: '已暂停', completed: '已完成', stale: '需要重新分析', failed: '处理失败', interrupted: '处理已中断', cancelled: '已取消'};

// Algorithm and ordered selection adapted from collaborator commit 69d3fa0.
export function TopicSegmentsPanel({jobId, documentRevision, prepare, onSeek}: {
  jobId: string; documentRevision: number; prepare: () => Promise<string | null>; onSeek: (seconds: number) => void;
}) {
  const client = useQueryClient();
  const base = `/jobs/${jobId}`;
  const key = ['companion', 'topics', jobId];
  const topics = useQuery({queryKey: [...key, documentRevision], queryFn: () => api<Topics>(`${base}/topic-segments`),
    refetchInterval: query => working(query.state.data?.state) ? 1000 : false});
  const clips = useQuery({queryKey: [...key, 'clips'], queryFn: () => api<Clips>(`${base}/topic-clips`),
    refetchInterval: query => working(query.state.data?.state) ? 1000 : false});
  const danmaku = useQuery({queryKey: [...key, 'danmaku'], queryFn: () => api<{count: number; source?: string}>(`${base}/danmaku`)});
  const [start, setStart] = useState('');
  const [end, setEnd] = useState('');
  const [limit, setLimit] = useState(30);
  const [selected, setSelected] = useState<number[]>([]);
  const [sort, setSort] = useState('time');
  const [mode, setMode] = useState<'separate' | 'combined'>('separate');
  const [variant, setVariant] = useState<'original' | 'zh' | 'bilingual'>('original');
  const [notice, setNotice] = useState('');
  const [streamer, setStreamer] = useState('');
  const store = topics.data;
  useEffect(() => setSelected([]), [store?.operation_id, store?.created_at]);
  const refresh = () => { void client.invalidateQueries({queryKey: key}); void client.invalidateQueries({queryKey: ['workstation', 'operations']}); };
  const analyze = useMutation({mutationFn: async () => {
    const error = await prepare();
    if (error) throw new Error(error);
    const options = {start_seconds: start.trim() ? parseTime(start) : undefined,
      end_seconds: end.trim() ? parseTime(end) : undefined, max_segments: limit};
    return api(`${base}/topic-segments`, options);
  }, onSuccess: () => {setNotice('分析已加入统一队列，可在任务记录中启动队列、取消或重试。'); refresh();}});
  const generate = useMutation({mutationFn: async () => {
    const error = await prepare();
    if (error) throw new Error(error);
    return api(`${base}/topic-clips`, {indices: selected, mode, variant});
  }, onSuccess: () => {setNotice('视频生成已加入统一队列。'); refresh();}});
  const upload = useMutation({mutationFn: async (file: File) => {
    if (file.size > 4 * 1024 * 1024) throw new Error('请选择不超过 4 MiB 的 XML 或 ASS 弹幕文件。');
    return api(`${base}/danmaku`, {content: await file.text(), streamer: streamer.trim() || undefined});
  }, onSuccess: () => {setNotice('弹幕已导入，请重新分析以更新评分。'); refresh();}});
  const pending = analyze.isPending || generate.isPending || upload.isPending || working(store?.state) || working(clips.data?.state);
  const stale = store?.state === 'stale' || (store?.document_revision !== undefined && store.document_revision !== documentRevision);
  const segments = store?.segments ?? [];
  const sorted = sort === 'score' ? [...segments].sort((a,b) => (b.score ?? -1) - (a.score ?? -1) || a.index - b.index) : segments;
  const error = topics.error ?? clips.error ?? danmaku.error ?? analyze.error ?? generate.error ?? upload.error;
  return <section className="topic-workbench" aria-label="高光分析与切片">
    <h3>高光分析与切片</h3>
    <p className="companion-footnote">从已保存的字幕筛选话题，生成标题与摘要；分析会使用当前 AI 设置的额度。评分是本场相对排序，仍需预览确认。</p>
    <form className="cue-style-fields" onSubmit={event => {event.preventDefault(); analyze.mutate();}}>
      <label className="ny-field">分析开始<input className="ny-input" placeholder="00:00 或秒数" value={start} onChange={event => setStart(event.target.value)} /></label>
      <label className="ny-field">分析结束<input className="ny-input" placeholder="留空至结尾" value={end} onChange={event => setEnd(event.target.value)} /></label>
      <label className="ny-field">最多话题数<input className="ny-input" type="number" min={1} max={100} required value={limit}
        onChange={event => setLimit(event.target.valueAsNumber)} /></label>
      <button className="ny-button ny-button--primary" disabled={pending} type="submit">分析高光话题</button>
    </form>
    <details><summary>弹幕与评分输入 · {danmaku.data?.count ?? 0} 条</summary>
      <p className="companion-footnote">导入 XML／ASS 弹幕可评估互动热度。缺弹幕时不显示完整互动评分，音频兴奋度仅供参考。</p>
      <label className="ny-field">主播／系列名称（选填）<input className="ny-input" maxLength={128} value={streamer} onChange={event => setStreamer(event.target.value)} placeholder="同一名称共用热词画像" /></label>
      <label className="ny-field">导入弹幕<input type="file" accept=".xml,.ass" disabled={pending} onChange={event => {const file = event.target.files?.[0]; if (file) upload.mutate(file); event.target.value = '';}} /></label>
    </details>
    {notice && <p role="status">{notice}</p>}
    {error && <p className="companion-error" role="alert">{error.message}</p>}
    {store && <p role="status">分析：{states[store.state] ?? store.state} · 文档版本 {store.document_revision ?? '—'}</p>}
    {store?.state === 'completed' && <p className="companion-footnote">音频因子：{store.audio_state === 'available' ? '可用' : store.audio_state === 'truncated' ? '超长音频仅分析前 12 小时' : '不可用，评分未使用音频因子'}{store.streamer ? ` · 主播画像：${store.streamer}` : ''}</p>}
    {stale && <p className="companion-error">字幕已修改，请重新分析。</p>}
    {store?.error && <p role="alert" className="companion-error">{store.error}</p>}
    {!!store?.vocabulary?.length && <p>本场热词：{store.vocabulary.join(' · ')}</p>}
    {store?.quotes?.map((quote, index) => <button type="button" className="ny-button ny-button--quiet" key={index}
      disabled={quote.start === undefined} onClick={() => {if (quote.start !== undefined) onSeek(quote.start);}}>金句：{quote.text}</button>)}
    {!!segments.length && <>
      <label className="ny-field">话题排序<select className="ny-input" value={sort} onChange={event => setSort(event.target.value)}><option value="time">时间顺序</option><option value="score">评分从高到低</option></select></label>
      <p className="companion-footnote">已选 {selected.length} 段；组合视频按勾选先后排列。</p>
      <div className="topic-results">{sorted.map(segment => <article className="topic-result" key={segment.index}>
        <label className="topic-selection"><input type="checkbox" checked={selected.includes(segment.index)} disabled={pending}
          aria-label={`选择${segment.title}`} onChange={() => setSelected(current => current.includes(segment.index) ? current.filter(index => index !== segment.index) : [...current, segment.index])} />
          <strong>{selected.includes(segment.index) ? `${selected.indexOf(segment.index) + 1}. ` : ''}{segment.title}</strong></label>
        <button type="button" className="ny-button ny-button--quiet" onClick={() => onSeek(segment.start_seconds)}>{time(segment.start_seconds)} — {time(segment.end_seconds)} · 预览</button>
        <p>{segment.summary}</p>
        <p className="companion-footnote">{segment.score == null ? '互动评分不可用' : `相对评分 ${segment.score} 分`}{segment.dm_count != null && ` · 弹幕 ${segment.dm_count} 条`}{segment.loudness_db != null && ` · 响度 ${segment.loudness_db} dBFS`}</p>
        {!!segment.hot_words?.length && <p className="companion-footnote">热词：{segment.hot_words.join(' · ')}</p>}
        {!!segment.risk_terms?.length && <p className="companion-error">需复核词：{segment.risk_terms.join('、')}</p>}
      </article>)}</div>
      <div className="cue-style-fields">
        <label className="ny-field">生成方式<select className="ny-input" value={mode} onChange={event => setMode(event.target.value === 'combined' ? 'combined' : 'separate')}><option value="separate">分别生成</option><option value="combined">组合视频</option></select></label>
        <label className="ny-field">烧录字幕<select className="ny-input" value={variant} onChange={event => {switch (event.target.value) {case 'zh': setVariant('zh'); break; case 'bilingual': setVariant('bilingual'); break; default: setVariant('original');}}}><option value="original">原文</option><option value="zh">中文</option><option value="bilingual">双语</option></select></label>
      </div>
      <button className="ny-button ny-button--primary" disabled={pending || stale || store?.state !== 'completed' || !selected.length} onClick={() => generate.mutate()}>生成选中视频</button>
    </>}
    {clips.data && clips.data.state !== 'not_started' && <p role="status">视频：{states[clips.data.state] ?? clips.data.state}</p>}
    {clips.data?.error && <p role="alert" className="companion-error">{clips.data.error}</p>}
    {clips.data?.items?.map(item => item.url ? <a className="ny-button" key={item.index} href={item.url} download>下载话题 {item.index + 1}</a> : item.error ? <p key={item.index} role="alert">{item.error}</p> : null)}
    {clips.data?.combined?.url && <a className="ny-button" href={clips.data.combined.url} download>下载组合视频</a>}
  </section>;
}
