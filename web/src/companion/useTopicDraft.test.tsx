import {QueryClient, QueryClientProvider} from '@tanstack/react-query';
import {act, renderHook, waitFor} from '@testing-library/react';
import type {ReactNode} from 'react';
import {afterEach, beforeEach, expect, it, vi} from 'vitest';
import {useTopicDraft} from './useTopicDraft';

beforeEach(() => localStorage.clear());
afterEach(() => vi.restoreAllMocks());
function mount(jobId = 'saved-task') {
  const client = new QueryClient({defaultOptions: {queries: {retry: false}}});
  return renderHook(() => useTopicDraft(jobId), {wrapper: ({children}: {children: ReactNode}) => <QueryClientProvider client={client}>{children}</QueryClientProvider>});
}
it('restores reviewed ordering and ranges after the query client is recreated', () => {
  const first = mount();
  act(() => first.result.current.update({analysisKey: 'analysis/1', selected: [2, 0], ranges: {2: {start_seconds: 4, end_seconds: 8}}, current: 2}));
  first.unmount();const second = mount();
  expect(second.result.current.draft).toMatchObject({analysisKey: 'analysis/1', selected: [2, 0], ranges: {2: {start_seconds: 4, end_seconds: 8}}, current: 2});
  const other = mount('other-task');expect(other.result.current.draft.selected).toEqual([]);
});
it.each(['{broken', '{"selected":"wrong"}', '{"version":2,"draft":{}}'])('ignores corrupt or unsupported storage: %s', raw => {
  localStorage.setItem('nyaru-topic-draft-v1:saved-task', raw);
  expect(mount().result.current.draft.selected).toEqual([]);
});
it('keeps selections in memory and warns if browser storage quota is exhausted', async () => {
  const hook = mount();vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {throw new DOMException('full', 'QuotaExceededError');});
  act(() => hook.result.current.update({selected: [0]}));
  await waitFor(() => expect(hook.result.current.draft.selected).toEqual([0]));
  expect(hook.result.current.persistenceError).toMatch(/重新打开/);
});
