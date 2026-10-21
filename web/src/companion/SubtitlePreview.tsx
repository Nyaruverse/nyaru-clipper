import { useEffect, useRef, useState, type RefObject, type ReactNode } from 'react';
import { activeCue, layoutCue, type CueSegment, type SubtitleStyle } from './subtitleStyle';
import { DocumentOverlay } from './DocumentOverlay';
import type { Language, SubtitleDocument } from './subtitleDocument';
interface Props { video: RefObject<HTMLVideoElement>; segments: CueSegment[]; bilingual: CueSegment[]; offset: number; style: SubtitleStyle; children: ReactNode; source: string;
  document?: SubtitleDocument | null; jobId?: string; selected?: readonly string[]; language?: Language; editing?: boolean; showBilingual?: boolean;
  onMove?: (dx: number, dy: number) => void; onTime?: (time: number) => void; loop?: { start: number; end: number } | null;
}
export function SubtitlePreview({video,segments,bilingual,offset,style,children,source,document: documentDraft,jobId,selected=[],language='original',editing=false,showBilingual=false,onMove,onTime,loop}: Props) {
  const wrapper = useRef<HTMLDivElement>(null);
  const [time,setTime] = useState(0);
  const [box,setBox] = useState({width:0,height:0,left:0,top:0});
  const [error,setError] = useState('');
  const [styled,setStyled] = useState(true);
  const [fullscreen,setFullscreen] = useState(false);
  useEffect(() => {
    const update = () => setFullscreen(document.fullscreenElement === wrapper.current);
    document.addEventListener('fullscreenchange',update);
    return () => document.removeEventListener('fullscreenchange',update);
  },[]);
  useEffect(() => {
    const element = video.current;
    if (!element) return;
    const update = () => {
      if (loop && !element.paused && (element.currentTime + offset >= loop.end || element.currentTime + offset < loop.start)) element.currentTime = Math.max(0,loop.start - offset);
      setTime(element.currentTime);
      onTime?.(element.currentTime + offset);
      const width = element.clientWidth, height = element.clientHeight;
      const ratio = element.videoWidth / element.videoHeight || 16 / 9;
      const imageWidth = Math.min(width,height * ratio), imageHeight = imageWidth / ratio;
      setBox({width:imageWidth,height:imageHeight,left:(width-imageWidth)/2,top:(height-imageHeight)/2});
      for (const track of Array.from(element.textTracks ?? [])) track.mode = styled ? 'hidden' : 'showing';
    };
    const events = ['timeupdate','seeking','seeked','pause','loadedmetadata','loadeddata'];
    events.forEach(event => element.addEventListener(event,update));
    element.textTracks?.addEventListener?.('addtrack',update);
    const observer = typeof ResizeObserver === 'undefined' ? null : new ResizeObserver(update);
    observer?.observe(element); update();
    return () => { events.forEach(event => element.removeEventListener(event,update)); element.textTracks?.removeEventListener?.('addtrack',update); observer?.disconnect(); };
  },[video,source,styled,offset,onTime,loop?.start,loop?.end]);
  const cue = activeCue({segments,bilingual,time,offset});
  const layout = cue ? layoutCue(cue,style,box.height ? 1080 * box.width / box.height : 1920) : null;
  const scale = box.height / 1080;
  return <><div ref={wrapper} className="subtitle-video-wrapper">{children}
    {styled && documentDraft && jobId && <div className="subtitle-overlay" aria-label="样式字幕预览" style={{width:box.width,height:box.height,left:box.left,top:box.top}}><DocumentOverlay id={jobId} document={documentDraft} time={time + offset} bilingual={showBilingual} selected={selected} language={language} editing={editing} onMove={onMove ?? (() => {})} onPause={() => video.current?.pause()} /></div>}
    {styled && !documentDraft && layout && <div className="subtitle-overlay" aria-label="样式字幕预览" style={{width:box.width,height:box.height,left:box.left,top:box.top}}>
      {(['original','translation'] as const).map(key => { const textStyle = style[key], entry = layout[key]; return entry.text && <div key={key} className="subtitle-line" style={{[textStyle.position]:entry.margin * scale}}><span data-testid={`subtitle-${key}`} className="subtitle-text" style={{paddingInline:textStyle.outline * scale,fontFamily:`${JSON.stringify(textStyle.font)}, sans-serif`,fontSize:textStyle.size * scale,lineHeight:1.2,color:textStyle.color,WebkitTextStroke:`${textStyle.outline * scale}px ${textStyle.outline_color}`,paintOrder:'stroke fill',backgroundColor:`${textStyle.background_color}${Math.round(textStyle.background_opacity*255).toString(16).padStart(2,'0')}`}}>{entry.text}</span></div>; })}
    </div>}
    {fullscreen && <button type="button" className="ny-button subtitle-fullscreen-exit" onClick={async () => {try {await document.exitFullscreen();} catch (err) {setError(err instanceof Error ? err.message : "无法退出全屏");}}}>退出含字幕全屏</button>}
  </div><div className="companion-downloads"><label><input type="checkbox" checked={styled} onChange={event => setStyled(event.target.checked)} />样式字幕预览</label><button type="button" className="ny-button" onClick={async () => { try { if (!wrapper.current?.requestFullscreen) throw new Error('当前浏览器不支持含字幕全屏'); await wrapper.current.requestFullscreen(); } catch (err) { setError(err instanceof Error ? err.message : '无法全屏'); } }}>含字幕全屏</button></div>
  {!documentDraft && layout && !layout.fits && <p role="alert" className="companion-error">字幕超出画布，请减小字号、边距或文本长度。</p>}{error && <p role="alert" className="companion-error">{error}</p>}</>;
}
