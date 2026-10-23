import { act, renderHook } from '@testing-library/react';
import { expect, it, vi } from 'vitest';
import { useNativeQuitBridge } from './useNativeQuitBridge';

it('publishes clean/dirty status and removes the bridge when the editor unmounts', async () => {
  const hasUnsaved = vi.fn(() => false), flush = vi.fn(async () => null);
  const hook = renderHook(() => useNativeQuitBridge(false, hasUnsaved, flush));
  expect(window.nyaruQuit?.status()).toBe('clean');
  hasUnsaved.mockReturnValue(true);
  expect(window.nyaruQuit?.status()).toBe('dirty');
  hook.unmount();
  expect(window.nyaruQuit).toBeUndefined();
  expect(flush).not.toHaveBeenCalled();
});

it('awaits save acknowledgement and returns a failure without authorizing quit', async () => {
  let finish: ((error: string | null) => void) | undefined;
  const flush = vi.fn(() => new Promise<string | null>(resolve => { finish = resolve; }));
  renderHook(() => useNativeQuitBridge(false, () => true, flush));
  let finished = false;
  const saving = window.nyaruQuit?.save().then(value => { finished = true; return value; });
  expect(finished).toBe(false);
  await act(async () => { finish?.('conflict'); });
  expect(await saving).toBe('conflict');
});

it('requires settings to be saved first, including settings edited during subtitle save', async () => {
  let finish: ((error: string | null) => void) | undefined;
  const flush = vi.fn(() => new Promise<string | null>(resolve => { finish = resolve; }));
  const hook = renderHook(({ dirty }) => useNativeQuitBridge(dirty, () => false, flush), { initialProps: { dirty: true } });
  expect(window.nyaruQuit?.status()).toBe('dirty');
  expect(await window.nyaruQuit?.save()).toEqual(expect.any(String));
  expect(flush).not.toHaveBeenCalled();
  hook.rerender({ dirty: false });
  const saving = window.nyaruQuit?.save();
  hook.rerender({ dirty: true });
  await act(async () => { finish?.(null); });
  expect(await saving).toEqual(expect.any(String));
});

it('protects cached metadata drafts even when the task editor is closed', async () => {
  const flush = vi.fn(async () => null);
  let dirty = true;
  renderHook(() => useNativeQuitBridge(false, () => false, flush, () => dirty));
  expect(window.nyaruQuit?.status()).toBe('dirty');
  expect(await window.nyaruQuit?.save()).toContain('任务标题与标签');
  expect(flush).not.toHaveBeenCalled();
  const event = new Event('beforeunload', {cancelable: true});
  window.dispatchEvent(event);
  expect(event.defaultPrevented).toBe(true);
  dirty = false;
  expect(window.nyaruQuit?.status()).toBe('clean');
});
