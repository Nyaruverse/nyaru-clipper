import { fireEvent, render, screen } from '@testing-library/react';
import { expect, it, vi } from 'vitest';
import { CueEditor } from './CueEditor';
import { documentFixture } from './subtitleDocument.fixture';

it('edits one language of selected cue and supports batch nudge, undo and restoring inheritance', () => {
  const doc = documentFixture();
  const change = vi.fn<(update: (document: ReturnType<typeof documentFixture>) => ReturnType<typeof documentFixture>) => void>();
  const undo = vi.fn();
  render(<CueEditor document={doc} selected={['cue-000001']} onSelect={vi.fn()} change={change} language="original" onLanguage={vi.fn()}
    currentTime={3} onSeek={vi.fn()} undo={undo} redo={vi.fn()} canUndo canRedo={false} />);
  fireEvent.change(screen.getByLabelText('本条原文'), { target: { value: '修改后' } });
  const next = change.mock.calls[change.mock.calls.length - 1][0](doc);
  expect(next.cues[0].text).toBe('修改后');
  expect(next.cues[0].original_emphasis).toEqual([]);
  expect(next.cues[1]).toBe(doc.cues[1]);
  fireEvent.click(screen.getByRole('button', { name: /^位置$/ }));
  fireEvent.click(screen.getByRole('button', { name: '向右 1 像素' }));
  const moved = change.mock.calls[change.mock.calls.length - 1][0](doc);
  expect(moved.cues[0].original_style?.x).toBe(641);
  expect(moved.cues[0].translation_style).toBeNull();
  fireEvent.click(screen.getByRole('button', { name: '恢复所选继承' }));
  expect(change.mock.calls[change.mock.calls.length - 1][0](moved).cues[0].original_style).toBeNull();
  fireEvent.click(screen.getByRole('button', { name: '撤销' }));
  expect(undo).toHaveBeenCalledOnce();
});

it('preserves bilingual spacing when linked numeric positioning starts from automatic layout', () => {
  const base = documentFixture();
  const doc = { ...base, width: 640, height: 360, cues: [{ ...base.cues[0], translation: 'line1\nline2' }] };
  const change = vi.fn<(update: (document: ReturnType<typeof documentFixture>) => ReturnType<typeof documentFixture>) => void>();
  render(<CueEditor document={doc} selected={['cue-000001']} onSelect={vi.fn()} change={change} language="original" onLanguage={vi.fn()} currentTime={2} onSeek={vi.fn()} undo={vi.fn()} redo={vi.fn()} canUndo={false} canRedo={false} linked />);
  fireEvent.click(screen.getByRole('button', { name: /^位置$/ }));
  fireEvent.change(screen.getByLabelText('X 坐标'), { target: { value: '321' } });
  const moved = change.mock.calls[change.mock.calls.length - 1][0](doc).cues[0];
  expect(moved.original_style?.y).toBe(312);
  expect(moved.translation_style?.y).toBeCloseTo(346.666667);
  expect(moved.translation_style?.x).toBe(321);
});
