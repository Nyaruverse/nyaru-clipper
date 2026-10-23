import {QueryClient, QueryClientProvider} from '@tanstack/react-query';
import {fireEvent, render, screen, waitFor} from '@testing-library/react';
import {afterEach, expect, it, vi} from 'vitest';
import {UnifiedQueue} from './UnifiedQueue';
import type {OperationsSnapshot} from './unifiedOperations';

afterEach(() => vi.unstubAllGlobals());

it('refreshes a stale queue and asks before retrying an uncertain external request', async () => {
  let snapshot: OperationsSnapshot = {revision: 2, paused: true, recovering: false, operations: [
    {id: 'operation-a', task_id: 'a'.repeat(32), kind: 'translate', state: 'interrupted', attempt: 1,
      priority: 0, position: 1, cancel_requested: false, failure_code: 'external_outcome_unknown_possible_repeat_charge'}]};
  const mutations: {url: string; body: unknown}[] = [];
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
    const request = input instanceof Request ? input : new Request(input);
    if (request.method === 'GET') return Response.json(snapshot);
    mutations.push({url: request.url, body: await request.json()});
    if (request.url.endsWith('/queue')) {
      snapshot = {...snapshot, revision: 3, paused: false};
      return Response.json({detail: 'stale'}, {status: 409});
    }
    snapshot = {...snapshot, revision: 4, operations: snapshot.operations.map(item => ({...item, state: 'queued'}))};
    return Response.json(snapshot);
  }));
  const confirm = vi.fn(() => false);
  vi.stubGlobal('confirm', confirm);
  const queryClient = new QueryClient({defaultOptions: {queries: {retry: false}, mutations: {retry: false}}});
  render(<QueryClientProvider client={queryClient}><UnifiedQueue onSelect={() => {}}/></QueryClientProvider>);
  fireEvent.click(await screen.findByRole('button', {name: '重试'}));
  expect(confirm).toHaveBeenCalledOnce();
  expect(mutations).toHaveLength(0);
  fireEvent.click(screen.getByRole('button', {name: '启动队列'}));
  await screen.findByText('队列状态已变化，请重新读取后重试');
  await screen.findByRole('button', {name: '暂停后续任务'});
  confirm.mockReturnValue(true);
  fireEvent.click(screen.getByRole('button', {name: '重试'}));
  await waitFor(() => expect(mutations[1]?.body).toEqual({acknowledge_external_outcome: true}));
  await waitFor(() => expect(screen.queryByRole('button', {name: '重试'})).not.toBeInTheDocument());
});
