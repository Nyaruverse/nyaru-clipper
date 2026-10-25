import { fireEvent, render, screen } from '@testing-library/react';
import { expect, it, vi } from 'vitest';
import { TextStyleFields } from './TextStyleFields';
import { defaultStyle } from './subtitleStyle';

it('warns on absent server fonts and offers installed families without claiming glyph coverage', () => {
  const view = render(<TextStyleFields style={{ ...defaultStyle.original, font: 'Missing Font' }} onChange={vi.fn()} fonts={{ available: true, families: ['Arial', '苹方'] }} />);
  expect(screen.getByRole('status')).toHaveTextContent('未检测到字体');
  expect(document.querySelector('datalist option[value="苹方"]')).toBeInTheDocument();
  view.rerender(<TextStyleFields style={defaultStyle.original} onChange={vi.fn()} fonts={{ available: true, families: ['Arial'] }} />);
  expect(screen.queryByRole('status')).toBeNull();
});

it('shares pinned fonts across editors and applies a pinned family', () => {
  const change = vi.fn();
  render(<><TextStyleFields style={defaultStyle.original} onChange={change} />
    <TextStyleFields style={{...defaultStyle.original, font: '苹方'}} onChange={change} /></>);

  fireEvent.click(screen.getAllByRole('button', {name: '收藏当前字体'})[0]);

  expect(screen.getAllByRole('button', {name: '使用收藏字体 Arial'})).toHaveLength(2);
  fireEvent.click(screen.getAllByRole('button', {name: '使用收藏字体 Arial'})[1]);
  expect(change).toHaveBeenCalledWith({font: 'Arial'});
});

it('adds an outline without changing the existing stroke or font', () => {
  const change = vi.fn();
  render(<TextStyleFields style={defaultStyle.original} onChange={change} />);

  fireEvent.click(screen.getByRole('button', {name: '添加描边层'}));

  expect(change).toHaveBeenCalledWith({outline_layers: [{color: '#000000', width: 4}]});
});
