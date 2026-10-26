import {useRef} from 'react';
import {fireEvent, render} from '@testing-library/react';
import {expect, it, vi} from 'vitest';
import {SubtitlePreview} from './SubtitlePreview';
import {defaultStyle} from './subtitleStyle';

function Player({loop = false}: {readonly loop?: boolean}) {
  const video = useRef<HTMLVideoElement>(null);
  return <SubtitlePreview video={video} segments={[]} bilingual={[]} offset={10} source="clip.mp4" style={defaultStyle}
    loop={loop ? {start: 15, end: 25} : null} stopAt={25}><video ref={video}/></SubtitlePreview>;
}

it('stops at the source range end when previewing a clip without repetition', () => {
  // Given an actively playing clip whose source offset is ten seconds.
  render(<Player/>);
  const video = document.querySelector('video');if (!video) throw new Error('Expected video');
  const pause = vi.fn();Object.defineProperty(video, 'pause', {value: pause});
  Object.defineProperty(video, 'paused', {value: false});
  // When playback crosses the absolute source endpoint.
  fireEvent.timeUpdate(video, {target: {currentTime: 16}});
  // Then it pauses at the corresponding clip-relative endpoint.
  expect(pause).toHaveBeenCalledOnce();expect(video.currentTime).toBe(15);
});

it('repeats only the chosen source range when repetition is enabled', () => {
  // Given the same clip with explicit repetition.
  render(<Player loop/>);
  const video = document.querySelector('video');if (!video) throw new Error('Expected video');
  const pause = vi.fn();Object.defineProperty(video, 'pause', {value: pause});
  Object.defineProperty(video, 'paused', {value: false});
  // When playback crosses the range endpoint.
  fireEvent.timeUpdate(video, {target: {currentTime: 16}});
  // Then it seeks to the source range start without pausing.
  expect(video.currentTime).toBe(5);expect(pause).not.toHaveBeenCalled();
});
