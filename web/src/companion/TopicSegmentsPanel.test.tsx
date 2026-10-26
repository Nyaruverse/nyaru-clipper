import {fireEvent, render, screen, waitFor} from '@testing-library/react';
import {QueryClient, QueryClientProvider} from '@tanstack/react-query';
import {afterEach, expect, it, vi} from 'vitest';
import {TopicSegmentsPanel} from './TopicSegmentsPanel';

const segments = [0, 1].map(index => ({index, start_seconds: index * 30, end_seconds: (index + 1) * 30,
  title: `话题${index + 1}`, summary: '字幕里的内容', score: index * 30 + 40, hot_words: []}));
afterEach(() => vi.unstubAllGlobals());
function setup(revision = 2, state = 'completed') {
  const fetcher = vi.fn(async (input: RequestInfo | URL, options?: RequestInit) => {
    const path = String(input);
    if (options?.method === 'POST') return new Response(JSON.stringify({state: 'queued', operation_id: 'operation'}));
    if (path.endsWith('/topic-segments')) return new Response(JSON.stringify({state, document_revision: state === 'not_started' ? 0 : 2, segments}));
    if (path.endsWith('/topic-clips')) return new Response(JSON.stringify({state: 'not_started', items: []}));
    return new Response(JSON.stringify({count: 0, source: null}));
  });
  vi.stubGlobal('fetch', fetcher);
  const client = new QueryClient({defaultOptions: {queries: {retry: false}, mutations: {retry: false}}});
  const prepare = vi.fn(async () => null);
  render(<QueryClientProvider client={client}><TopicSegmentsPanel jobId="task" documentRevision={revision} prepare={prepare} onSeek={vi.fn()} /></QueryClientProvider>);
  return {fetcher, prepare};
}
it('exports selected topics in click order even when displayed by score', async () => {
  const {fetcher, prepare} = setup();
  await screen.findByText('话题1');
  fireEvent.change(screen.getByLabelText('话题排序'), {target: {value: 'score'}});
  fireEvent.click(screen.getByLabelText('选择话题2'));
  fireEvent.click(screen.getByLabelText('选择话题1'));
  await waitFor(() => expect(screen.getByRole('button', {name: '生成选中视频'})).toBeEnabled());
  fireEvent.click(screen.getByRole('button', {name: '生成选中视频'}));
  fireEvent.click(await screen.findByRole('button', {name: '加入生成队列'}));
  await waitFor(() => expect(fetcher.mock.calls.some(([path, options]) => String(path).endsWith('/topic-clips') && options?.method === 'POST')).toBe(true));
  const call = fetcher.mock.calls.find(([path, options]) => String(path).endsWith('/topic-clips') && options?.method === 'POST');
  expect(JSON.parse(String(call?.[1]?.body)).indices).toEqual([1, 0]);
  expect(prepare).toHaveBeenCalled();
});
it('rejects export of a topic analysis from an older editing revision', async () => {
  setup(3);
  await screen.findByText('话题1');
  fireEvent.click(screen.getByLabelText('选择话题1'));
  expect(screen.getByRole('button', {name: '生成选中视频'})).toBeDisabled();
  expect(screen.getByText(/字幕已修改/)).toBeInTheDocument();
});
it('does not claim subtitles changed before the first analysis', async () => {
  setup(3, 'not_started');
  await screen.findByText(/尚未分析/);
  expect(screen.queryByText(/字幕已修改/)).not.toBeInTheDocument();
});
