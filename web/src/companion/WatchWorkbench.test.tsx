import {QueryClient, QueryClientProvider} from '@tanstack/react-query';
import {fireEvent, render, screen, waitFor, within} from '@testing-library/react';
import {afterEach, beforeEach, expect, it, vi} from 'vitest';
import {TopicSegmentsPanel} from './TopicSegmentsPanel';

const segments = [0, 1].map(index => ({index, start_seconds: index * 30, end_seconds: (index + 1) * 30,
  title: `片段${index + 1}`, summary: '原始字幕中的话题', score: index ? 80 : 60}));
beforeEach(() => localStorage.clear());
afterEach(() => vi.unstubAllGlobals());
function setup(extra: Record<string, unknown> = {}) {
  const client = new QueryClient({defaultOptions: {queries: {retry: false}, mutations: {retry: false}}});
  const posts: {url: string; body: unknown}[] = [];
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, options?: RequestInit) => {
    const url = String(input);
    if (options?.method === 'POST') {posts.push({url, body: JSON.parse(String(options.body))});return new Response('{"state":"queued","operation_id":"next"}');}
    if (url.endsWith('/topic-segments')) return new Response(JSON.stringify({state: 'completed', operation_id: 'first', document_revision: 2, created_at: 1, segments, ...extra}));
    return new Response(JSON.stringify(url.endsWith('/danmaku') ? {count: 0} : {state: 'not_started', items: []}));
  }));
  const props = {jobId: 'task', documentRevision: 2, duration: 60, prepare: async () => null, onSeek: vi.fn(), onPreview: vi.fn()};
  const mount = (jobId = props.jobId, queryClient = client) => render(<QueryClientProvider client={queryClient}><TopicSegmentsPanel {...props} jobId={jobId}/></QueryClientProvider>);
  return {mount, posts, props, client};
}

it('retains analysis inputs and selection when the same task panel is reopened', async () => {
  // Given a selected candidate and a draft analysis range.
  const {mount} = setup();const first = mount();
  await screen.findByText('片段1');
  fireEvent.click(screen.getByText('分析选项'));
  fireEvent.change(screen.getByLabelText('分析开始'), {target: {value: '00:10'}});
  fireEvent.click(screen.getByLabelText('选择片段2'));
  // When the same task panel is remounted with its existing query client.
  first.unmount();mount();
  // Then both the draft and selected candidate remain.
  expect(await screen.findByLabelText('选择片段2')).toBeChecked();
  expect(screen.getByLabelText('分析开始')).toHaveValue('00:10');
});

it('isolates task drafts and clears reviewed ranges when a new analysis replaces them', async () => {
  const analysis = {operation_id: 'first'};
  const {mount, client, props} = setup(analysis);const first = mount();
  await screen.findByText('片段1');
  fireEvent.click(screen.getByLabelText('选择片段2'));
  fireEvent.click(screen.getByRole('button', {name: '预览片段2'}));
  fireEvent.change(await screen.findByLabelText('高光入点'), {target: {value: '00:35'}});
  fireEvent.click(screen.getByRole('button', {name: '应用片段范围'}));
  await waitFor(() => expect(screen.getByLabelText('高光入点')).toHaveValue('00:35.0'));
  first.unmount();const other = mount('other');
  expect(await screen.findByLabelText('选择片段2')).not.toBeChecked();
  other.unmount();props.onPreview.mockClear();mount();
  expect(await screen.findByLabelText('选择片段2')).toBeChecked();
  expect(screen.getByLabelText('高光入点')).toHaveValue('00:35.0');
  await waitFor(() => expect(props.onPreview).toHaveBeenLastCalledWith(expect.objectContaining({start_seconds: 35, end_seconds: 60})));
  analysis.operation_id = 'replacement';
  await client.invalidateQueries({queryKey: ['companion', 'topics', 'task']});
  await waitFor(() => expect(screen.getByLabelText('选择片段2')).not.toBeChecked());
  expect(screen.queryByLabelText('高光入点')).not.toBeInTheDocument();
  expect(props.onPreview).toHaveBeenLastCalledWith(null);
});

