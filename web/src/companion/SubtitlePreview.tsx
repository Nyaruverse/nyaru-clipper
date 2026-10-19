/** 旧版样式字幕预览：多层描边叠层 + X/Y 百分比定位，与烧录合成（ASS）渲染一致。 */
import { useEffect, useRef, useState, type RefObject, type ReactNode } from 'react';
import { SubtitleOverlay } from './legacyStyle';
import { ShapeOverlay } from './ShapeOverlay';
import type { LegacyStyleConfig, Segment, Shape, SubtitleMode } from './companionApi';

interface Props {
  video: RefObject<HTMLVideoElement>;
  /** 切换视频源时重置状态（如 `${job.id}/${preview}`） */
  source: string;
  segments: Segment[];
  zhSegments: Segment[];
  bilingualSegments: Segment[];
  style: LegacyStyleConfig;
  mode: SubtitleMode;
  shapes?: readonly Shape[];
  children: ReactNode;
}

export function SubtitlePreview({ video, source, segments, zhSegments, bilingualSegments, style, mode, shapes = [], children }: Props) {
  const wrapper = useRef<HTMLDivElement>(null);
  const [time, setTime] = useState(0);
  const [box, setBox] = useState({ width: 0, height: 0, left: 0, top: 0 });
  const [error, setError] = useState('');
  const [styled, setStyled] = useState(true);
  const [fullscreen, setFullscreen] = useState(false);
  useEffect(() => {
    const update = () => setFullscreen(document.fullscreenElement === wrapper.current);
    document.addEventListener('fullscreenchange', update);
    return () => document.removeEventListener('fullscreenchange', update);
  }, []);
  useEffect(() => {
    const element = video.current;
    if (!element) return;
    const update = () => {
      setTime(element.currentTime);
      const width = element.clientWidth, height = element.clientHeight;
      const ratio = element.videoWidth / element.videoHeight || 16 / 9;
      const imageWidth = Math.min(width, height * ratio), imageHeight = imageWidth / ratio;
      setBox({ width: imageWidth, height: imageHeight, left: (width - imageWidth) / 2, top: (height - imageHeight) / 2 });
      for (const track of Array.from(element.textTracks ?? [])) track.mode = styled ? 'hidden' : 'showing';
    };
    const events = ['timeupdate', 'seeking', 'seeked', 'pause', 'loadedmetadata', 'loadeddata'];
    events.forEach(event => element.addEventListener(event, update));
    element.textTracks?.addEventListener?.('addtrack', update);
    const observer = typeof ResizeObserver === 'undefined' ? null : new ResizeObserver(update);
    observer?.observe(element); update();
    return () => { events.forEach(event => element.removeEventListener(event, update)); element.textTracks?.removeEventListener?.('addtrack', update); observer?.disconnect(); };
  }, [video, source, styled]);
  const scale = box.height / 1080;
  return <><div ref={wrapper} className="companion-video-wrap subtitle-video-wrapper">{children}
    {shapes.length > 0 && <ShapeOverlay shapes={shapes} scale={scale} style={{ width: box.width, height: box.height, left: box.left, top: box.top }} />}
    {styled && <SubtitleOverlay mode={mode} currentTime={time} original={segments} translated={zhSegments} bilingual={bilingualSegments} style={style} scale={scale} box={{ width: box.width, height: box.height, left: box.left, top: box.top }} />}
    {fullscreen && <button type="button" className="ny-button subtitle-fullscreen-exit" onClick={async () => {
      try { await document.exitFullscreen(); } catch (err) { setError(err instanceof Error ? err.message : "无法退出全屏"); }
    }}>退出含字幕全屏</button>}
  </div>
  <div className="companion-downloads">
    <label><input type="checkbox" checked={styled} onChange={event => setStyled(event.target.checked)} />样式字幕预览</label>
    <button type="button" className="ny-button" onClick={async () => {
      try {
        if (!wrapper.current?.requestFullscreen) throw new Error("当前浏览器不支持含字幕全屏");
        await wrapper.current.requestFullscreen();
      } catch (err) { setError(err instanceof Error ? err.message : "无法全屏"); }
    }}>含字幕全屏</button>
  </div>
  {error && <p role="alert" className="companion-error">{error}</p>}</>;
}
