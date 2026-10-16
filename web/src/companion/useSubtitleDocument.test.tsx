import { act, renderHook, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { useSubtitleDocument } from './useSubtitleDocument';
import { documentFixture } from './subtitleDocument.fixture';

afterEach(() => vi.unstubAllGlobals());

it('preserves edits on task switching and serializes save/revision with undo and redo', async () => {
  const fixture = documentFixture();
  const posts: unknown[] = [];
  vi.stubGlobal('fetch', vi.fn(async (_url: string, init?: RequestInit) => {
    const doc = init?.body ? JSON.parse(String(init.body)) : fixture;
    if (init?.body) posts.push(doc);
    return new Response(JSON.stringify({ ...doc, revision: init?.body ? doc.revision + 1 : 0 }));
  }));
  const hook = renderHook(({ id }) => useSubtitleDocument(id, true), { initialProps: { id: 'first' } });
  await waitFor(() => expect(hook.result.current.document).not.toBeNull());
  act(() => hook.result.current.change(doc => ({ ...doc, cues: doc.cues.map((cue, i) => i ? cue : { ...cue, text: 'changed' }) })));
  expect(hook.result.current.dirty).toBe(true);
  act(() => hook.result.current.undo());
  expect(hook.result.current.document?.cues[0].text).toBe(fixture.cues[0].text);
  act(() => hook.result.current.redo());
  expect(hook.result.current.document?.cues[0].text).toBe('changed');
  hook.rerender({ id: 'second' });
  await waitFor(() => expect(hook.result.current.document).not.toBeNull());
  hook.rerender({ id: 'first' });
  expect(hook.result.current.document?.cues[0].text).toBe('changed');
  await waitFor(() => expect(posts).toHaveLength(1), { timeout: 3000 });
  await waitFor(() => expect(hook.result.current.dirty).toBe(false));
  expect(hook.result.current.document?.revision).toBe(1);
});

it('keeps unsaved text and blocks export readiness on save conflict', async () => {
  vi.stubGlobal('fetch', vi.fn(async (_url: string, init?: RequestInit) => new Response(JSON.stringify(init?.body ? { detail: '编辑稿已更新，请重新载入' } : documentFixture()), { status: init?.body ? 409 : 200 })));
  const hook = renderHook(() => useSubtitleDocument('conflict', true));
  await waitFor(() => expect(hook.result.current.document).not.toBeNull());
  act(() => hook.result.current.change(doc => ({ ...doc, cues: [{ ...doc.cues[0], text: 'keep me' }] })));
  await waitFor(() => expect(hook.result.current.error).toMatch(/重新载入/), { timeout: 3000 });
  expect(hook.result.current.document?.cues[0].text).toBe('keep me');
  expect(hook.result.current.dirty).toBe(true);
});

it('preserves edits made while a source refresh is in flight', async () => {
  let release: ((response: Response) => void) | undefined;
  let reads = 0;
  vi.stubGlobal('fetch', vi.fn(async () => {
    if (++reads === 1) return new Response(JSON.stringify(documentFixture()));
    return new Promise<Response>(resolve => { release = resolve; });
  }));
  const hook = renderHook(({ token }) => useSubtitleDocument('refresh', true, token), { initialProps: { token: 'not_started' } });
  await waitFor(() => expect(hook.result.current.document).not.toBeNull());
  hook.rerender({ token: 'completed' });
  await waitFor(() => expect(release).toBeDefined());
  act(() => hook.result.current.change(doc => ({ ...doc, cues: [{ ...doc.cues[0], text: 'must survive refresh' }] })));
  await act(async () => { release?.(new Response(JSON.stringify(documentFixture()))); });
  expect(hook.result.current.document?.cues[0].text).toBe('must survive refresh');
  expect(hook.result.current.error).toMatch(/保留/);
});
