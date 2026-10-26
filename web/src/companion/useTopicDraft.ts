import {useState} from 'react';
import {skipToken, useQuery, useQueryClient} from '@tanstack/react-query';

export interface TopicRange {
  readonly start_seconds: number;
  readonly end_seconds: number;
}
export interface TopicDraft {
  readonly start: string;
  readonly end: string;
  readonly limit: number;
  readonly selected: readonly number[];
  readonly sort: 'time' | 'score';
  readonly mode: 'separate' | 'combined';
  readonly variant: 'original' | 'zh' | 'bilingual';
  readonly streamer: string;
  readonly current: number | null;
  readonly ranges: Readonly<Partial<Record<number, TopicRange>>>;
  readonly analysisKey: string | null;
  readonly optionsOpen: boolean;
}
const initialDraft: TopicDraft = {start: '', end: '', limit: 30, selected: [], sort: 'time',
  mode: 'separate', variant: 'bilingual', streamer: '', current: null, ranges: {}, analysisKey: null, optionsOpen: false};

// shortcut: drafts are browser-origin scoped; use task storage when native port changes must preserve review.
const storageKey = (jobId: string) => `nyaru-topic-draft-v1:${jobId}`;
function isDraft(value: unknown): value is TopicDraft {
  if (!value || typeof value !== 'object') return false;
  const d = value;
  return 'start' in d && typeof d.start === 'string' && 'end' in d && typeof d.end === 'string'
    && 'limit' in d && typeof d.limit === 'number' && Number.isInteger(d.limit) && d.limit >= 1 && d.limit <= 100
    && 'selected' in d && Array.isArray(d.selected) && d.selected.every(index => Number.isInteger(index) && index >= 0)
    && 'sort' in d && (d.sort === 'time' || d.sort === 'score')
    && 'mode' in d && (d.mode === 'separate' || d.mode === 'combined')
    && 'variant' in d && (d.variant === 'original' || d.variant === 'zh' || d.variant === 'bilingual')
    && 'streamer' in d && typeof d.streamer === 'string'
    && 'current' in d && (d.current === null || typeof d.current === 'number' && Number.isInteger(d.current) && d.current >= 0)
    && 'analysisKey' in d && (d.analysisKey === null || typeof d.analysisKey === 'string')
    && 'optionsOpen' in d && typeof d.optionsOpen === 'boolean'
    && 'ranges' in d && !!d.ranges && typeof d.ranges === 'object' && !Array.isArray(d.ranges)
    && Object.entries(d.ranges).every(([key, range]) => /^\d+$/.test(key) && range && typeof range === 'object'
      && 'start_seconds' in range && typeof range.start_seconds === 'number' && Number.isFinite(range.start_seconds) && range.start_seconds >= 0
      && 'end_seconds' in range && typeof range.end_seconds === 'number' && Number.isFinite(range.end_seconds) && range.end_seconds > range.start_seconds);
}
function restore(jobId: string): TopicDraft {
  try {
    const raw = localStorage.getItem(storageKey(jobId));
    if (!raw) return initialDraft;
    const saved: unknown = JSON.parse(raw);
    return isDraft(saved) ? saved : initialDraft;
  } catch (error) {
    if (error instanceof Error || error instanceof DOMException) return initialDraft;
    throw error;
  }
}

export function useTopicDraft(jobId: string) {
  const client = useQueryClient();
  const [persistenceError, setPersistenceError] = useState('');
  const key = ['companion', 'topic-draft', jobId];
  const query = useQuery({queryKey: key, queryFn: skipToken, initialData: () => restore(jobId), gcTime: Infinity});
  function update(patch: Partial<TopicDraft> | ((draft: TopicDraft) => Partial<TopicDraft>)) {
    const draft = client.getQueryData<TopicDraft>(key) ?? initialDraft;
    const next = {...draft, ...(typeof patch === 'function' ? patch(draft) : patch)};
    client.setQueryData<TopicDraft>(key, next);
    try {localStorage.setItem(storageKey(jobId), JSON.stringify(next));setPersistenceError('');}
    catch (error) {
      if (!(error instanceof Error) && !(error instanceof DOMException)) throw error;
      setPersistenceError('浏览器无法保存高光审阅；当前选择仍保留，重新打开窗口后可能丢失。');
    }
  }
  return {draft: query.data ?? initialDraft, update, persistenceError};
}
