import * as Dialog from '@radix-ui/react-dialog';
import {ArrowDown, ArrowUp, X} from 'lucide-react';
import {time} from './companionApi';
import type {TopicDraft, TopicRange} from './useTopicDraft';

interface SelectedTopic extends TopicRange {readonly index: number;readonly title: string}
interface Props {
  readonly draft: TopicDraft;
  readonly items: readonly SelectedTopic[];
  readonly disabled: boolean;
  readonly pending: boolean;
  readonly open: boolean;
  readonly problem: string | null;
  readonly onOpen: (open: boolean) => void;
  readonly update: (patch: Partial<TopicDraft>) => void;
  readonly onGenerate: () => void;
}
export function TopicSelection({draft, items, disabled, pending, open, problem, onOpen, update, onGenerate}: Props) {
  const seconds = items.reduce((total, item) => total + item.end_seconds - item.start_seconds, 0);
  function move(index: number, offset: number) {
    const selected = [...draft.selected], destination = index + offset;
    if (destination < 0 || destination >= selected.length) return;
    const item = selected.splice(index, 1)[0];
    if (item === undefined) return;
    selected.splice(destination, 0, item);update({selected});
  }
  return <Dialog.Root open={open} onOpenChange={onOpen}>
    <footer className="topic-selection-footer"><div><strong>已选 {items.length} 段 · {time(seconds)}</strong><p className="companion-muted">按确认列表中的顺序生成</p></div>
      <Dialog.Trigger className="ny-button ny-button--primary" disabled={disabled || !items.length}>生成选中视频</Dialog.Trigger>
    </footer>
    <Dialog.Portal container={document.querySelector<HTMLElement>('.ny-companion') ?? undefined}>
      <Dialog.Overlay className="topic-export-overlay"/>
      <Dialog.Content className="topic-export-dialog" aria-describedby="topic-export-description">
        <div className="companion-section-heading"><Dialog.Title>确认生成高光</Dialog.Title><Dialog.Close className="ny-button ny-button--quiet" aria-label="关闭生成确认"><X size={18}/></Dialog.Close></div>
        <Dialog.Description id="topic-export-description">共 {items.length} 段 · {time(seconds)}。范围、顺序和字幕语言确认后才会加入统一队列。</Dialog.Description>
        <ol className="topic-export-order">{items.map((item, index) => <li key={item.index}><div><strong>{item.title}</strong><p>{time(item.start_seconds)} — {time(item.end_seconds)}</p></div><div className="topic-order-actions">
          <button className="ny-button" aria-label={`上移${item.title}`} disabled={pending || index === 0} onClick={() => move(index, -1)}><ArrowUp size={16}/></button>
          <button className="ny-button" aria-label={`下移${item.title}`} disabled={pending || index === items.length - 1} onClick={() => move(index, 1)}><ArrowDown size={16}/></button>
        </div></li>)}</ol>
        <label className="ny-field">生成方式<select className="ny-input" value={draft.mode} disabled={pending} onChange={event => update({mode: event.target.value === 'combined' ? 'combined' : 'separate'})}><option value="separate">分别生成</option><option value="combined">组合视频</option></select></label>
        <label className="ny-field">烧录字幕<select className="ny-input" value={draft.variant} disabled={pending} onChange={event => {switch (event.target.value) {case 'zh': update({variant: 'zh'});break;case 'bilingual': update({variant: 'bilingual'});break;case 'original': update({variant: 'original'});break;}}}><option value="original">原文</option><option value="zh">中文</option><option value="bilingual">双语</option></select></label>
        {problem && <p role="alert" className="companion-error">{problem}</p>}
        <div className="topic-confirm-actions"><Dialog.Close className="ny-button">继续调整</Dialog.Close><button className="ny-button ny-button--primary" disabled={disabled || pending || !items.length || !!problem} onClick={onGenerate}>{pending ? '正在提交…' : '加入生成队列'}</button></div>
      </Dialog.Content>
    </Dialog.Portal>
  </Dialog.Root>;
}
