import {useMutation, useQueryClient} from '@tanstack/react-query';
import {DndContext, PointerSensor, closestCenter, useSensor, useSensors} from '@dnd-kit/core';
import {SortableContext, arrayMove, useSortable, verticalListSortingStrategy} from '@dnd-kit/sortable';
import {CSS} from '@dnd-kit/utilities';
import {GripVertical} from 'lucide-react';
import {QueueKeyboardSensor, queueKeyboardCoordinates} from '../workstation/features/queue/QueueList';
import {workstationKeys} from '../workstation/api/queryKeys';
import {admissions, cancel, reorder, retry, useUnifiedOperations, waiting, type Operation, type OperationsSnapshot} from './unifiedOperations';

const kinds = {process_recording: '录像处理', process_live: '实时录播', translate: '字幕翻译', export: '导出', analyze_topics: '高光分析', export_topics: '话题视频'};
const states = {queued: '等待', paused: '已暂停', running: '运行中', succeeded: '已完成', failed: '失败', interrupted: '已中断', cancelled: '已取消'};
type Action = (work: () => Promise<OperationsSnapshot>) => void;
const failures: Record<string, string> = {
  external_outcome_unknown_possible_repeat_charge: '外部请求结果不确定；重试前请确认可能重复计费。',
  asr_model_unavailable_offline: '缺少本地模型缓存，请准备模型后重试。',
  upload_incomplete_reselect_file: '录像导入未完成，请重新选择文件创建任务。',
  cancelled: '操作已取消，已发布结果保留。',
};

function Row({operation, disabled, onSelect, act}: {operation: Operation; disabled: boolean; onSelect: (id: string) => void; act: Action}) {
  const waitingState = operation.state === 'queued' || operation.state === 'paused';
  const sortable = useSortable({id: operation.id, disabled: disabled || operation.state !== 'queued'});
  const name = `${kinds[operation.kind]} ${operation.task_id.slice(0, 8)}`;
  function requestRetry() {
    const unknown = operation.failure_code === 'external_outcome_unknown_possible_repeat_charge';
    if (unknown && !window.confirm('上次外部请求的结果不确定，重新请求可能重复计费。确认后才会重新排队，是否继续？')) return;
    act(() => retry(operation, unknown));
  }
  return <tr ref={sortable.setNodeRef} data-queue-target={sortable.isOver && !sortable.isDragging ? 'true' : undefined} style={{transform: CSS.Transform.toString(sortable.transform), transition: sortable.transition}}>
    <td><button className="ny-button" ref={sortable.setActivatorNodeRef} {...sortable.attributes} {...sortable.listeners} disabled={disabled || operation.state !== 'queued'} aria-label={`拖动排序 ${name}`}><GripVertical size={16}/></button></td>
    <td><button className="ny-button" onClick={() => onSelect(operation.task_id)}>{name}</button><small>尝试 {operation.attempt}</small></td>
    <td data-label="状态">{states[operation.state]}{operation.cancel_requested && ' · 等待进程退出'}{operation.failure_code && <><small>{failures[operation.failure_code] ?? '处理未完成，已有结果保留；请检查诊断后重试。'}</small><details><summary>诊断代码</summary><code>{operation.failure_code}</code></details></>}</td>
    <td data-label="优先级"><select className="ny-input" aria-label={`${name} 优先级`} value={operation.priority} disabled={disabled || !waitingState} onChange={e => act(() => waiting(operation, operation.state === 'paused' ? 'paused' : 'queued', Number(e.target.value)))}>
      {[-100, -10, 0, 10, 100, operation.priority].filter((v, i, all) => all.indexOf(v) === i).sort((a,b) => b-a).map(value => <option key={value} value={value}>{value}</option>)}
    </select></td>
    <td data-label="操作"><div className="unified-queue-actions">
      {waitingState && <button className="ny-button" disabled={disabled} onClick={() => act(() => waiting(operation, operation.state === 'queued' ? 'paused' : 'queued'))}>{operation.state === 'queued' ? '暂停' : '排队'}</button>}
      {(waitingState || operation.state === 'running') && <button className="ny-button" disabled={disabled || operation.cancel_requested} onClick={() => act(() => cancel(operation))}>取消</button>}
      {['failed', 'interrupted', 'cancelled'].includes(operation.state) && operation.failure_code !== 'upload_incomplete_reselect_file' && <button className="ny-button" disabled={disabled} onClick={requestRetry}>重试</button>}
    </div></td>
  </tr>;
}

export function UnifiedQueue({onSelect}: {onSelect: (id: string) => void}) {
  const query = useUnifiedOperations(true);
  const client = useQueryClient();
  const mutation = useMutation({mutationFn: (work: () => Promise<OperationsSnapshot>) => work(),
    onSuccess: snapshot => client.setQueryData(workstationKeys.operations, snapshot),
    onSettled: () => client.invalidateQueries({queryKey: workstationKeys.operations})});
  const snapshot = query.data;
  const queued = snapshot?.operations.filter(item => item.state === 'queued') ?? [];
  const ids = queued.map(item => item.id);
  const sensors = useSensors(useSensor(PointerSensor, {activationConstraint: {distance: 6}}), useSensor(QueueKeyboardSensor, {coordinateGetter: queueKeyboardCoordinates(ids)}));
  const disabled = mutation.isPending || !!snapshot?.recovering;
  return <section className="companion-panel unified-queue" aria-label="统一任务队列">
    <div className="companion-section-heading"><h2>任务队列</h2>{snapshot && <button className="ny-button" disabled={disabled} onClick={() => mutation.mutate(() => admissions(snapshot))}>{snapshot.paused ? '启动队列' : '暂停后续任务'}</button>}</div>
    <p role="status">{query.isLoading ? '正在读取任务队列…' : snapshot?.recovering ? '正在恢复产物，队列暂不可操作' : snapshot?.paused ? '队列已暂停，新任务会保留等待。启动队列后依次运行。' : '单个任务依次运行；暂停队列不打断当前任务。'} 同一优先级内可拖动排序，也可聚焦拖动按钮后按空格、方向键和回车。</p>
    {(query.error || mutation.error) && <p className="companion-error" role="alert">{(mutation.error ?? query.error)?.message}</p>}
    <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={({active, over}) => {
      if (!snapshot || !over || active.id === over.id || disabled) return;
      const from = ids.indexOf(String(active.id)), to = ids.indexOf(String(over.id));
      if (from < 0 || to < 0 || queued[from].priority !== queued[to].priority) return;
      mutation.mutate(() => reorder(snapshot, arrayMove(ids, from, to)));
    }}><SortableContext items={ids} strategy={verticalListSortingStrategy}>
      <div className="unified-queue-scroll"><table><thead><tr><th>排序</th><th>任务</th><th>状态</th><th>优先级</th><th>操作</th></tr></thead><tbody>
        {snapshot?.operations.map(operation => <Row key={operation.id} operation={operation} disabled={disabled} onSelect={onSelect} act={work => mutation.mutate(work)}/>)}
      </tbody></table></div>
    </SortableContext></DndContext>
    {snapshot && !snapshot.operations.length && <p className="companion-muted">还没有排队的操作。</p>}
  </section>;
}
