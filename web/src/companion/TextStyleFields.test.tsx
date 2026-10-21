import { render, screen } from '@testing-library/react';
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
