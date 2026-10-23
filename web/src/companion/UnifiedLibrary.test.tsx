import {QueryClient, QueryClientProvider} from '@tanstack/react-query';
import {fireEvent, render, screen} from '@testing-library/react';
import {afterEach, expect, it, vi} from 'vitest';
import {UnifiedLibrary} from './UnifiedLibrary';

afterEach(() => vi.unstubAllGlobals());

it('keeps the original draft and version across filters, selection and drawer reopening', async () => {
  const first = {task_id: 'a'.repeat(32), title: '任务 A', tags: [], version: 'original', archived: false};
  const second = {...first, task_id: 'b'.repeat(32), title: '任务 B'};
  let submitted: unknown;
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
    const request = input instanceof Request ? input : new Request(input);
    if (request.method === 'PATCH') {
      submitted = await request.json();
      return Response.json({detail: 'stale'}, {status: 409});
    }
    return Response.json({items: new URL(request.url).searchParams.get('search') ? [second] : [first, second], total: 2});
  }));
  const client = new QueryClient({defaultOptions: {queries: {retry: false}}});
  const view = (id: string) => <QueryClientProvider client={client}><UnifiedLibrary selectedId={id} onSelect={() => {}}/></QueryClientProvider>;
  const mounted = render(view(first.task_id));
  fireEvent.click(await screen.findByText('任务标题与标签'));
  fireEvent.change(screen.getByLabelText('任务标题'), {target: {value: '未保存草稿'}});
  fireEvent.change(screen.getByLabelText('搜索任务'), {target: {value: 'B'}});
  await screen.findByRole('button', {name: /任务 B/});
  mounted.rerender(view(second.task_id));
  fireEvent.change(screen.getByLabelText('搜索任务'), {target: {value: ''}});
  mounted.rerender(view(first.task_id));
  fireEvent.click(await screen.findByText('任务标题与标签'));
  expect(screen.getByLabelText('任务标题')).toHaveValue('未保存草稿');
  mounted.unmount();
  render(view(first.task_id));
  fireEvent.click(await screen.findByText('任务标题与标签'));
  expect(screen.getByLabelText('任务标题')).toHaveValue('未保存草稿');
  fireEvent.click(screen.getByRole('button', {name: '保存任务信息'}));
  await screen.findByRole('alert');
  expect(submitted).toEqual({expected_version: 'original', title: '未保存草稿', tags: []});
});
