import { useRef } from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { expect, it, vi } from 'vitest';
import { SubtitlePreview } from './SubtitlePreview';
import { DEFAULT_STYLE } from './legacyStyle';

function Harness() {
  const video = useRef<HTMLVideoElement>(null);
  return <SubtitlePreview video={video} source="clip.mp4"
    segments={[{ id: '1', start_seconds: 0, end_seconds: 12, text: '原文' }]}
    zhSegments={[{ id: '1', start_seconds: 0, end_seconds: 12, text: '译文' }]}
    bilingualSegments={[{ id: '1', start_seconds: 0, end_seconds: 12, text: '原文\n译文' }]}
    style={DEFAULT_STYLE} mode="bilingual"><video ref={video} aria-label="test video" /></SubtitlePreview>;
}

it('renders bilingual lines with legacy multi-layer outline text', () => {
  render(<Harness />);
  const video = screen.getByLabelText('test video');
  Object.defineProperties(video, { clientWidth: { value: 1920 }, clientHeight: { value: 1080 }, videoWidth: { value: 1920 }, videoHeight: { value: 1080 }, textTracks: { value: [] } });
  fireEvent.loadedMetadata(video);
  fireEvent(video, new Event('timeupdate'));
  const lines = document.querySelectorAll('.subtitle-overlay .subtitle-overlay-line');
  expect(lines.length).toBe(2);
  // 默认样式单层 2px 描边：每行 = 1 描边叠层 + 1 填充层
  expect(lines[0].querySelectorAll('span span').length).toBeGreaterThan(1);
});

it('toggles styled overlay off via the checkbox', () => {
  render(<Harness />);
  const video = screen.getByLabelText('test video');
  Object.defineProperties(video, { clientWidth: { value: 1920 }, clientHeight: { value: 1080 }, videoWidth: { value: 1920 }, videoHeight: { value: 1080 }, textTracks: { value: [] } });
  fireEvent.loadedMetadata(video);
  fireEvent(video, new Event('timeupdate'));
  expect(document.querySelector('.subtitle-overlay')).not.toBeNull();
  fireEvent.click(screen.getByRole('checkbox', { name: '样式字幕预览' }));
  expect(document.querySelector('.subtitle-overlay')).toBeNull();
});

it('requests fullscreen on the wrapper containing subtitles and video', () => {
  render(<Harness />);
  const wrapper = document.querySelector('.subtitle-video-wrapper');
  const request = vi.fn().mockResolvedValue(undefined);
  Object.defineProperty(wrapper, 'requestFullscreen', { value: request });
  fireEvent.click(screen.getByText('含字幕全屏'));
  expect(request).toHaveBeenCalledOnce();
  expect(wrapper?.querySelector('video')).not.toBeNull();
});

it('exposes an exit action inside fullscreen and exits through the document API', () => {
  render(<Harness />);
  const video = screen.getByLabelText('test video');
  const wrapper = video.parentElement;
  const exit = vi.fn().mockResolvedValue(undefined);
  Object.defineProperty(document, 'exitFullscreen', { value: exit, configurable: true });
  Object.defineProperty(document, 'fullscreenElement', { value: wrapper, configurable: true });
  fireEvent(document, new Event('fullscreenchange'));
  const button = screen.getByRole('button', { name: '退出含字幕全屏' });
  expect(wrapper?.contains(button)).toBe(true);
  fireEvent.click(button);
  expect(exit).toHaveBeenCalledOnce();
  Object.defineProperty(document, 'fullscreenElement', { value: null, configurable: true });
  fireEvent(document, new Event('fullscreenchange'));
  expect(screen.queryByRole('button', { name: '退出含字幕全屏' })).toBeNull();
});