it('rejects an inverted trim without changing the candidate preview', async () => {
  const {mount, props} = setup();mount();await screen.findByText('片段1');
  fireEvent.click(screen.getByRole('button', {name: '预览片段1'}));
  fireEvent.change(await screen.findByLabelText('高光出点'), {target: {value: '00:00'}});
  fireEvent.click(screen.getByRole('button', {name: '应用片段范围'}));
  expect(screen.getByRole('alert')).toHaveTextContent('出点须晚于入点');
  expect(props.onSeek).toHaveBeenCalledTimes(1);
});

it('shows partial coverage instead of claiming a complete analysis', async () => {
  // Given only half of the source cues were analyzed.
  const {mount} = setup({total_cues: 200, covered_cues: 100, truncated: true});
  // When its completed analysis is displayed.
  mount();
  // Then incomplete coverage is explicit.
  expect(await screen.findByText(/仅覆盖 100\/200 条字幕/)).toBeVisible();
});

it('confirms adjusted ranges and ordered selection before admitting an export', async () => {
  // Given two candidates selected in reverse order with the first range trimmed.
  const {mount, posts} = setup();mount();
  await screen.findByText('片段1');
  fireEvent.click(screen.getByLabelText('选择片段2'));
  fireEvent.click(screen.getByLabelText('选择片段1'));
  fireEvent.click(screen.getByRole('button', {name: '预览片段1'}));
  fireEvent.change(await screen.findByLabelText('高光入点'), {target: {value: '00:01'}});
  fireEvent.click(screen.getByRole('button', {name: '应用片段范围'}));
  // When generation is requested, then no export is admitted before confirmation.
  fireEvent.click(screen.getByRole('button', {name: '生成选中视频'}));
  expect(posts).toHaveLength(0);
  const dialog = screen.getByRole('dialog', {name: '确认生成高光'});
  expect(within(dialog).getByText(/共 2 段/)).toBeVisible();
  fireEvent.click(within(dialog).getByRole('button', {name: '加入生成队列'}));
  await waitFor(() => expect(posts).toHaveLength(1));
  expect(posts[0].body).toMatchObject({indices: [1, 0], ranges: [{index: 0, start_seconds: 1, end_seconds: 30}]});
});

it('explains an empty completed analysis without offering generation', async () => {
  // Given analysis completed without candidates.
  const {mount} = setup({segments: []});
  // When results are opened.
  mount();
  // Then the operator sees a specific empty result and a disabled export.
  expect(await screen.findByText('没有找到高光候选')).toBeVisible();
  expect(screen.getByRole('button', {name: '生成选中视频'})).toBeDisabled();
});

it('restores reviewed ranges after a same-origin reload and resets them only for a replacement analysis', async () => {
  const analysis = {operation_id: 'original'};
  const {mount} = setup(analysis);const first = mount();
  fireEvent.click(await screen.findByLabelText('选择片段2'));
  fireEvent.click(screen.getByRole('button', {name: '预览片段2'}));
  fireEvent.change(await screen.findByLabelText('高光入点'), {target: {value: '00:35'}});
  fireEvent.click(screen.getByRole('button', {name: '应用片段范围'}));
  first.unmount();
  const reloaded = new QueryClient({defaultOptions: {queries: {retry: false}}});mount('task', reloaded);
  expect(await screen.findByLabelText('选择片段2')).toBeChecked();
  expect(screen.getByLabelText('高光入点')).toHaveValue('00:35.0');
  analysis.operation_id = 'replacement';await reloaded.invalidateQueries({queryKey: ['companion', 'topics', 'task']});
  await waitFor(() => expect(screen.getByLabelText('选择片段2')).not.toBeChecked());
  expect(screen.queryByLabelText('高光入点')).not.toBeInTheDocument();
});
it('does not display a null revision as an editing version or stale document', async () => {
  const {mount} = setup({document_revision: null});mount();await screen.findByText('片段1');
  expect(screen.queryByText(/vnull/)).not.toBeInTheDocument();
  expect(screen.queryByText(/字幕已修改/)).not.toBeInTheDocument();
});
