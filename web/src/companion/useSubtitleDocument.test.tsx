import { act, renderHook, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { useSubtitleDocument } from './useSubtitleDocument';
import { documentFixture } from './subtitleDocument.fixture';

afterEach(() => { vi.useRealTimers(); vi.unstubAllGlobals(); });

it('flushes a deselected draft immediately before the autosave delay', async () => {
  const posts: string[] = [];
  vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => {
    const doc = init?.body ? JSON.parse(String(init.body)) : documentFixture();
    if (init?.body) posts.push(url);
    return new Response(JSON.stringify({ ...doc, revision: init?.body ? doc.revision + 1 : 0 }));
  }));
  const hook = renderHook(({ id }) => useSubtitleDocument(id, true), { initialProps: { id: 'first' } });
  await waitFor(() => expect(hook.result.current.document).not.toBeNull());
  vi.useFakeTimers();
  act(() => hook.result.current.change(doc => ({ ...doc, cues: [{ ...doc.cues[0], text: 'quit draft' }] })));
  hook.rerender({ id: 'second' });
  expect(hook.result.current.hasUnsaved()).toBe(true);
  expect(posts).toHaveLength(0);
  await act(async () => expect(await hook.result.current.flush()).toBeNull());
  expect(posts).toEqual(['/companion-api/jobs/first/subtitle-document']);
  expect(hook.result.current.hasUnsaved()).toBe(false);
});

it('waits an existing save and flushes a newer edit with the returned revision', async () => {
  const posts: ReturnType<typeof documentFixture>[] = [];
  let release: ((response: Response) => void) | undefined;
  vi.stubGlobal('fetch', vi.fn(async (_url: string, init?: RequestInit) => {
    if (!init?.body) return new Response(JSON.stringify(documentFixture()));
    const doc = JSON.parse(String(init.body)); posts.push(doc);
    if (posts.length === 1) return new Promise<Response>(resolve => { release = resolve; });
    return new Response(JSON.stringify({ ...doc, revision: doc.revision + 1 }));
  }));
  const hook = renderHook(() => useSubtitleDocument('first', true));
  await waitFor(() => expect(hook.result.current.document).not.toBeNull());
  vi.useFakeTimers();
  act(() => hook.result.current.change(doc => ({ ...doc, cues: [{ ...doc.cues[0], text: 'first' }] })));
  await act(async () => { await vi.advanceTimersByTimeAsync(650); });
  act(() => hook.result.current.change(doc => ({ ...doc, cues: [{ ...doc.cues[0], text: 'second' }] })));
  let finished = false;
  const flush = hook.result.current.flush().then(value => { finished = true; return value; });
  await act(async () => { await Promise.resolve(); });
  expect(finished).toBe(false); expect(posts).toHaveLength(1);
  await act(async () => { release?.(new Response(JSON.stringify({ ...posts[0], revision: 1 }))); expect(await flush).toBeNull(); });
  expect(posts).toHaveLength(2); expect(posts[1].revision).toBe(1);
  expect(posts[1].cues[0].text).toBe('second');
  expect(hook.result.current.hasUnsaved()).toBe(false);
});

it.each(['conflict', 'network', 'invalid'] as const)('retains the draft when quit flush fails: %s', async failure => {
  const posts = vi.fn();
  vi.stubGlobal('fetch', vi.fn(async (_url: string, init?: RequestInit) => {
    if (!init?.body) return new Response(JSON.stringify(documentFixture()));
    posts();
    if (failure === 'invalid') return new Response(JSON.stringify({ ...documentFixture(), revision: 1 }));
    if (failure === 'network') throw new Error('offline');
    return new Response(JSON.stringify({ detail: 'conflict' }), { status: 409 });
  }));
  const hook = renderHook(() => useSubtitleDocument('first', true));
  await waitFor(() => expect(hook.result.current.document).not.toBeNull());
  vi.useFakeTimers();
  act(() => hook.result.current.change(doc => ({ ...doc, cues: [{ ...doc.cues[0], text: 'keep', end_seconds: failure === 'invalid' ? -1 : doc.cues[0].end_seconds }] })));
  await act(async () => expect(await hook.result.current.flush()).toEqual(expect.any(String)));
  if (failure === 'invalid') expect(posts).not.toHaveBeenCalled();
  else expect(posts).toHaveBeenCalledTimes(1);
  expect(hook.result.current.hasUnsaved()).toBe(true);
  expect(hook.result.current.document?.cues[0].text).toBe('keep');
});

it('retries a failed autosave on explicit quit save and observes edits to later sessions while saving', async () => {
  let fail = true;
  let release: ((response: Response) => void) | undefined;
  const posts: { url: string; doc: ReturnType<typeof documentFixture> }[] = [];
  vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => {
    if (!init?.body) return new Response(JSON.stringify(documentFixture()));
    const doc = JSON.parse(String(init.body)); posts.push({ url, doc });
    if (fail) return new Response(JSON.stringify({ detail: 'conflict' }), { status: 409 });
    if (url.includes('/first/')) return new Promise<Response>(resolve => { release = resolve; });
    return new Response(JSON.stringify({ ...doc, revision: doc.revision + 1 }));
  }));
  const hook = renderHook(({ id }) => useSubtitleDocument(id, true), { initialProps: { id: 'first' } });
  await waitFor(() => expect(hook.result.current.document).not.toBeNull());
  act(() => hook.result.current.change(doc => ({ ...doc, cues: [{ ...doc.cues[0], text: 'first draft' }] })));
  await act(async () => { await hook.result.current.flush(); });
  expect(hook.result.current.error).toBeTruthy();
  hook.rerender({ id: 'second' });
  await waitFor(() => expect(hook.result.current.document).not.toBeNull());
  vi.useFakeTimers();
  act(() => hook.result.current.change(doc => ({ ...doc, cues: [{ ...doc.cues[0], text: 'older second draft' }] })));
  fail = false;
  let saving: Promise<string | null> | undefined;
  act(() => { saving = hook.result.current.flush(); });
  act(() => hook.result.current.change(doc => ({ ...doc, cues: [{ ...doc.cues[0], text: 'newest second draft' }] })));
  await act(async () => { release?.(new Response(JSON.stringify({ ...posts[1].doc, revision: 1 }))); expect(await saving).toBeNull(); });
  expect(posts).toHaveLength(3);
  expect(posts[2].doc.cues[0].text).toBe('newest second draft');
  expect(hook.result.current.hasUnsaved()).toBe(false);
});

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
