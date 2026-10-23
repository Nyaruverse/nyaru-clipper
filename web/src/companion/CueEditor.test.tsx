import { fireEvent, render, screen } from '@testing-library/react';
import { expect, it, vi } from 'vitest';
import { CueEditor } from './CueEditor';
import { documentFixture } from './subtitleDocument.fixture';

function paginatedDocument(count: number) {
  const base = documentFixture();
  return { ...base, cues: Array.from({ length: count }, (_, index) => ({
    ...base.cues[0], id: `row-${index + 1}`, text: `字幕 ${index + 1}`, translation: '',
  })) };
}

const editorProps = {
  selected: ['row-21'], onSelect: vi.fn(), change: vi.fn(), language: 'original', onLanguage: vi.fn(),
  currentTime: 3, onSeek: vi.fn(), undo: vi.fn(), redo: vi.fn(), canUndo: false, canRedo: false, compact: true,
} as const;

it('shows the remaining cues when a result shrinks from 21 cues on page two to two cues', () => {
  const { rerender } = render(<CueEditor {...editorProps} document={paginatedDocument(21)} />);
  fireEvent.click(screen.getByRole('button', { name: '下一页' }));
  expect(screen.getByText('字幕 21', { selector: '.cue-row span' })).toBeVisible();

  rerender(<CueEditor {...editorProps} document={paginatedDocument(2)} />);

  expect(screen.getByText('字幕 1', { selector: '.cue-row span' })).toBeVisible();
  expect(screen.getByText('字幕 2', { selector: '.cue-row span' })).toBeVisible();
  expect(screen.queryByRole('button', { name: '下一页' })).not.toBeInTheDocument();
});

it('clamps the last page when filtered results shrink while the search stays active', () => {
  const doc = paginatedDocument(41);
  const { rerender } = render(<CueEditor {...editorProps} document={doc} />);
  fireEvent.change(screen.getByRole('searchbox'), { target: { value: '字幕' } });
  fireEvent.click(screen.getByRole('button', { name: '下一页' }));
  fireEvent.click(screen.getByRole('button', { name: '下一页' }));
  expect(screen.getByText('3 / 3')).toBeVisible();

  rerender(<CueEditor {...editorProps} document={{ ...doc, cues: doc.cues.map((cue, index) => index < 21 ? cue : { ...cue, text: '不匹配' }) }} />);

  expect(screen.getByText('字幕 21', { selector: '.cue-row span' })).toBeVisible();
  expect(screen.getByText('2 / 2')).toBeVisible();
  expect(screen.getByRole('button', { name: '下一页' })).toBeDisabled();
  expect(screen.getByRole('searchbox')).toHaveValue('字幕');
});

it('starts a new filter on the first page', () => {
  render(<CueEditor {...editorProps} document={paginatedDocument(41)} />);
  fireEvent.click(screen.getByRole('button', { name: '下一页' }));

  fireEvent.change(screen.getByRole('searchbox'), { target: { value: '字幕 1' } });

  expect(screen.getByText('字幕 1')).toBeVisible();
  expect(screen.getAllByRole('checkbox')).toHaveLength(11);
  expect(screen.queryByRole('button', { name: '下一页' })).not.toBeInTheDocument();
});

it('keeps page, search, advanced tab and clipboard through ordinary text, style and revision edits', () => {
  const doc = paginatedDocument(41);
  const { rerender } = render(<CueEditor {...editorProps} document={doc} />);
  fireEvent.change(screen.getByRole('searchbox'), { target: { value: '字幕' } });
  fireEvent.click(screen.getByRole('button', { name: '下一页' }));
  fireEvent.click(screen.getByRole('button', { name: '高级逐条编辑' }));
  fireEvent.click(screen.getByRole('button', { name: '复制样式' }));
  fireEvent.click(screen.getByRole('button', { name: /^位置$/ }));

  rerender(<CueEditor {...editorProps} document={{ ...doc, revision: 1,
    style: { ...doc.style, original: { ...doc.style.original, size: 60 } },
    cues: doc.cues.map(cue => cue.id === 'row-21' ? { ...cue, text: '字幕 21 已修改' } : cue),
  }} />);

  expect(screen.getByText('字幕 21 已修改')).toBeVisible();
  expect(screen.getByText('2 / 3')).toBeVisible();
  expect(screen.getByRole('searchbox')).toHaveValue('字幕');
  expect(screen.getByRole('button', { name: '收起高级编辑' })).toBeVisible();
  expect(screen.getByLabelText('X 坐标')).toBeVisible();
  expect(screen.getByRole('button', { name: /^粘贴样式$/ })).toBeEnabled();
});

it.each(['task', 'source'] as const)('resets local editing state when the real %s identity changes', identity => {
  const doc = paginatedDocument(21);
  const { rerender } = render(<CueEditor {...editorProps} taskId="task-a" document={doc} />);
  fireEvent.change(screen.getByRole('searchbox'), { target: { value: '字幕' } });
  fireEvent.click(screen.getByRole('button', { name: '下一页' }));
  fireEvent.click(screen.getByRole('button', { name: '高级逐条编辑' }));
  fireEvent.click(screen.getByRole('button', { name: '复制样式' }));
  fireEvent.click(screen.getByRole('button', { name: /^位置$/ }));
  const next = paginatedDocument(2);

  rerender(<CueEditor {...editorProps} selected={['row-1']} taskId={identity === 'task' ? 'task-b' : 'task-a'}
    document={{ ...next, source_fingerprint: identity === 'source' ? 'b'.repeat(64) : doc.source_fingerprint,
      cues: next.cues.map(cue => ({ ...cue, text: `新来源 ${cue.id}` })) }} />);

  expect(screen.getByText('新来源 row-1', { selector: '.cue-row span' })).toBeVisible();
  expect(screen.getByText('新来源 row-2', { selector: '.cue-row span' })).toBeVisible();
  expect(screen.getByRole('searchbox')).toHaveValue('');
  expect(screen.getByRole('button', { name: '高级逐条编辑' })).toBeVisible();
  expect(screen.getByLabelText('本条原文')).toHaveValue('新来源 row-1');
  expect(screen.getByRole('button', { name: /^粘贴样式$/ })).toBeDisabled();
});

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
