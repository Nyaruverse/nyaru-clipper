import { act, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { DocumentOverlay } from './DocumentOverlay';
import { documentFixture } from './subtitleDocument.fixture';

afterEach(() => vi.unstubAllGlobals());
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
