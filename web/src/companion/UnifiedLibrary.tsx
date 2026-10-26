import {useEffect, useState} from 'react';
import {skipToken, useMutation, useQuery, useQueryClient} from '@tanstack/react-query';
import type {components} from '../generated/api-schema';
import {client, result} from './unifiedOperations';

type Item = components['schemas']['LibraryItem'];
const conflict = '任务元数据已变化，输入已保留；请重新载入后再保存。';
type Draft = {title: string; tags: string; version: string; dirty: boolean};
export const metadataDraftKey = ['companion', 'metadata-draft'];
export type {Draft as MetadataDraft};
const savedDraft = (item: Item): Draft => ({title: item.title ?? '', tags: item.tags.join(', '), version: item.version, dirty: false});

function Metadata({item}: {item: Item}) {
  const queries = useQueryClient();
  const key = [...metadataDraftKey, item.task_id];
  const query = useQuery({queryKey: key, queryFn: skipToken, initialData: () => savedDraft(item), gcTime: Infinity});
  const draft = query.data ?? savedDraft(item);
  const {title, tags, version, dirty} = draft;
  const edit = (patch: Partial<Draft>) => queries.setQueryData<Draft>(key, {...draft, ...patch});
  useEffect(() => {if (!dirty) queries.setQueryData(key, savedDraft(item));}, [item.version]);
  const mutation = useMutation({mutationFn: async (patch: {title?: string; tags?: string[]; archived?: boolean}) =>
    result(await client.PATCH('/api/v2/library/{task_id}', {params: {path: {task_id: item.task_id}}, body: {expected_version: version, ...patch}}), conflict),
    onSuccess: saved => {queries.setQueryData(key, savedDraft(saved));void queries.invalidateQueries({queryKey: ['companion', 'library']});void queries.invalidateQueries({queryKey: ['companion', 'job', item.task_id]});}});
  return <details className="companion-metadata"><summary>任务标题与标签</summary>
    <label className="ny-field">任务标题<input className="ny-input" value={title} disabled={mutation.isPending} maxLength={120} onChange={e => edit({title: e.target.value, dirty: true})}/></label>
    <label className="ny-field">任务标签<input className="ny-input" value={tags} disabled={mutation.isPending} placeholder="多个标签用逗号分隔" onChange={e => edit({tags: e.target.value, dirty: true})}/></label>
    {dirty && <p className="companion-muted">尚未保存。切换任务或筛选时会保留草稿，关闭本窗口后草稿会丢失。</p>}
    <div className="unified-queue-actions"><button className="ny-button" disabled={!dirty || mutation.isPending} onClick={() => mutation.mutate({title, tags: tags.split(/[,，]/).map(value => value.trim()).filter(Boolean)})}>保存任务信息</button>
      <button className="ny-button" disabled={mutation.isPending || dirty} onClick={() => mutation.mutate({archived: !item.archived})}>{item.archived ? '取消归档' : '归档任务'}</button></div>
    {mutation.error && <><p className="companion-error" role="alert">{mutation.error.message}</p><button className="ny-button" onClick={() => {if (window.confirm('重新载入已保存的标题与标签？当前输入将被替换。')) {queries.setQueryData(key, savedDraft(item));mutation.reset();void queries.invalidateQueries({queryKey: ['companion', 'library']});}}}>重新载入任务信息</button></>}
  </details>;
}

export function UnifiedLibrary({selectedId, onSelect}: {selectedId: string | null; onSelect: (id: string) => void}) {
  const [search, setSearch] = useState('');
  const [tag, setTag] = useState('');
  const [archived, setArchived] = useState(false);
  const [page, setPage] = useState(1);
  const query = useQuery({queryKey: ['companion', 'library', search, tag, archived, page], queryFn: async ({signal}) =>
    result(await client.GET('/api/v2/library', {signal, params: {query: {search, tag: tag || undefined, include_archived: archived, page, page_size: 25}}})), refetchInterval: 15000});
  const selected = query.data?.items.find(item => item.task_id === selectedId);
  return <>
    <label className="ny-field">搜索任务<input className="ny-input" value={search} placeholder="按标题或任务编号搜索" onChange={e => {setSearch(e.target.value);setPage(1);}}/></label>
    <label className="ny-field">筛选标签<input className="ny-input" value={tag} onChange={e => {setTag(e.target.value);setPage(1);}}/></label>
    <label><input type="checkbox" checked={archived} onChange={e => {setArchived(e.target.checked);setPage(1);}}/> 显示归档任务</label>
    {query.isLoading && <p role="status">正在读取任务记录…</p>}
    {query.error && <p className="companion-error" role="alert">{query.error.message}</p>}
    {query.data?.items.map(item => <button key={item.task_id} className="companion-history-item" aria-pressed={selectedId === item.task_id} onClick={() => onSelect(item.task_id)}><span><strong>{item.title || '未命名任务'}</strong><small>{item.task_id.slice(0, 8)}{item.tags.length ? ' · ' + item.tags.join('、') : ''}</small></span>{item.archived && <span>已归档</span>}</button>)}
    {query.data?.total === 0 && <p className="companion-muted">没有匹配的任务，请调整筛选或创建新任务。</p>}
    {query.data && query.data.total > 25 && <div className="unified-queue-actions"><button className="ny-button" disabled={page === 1} onClick={() => setPage(page - 1)}>上一页</button><span>第 {page} 页</span><button className="ny-button" disabled={page * 25 >= query.data.total} onClick={() => setPage(page + 1)}>下一页</button></div>}
    {selected && <Metadata key={selected.task_id} item={selected}/>}
  </>;
}
