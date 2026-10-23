import { act, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { DocumentOverlay } from './DocumentOverlay';
import { documentFixture } from './subtitleDocument.fixture';

afterEach(() => vi.unstubAllGlobals());
it('sends the same bounded active frame for short and 5000-cue documents, preserving overlaps and edits', async () => {
  const fetch = vi.fn(async (_url: string, _init?: RequestInit) => new Response(new Blob(['png'])));
  vi.stubGlobal('fetch', fetch);
  URL.createObjectURL = vi.fn(() => 'blob:frame');
  URL.revokeObjectURL = vi.fn();
  const original = documentFixture();
  const first = original.cues[0];
  const doc = { ...original, cues: [{ ...first, text: 'unsaved😀', original_emphasis: [] },
    { ...first, id: 'cue-000002', start_seconds: 2.005, end_seconds: 4 }] };
  const props = { id: 'short', document: doc, time: 2.02, bilingual: true, selected: [], language: 'original' as const, onMove: vi.fn(), editing: false };
  const view = render(<DocumentOverlay {...props} />);
  await waitFor(() => expect(fetch).toHaveBeenCalledTimes(1));
  const short = String(fetch.mock.calls[0][1]?.body);
  expect(JSON.parse(short).frame.cues).toEqual(doc.cues);
  expect(JSON.parse(short).document).toBeUndefined();
  const large = { ...doc, cues: [...doc.cues, ...Array.from({ length: 4998 }, (_, index) => ({ ...first,
    id: `cue-${String(index + 3).padStart(6, '0')}`, start_seconds: 6, end_seconds: 8 }))] };
  view.rerender(<DocumentOverlay {...props} id="large" document={large} />);
  await waitFor(() => expect(fetch).toHaveBeenCalledTimes(2));
  expect(String(fetch.mock.calls[1][1]?.body)).toBe(short);
  view.rerender(<DocumentOverlay {...props} id="large" document={large} time={2.5} />);
  await act(async () => { await new Promise(resolve => setTimeout(resolve, 120)); });
  expect(fetch).toHaveBeenCalledTimes(2);
});

it('requests actual libass pixels and hides stale pixels after the active scene changes', async () => {
  const fetch = vi.fn(async (_url: string, _init?: RequestInit) => new Response(new Blob(['png'], { type: 'image/png' })));
  vi.stubGlobal('fetch', fetch);
  URL.createObjectURL = vi.fn(() => 'blob:preview');
  URL.revokeObjectURL = vi.fn();
  const props = { id: 'test', document: documentFixture(), time: 2, bilingual: true, selected: ['cue-000001'], language: 'original' as const, onMove: vi.fn(), editing: true };
  const view = render(<DocumentOverlay {...props} />);
  await waitFor(() => expect(screen.getByAltText('精确字幕预览')).toBeInTheDocument());
  expect(JSON.parse(String(fetch.mock.calls[0][1]?.body ?? '{}')).time).toBe(2);
  view.rerender(<DocumentOverlay {...props} time={9} />);
  expect(screen.queryByAltText('精确字幕预览')).not.toBeInTheDocument();
  await act(async () => {});
});

it('aborts old tasks and distinguishes style, bilingual edits and undo generations', async () => {
  const pending: Array<(response: Response) => void> = [];
  const fetch = vi.fn((_url: string, _init?: RequestInit) => new Promise<Response>(resolve => pending.push(resolve)));
  vi.stubGlobal('fetch', fetch);
  URL.createObjectURL = vi.fn(() => `blob:${fetch.mock.calls.length}`);
  URL.revokeObjectURL = vi.fn();
  const doc = documentFixture();
  const props = { id: 'old', document: doc, time: 2, bilingual: false, selected: [], language: 'original' as const, onMove: vi.fn(), editing: false };
  const view = render(<DocumentOverlay {...props} />);
  await waitFor(() => expect(fetch).toHaveBeenCalledTimes(1));
  view.rerender(<DocumentOverlay {...props} id="new" />);
  expect(fetch.mock.calls[0][1]?.signal?.aborted).toBe(true);
  await waitFor(() => expect(fetch).toHaveBeenCalledTimes(2));
  await act(async () => { pending[1](new Response(new Blob(['new']))); });
  expect(screen.getByAltText('精确字幕预览')).toHaveAttribute('src', 'blob:2');
  await act(async () => { pending[0](new Response(new Blob(['old']))); });
  expect(URL.createObjectURL).toHaveBeenCalledTimes(1);
  const edited = { ...doc, style: { ...doc.style, original: { ...doc.style.original, color: '#123456' } } };
  view.rerender(<DocumentOverlay {...props} id="new" document={edited} />);
  expect(screen.queryByAltText('精确字幕预览')).not.toBeInTheDocument();
  await waitFor(() => expect(fetch).toHaveBeenCalledTimes(3));
  expect(JSON.parse(String(fetch.mock.calls[2][1]?.body)).frame.style.original.color).toBe('#123456');
  view.rerender(<DocumentOverlay {...props} id="new" />);
  await waitFor(() => expect(fetch).toHaveBeenCalledTimes(4));
  view.rerender(<DocumentOverlay {...props} id="new" bilingual />);
  await waitFor(() => expect(fetch).toHaveBeenCalledTimes(5));
  expect(JSON.parse(String(fetch.mock.calls[4][1]?.body)).bilingual).toBe(true);
  view.unmount();
  expect(fetch.mock.calls[4][1]?.signal?.aborted).toBe(true);
});
