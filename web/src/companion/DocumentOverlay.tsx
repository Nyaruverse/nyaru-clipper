import { useEffect, useRef, useState } from 'react';
import { activeDocumentCues, effectiveAnchor, documentProblem, type Language, type SubtitleDocument } from './subtitleDocument';

interface Props {
  readonly id: string; readonly document: SubtitleDocument; readonly time: number; readonly bilingual: boolean;
  readonly selected: readonly string[]; readonly language: Language; readonly editing: boolean;
  readonly onMove: (dx: number, dy: number) => void; readonly onPause?: () => void;
}

export function DocumentOverlay({ id, document: doc, time, bilingual, selected, language, editing, onMove, onPause }: Props) {
  const active = activeDocumentCues(doc, time);
  const generation = useRef({ document: doc, serial: 0 });
  if (generation.current.document !== doc) generation.current = { document: doc, serial: generation.current.serial + 1 };
  const scene = active.map(cue => cue.id).join('/');
  const key = `${id}/${generation.current.serial}/${scene}/${bilingual}`;
  const cache = useRef(new Map<string, string>());
  const [image, setImage] = useState<{ key: string; url: string } | null>(null);
  const [error, setError] = useState('');
  const [safeArea, setSafeArea] = useState(true);
  const [snap, setSnap] = useState(true);
  const canvas = useRef<HTMLDivElement>(null);
  const drag = useRef<{ x: number; y: number; anchorX: number; anchorY: number; appliedX: number; appliedY: number } | null>(null);
  const timeRef = useRef(time);
  timeRef.current = time;
  const problem = documentProblem(doc);

  useEffect(() => {
    if (!scene || problem) return;
    const cached = cache.current.get(key);
    if (cached) { setImage({ key, url: cached }); setError(''); return; }
    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      setError('');
      void fetch(`/companion-api/jobs/${id}/subtitle-preview`, { method: 'POST', signal: controller.signal,
        headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ frame: { ...doc, cues: active }, time: timeRef.current, bilingual }) }).then(async response => {
        if (!response.ok) {
          const result: unknown = await response.json();
          throw new Error(typeof result === 'object' && result !== null && 'detail' in result && typeof result.detail === 'string' ? result.detail : '精确预览生成失败');
        }
        const blob = await response.blob();
        if (controller.signal.aborted) return;
        const url = URL.createObjectURL(blob);
        cache.current.set(key, url);
        if (cache.current.size > 24) {
          const oldest = cache.current.keys().next().value;
          if (oldest) { const old = cache.current.get(oldest); if (old) URL.revokeObjectURL(old); cache.current.delete(oldest); }
        }
        setImage({ key, url });
      }).catch((failure: unknown) => {
        if (!controller.signal.aborted) setError(failure instanceof Error ? failure.message : '精确预览失败，请重试');
      });
    }, 80);
    return () => { window.clearTimeout(timer); controller.abort(); };
  // A scene is static within its interval; advancing the clock must not restart rendering.
  }, [key, id, scene, problem]);

  useEffect(() => {
    const urls = cache.current;
    return () => { for (const url of urls.values()) URL.revokeObjectURL(url); urls.clear(); };
  }, [id]);

  const cue = active.find(item => selected.includes(item.id));
  const point = cue ? effectiveAnchor(doc, cue, language, bilingual) : null;
  return <div ref={canvas} className="document-overlay" aria-label="精确字幕画布">
    {!!scene && !problem && image?.key === key && <img src={image.url} alt="精确字幕预览" draggable={false} />}
    {!!scene && !problem && image?.key !== key && !error && <span className="cue-render-status" role="status">字幕渲染中…</span>}
    {(error || problem) && <span className="cue-render-status is-error" role="alert">{error || problem}</span>}
    {editing && <>
      {safeArea && <div className="cue-safe-area" aria-hidden="true"><span /><i /></div>}
      <div className="cue-canvas-options"><label><input type="checkbox" checked={safeArea} onChange={event => setSafeArea(event.target.checked)} />参考线／安全区</label><label><input type="checkbox" checked={snap} onChange={event => setSnap(event.target.checked)} />吸附</label></div>
      {point && (bilingual || language === 'original') && <button type="button" className="cue-position-handle" aria-label={`${language === 'original' ? '原文' : '译文'}位置锚点`} title="拖动或使用方向键微调；Shift 为 10 像素" style={{ left: `${point.x / doc.width * 100}%`, top: `${point.y / doc.height * 100}%` }}
        onPointerDown={event => { if (event.button !== 0) return; onPause?.(); event.currentTarget.setPointerCapture(event.pointerId); drag.current = { x: event.clientX, y: event.clientY, anchorX: point.x, anchorY: point.y, appliedX: 0, appliedY: 0 }; }}
        onPointerMove={event => {
          const bounds = canvas.current?.getBoundingClientRect(), previous = drag.current;
          if (!previous || !bounds?.width || !bounds.height) return;
          let dx = (event.clientX - previous.x) * doc.width / bounds.width, dy = (event.clientY - previous.y) * doc.height / bounds.height;
          if (event.shiftKey) { if (Math.abs(dx) > Math.abs(dy)) dy = 0; else dx = 0; }
          if (snap && !event.altKey) {
            for (const x of [doc.width * 0.05, doc.width / 2, doc.width * 0.95]) if (Math.abs(previous.anchorX + dx - x) < 5 * doc.width / bounds.width) dx = x - previous.anchorX;
            for (const y of [doc.height * 0.05, doc.height / 2, doc.height * 0.95]) if (Math.abs(previous.anchorY + dy - y) < 5 * doc.height / bounds.height) dy = y - previous.anchorY;
          }
          const changeX = dx - previous.appliedX, changeY = dy - previous.appliedY;
          drag.current = { ...previous, appliedX: dx, appliedY: dy };
          if (changeX || changeY) onMove(changeX, changeY);
        }}
        onPointerUp={() => { drag.current = null; }} onPointerCancel={() => { drag.current = null; }}
        onKeyDown={event => {
          const directions: Readonly<Record<string, readonly [number, number]>> = { ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1] };
          const direction = directions[event.key];
          if (direction) { event.preventDefault(); event.stopPropagation(); const step = event.shiftKey ? 10 : 1; onMove(direction[0] * step, direction[1] * step); }
        }}><span aria-hidden="true">+</span></button>}
    </>}
  </div>;
}
