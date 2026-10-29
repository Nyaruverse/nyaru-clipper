/** 预览弹幕层：按播放进度拉取时间窗内的弹幕，匀速滚动，轨道/速度与烧录 ASS 一致。
 *
 * 性能要点（60fps）：
 * - 位移只用 transform（合成层动画），由合成线程逐帧推进，不触发重排重绘；
 * - 每条的 animation-delay 只在它「进入画面」的那一帧计算一次并写入 style，之后永不改写，
 *   因此 React 的其它重渲染（timeupdate、查询刷新）不会重启或回拨动画；
 * - 进入/离开画面由 requestAnimationFrame 按视频时钟判定，且只在集合变化时 setState；
 * - 相邻时间窗的弹幕合并进同一张表并按原有轨道优先排布，窗口滚动时不会整层重挂载；
 * - 拖动进度条时只重建动画锚点（epoch 递增换 key），不重新拉取数据。
 */
import { memo, useEffect, useMemo, useRef, useState } from 'react';
import type { RefObject } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api, type DanmakuWindow } from './companionApi';

const SCROLL_SPEED = 240;   // px/s（1080p 基准），与 danmaku_render 一致
const CANVAS_HEIGHT = 1080;
const LIFETIME = 8;         // 单条弹幕在屏时长（秒）
const CHUNK = 20;           // 时间窗粒度
const MAX_ACTIVE = 140;     // 同屏上限，超出直接丢弃（与 B站拥挤时的丢弃行为一致）
const SC_PREFIX = '【SC ¥';

interface Props {
  video: RefObject<HTMLVideoElement>;
  jobId: string;
  /** 当前预览视频在原视频时间轴上的起点（完整视频为 0，切片为切片开始时间） */
  offset: number;
  paused: boolean;
  fontSize: number;
  areaHeight: number;
  scale: number;
  box: { width: number; height: number; left: number; top: number };
}

interface Entry { key: string; at: number; text: string; color: number | null }
interface Placed extends Entry { track: number; width: number }

function textWidth(text: string, size: number) {
  let units = 0;
  for (const char of text) units += (char.codePointAt(0) ?? 0) > 0x2e80 ? 1 : 0.55;
  return units * size;
}

function cssColor(value: number | null) {
  if (typeof value !== 'number' || value < 0 || value > 0xffffff) return '#ffffff';
  return `rgb(${value & 0xff},${(value >> 8) & 0xff},${(value >> 16) & 0xff})`;
}

function sameKeys(a: string[], b: string[]) {
  return a.length === b.length && a.every((key, index) => key === b[index]);
}

function DanmakuLayer({ video, jobId, offset, paused, fontSize, areaHeight, scale, box }: Props) {
  const [chunk, setChunk] = useState(0);
  const [epoch, setEpoch] = useState(0);
  const [placements, setPlacements] = useState<Map<string, Placed>>(() => new Map());
  const [active, setActive] = useState<string[]>([]);

  const clock = useRef(0);                 // 原视频时间轴上的当前时间
  const chunkRef = useRef(0);
  const entriesRef = useRef<Map<string, Entry>>(new Map());
  const placementsRef = useRef<Map<string, Placed>>(new Map());
  const activeRef = useRef<string[]>([]);
  const delaysRef = useRef<Map<string, number>>(new Map());   // 每条弹幕的动画锚点（只写一次）
  const rafRef = useRef(0);

  const query = useQuery({
    queryKey: ['companion', 'danmaku-window', jobId, chunk],
    queryFn: () => api<DanmakuWindow>(`/jobs/${jobId}/danmaku/window?start=${Math.max(0, chunk * CHUNK - 12)}&end=${chunk * CHUNK + CHUNK + 12}`),
    enabled: box.width > 0,
    staleTime: 60_000,
    // 换窗口时保留上一窗数据，避免每 20 秒整层弹幕消失再出现
    placeholderData: (previous: DanmakuWindow | undefined) => previous,
  });

  // 合并新时间窗的弹幕（按 时间+文本 去重），并清理已经完全滚出屏幕的旧条目
  useEffect(() => {
    const data = query.data;
    if (!data) return;
    const map = entriesRef.current;
    for (const [at, text, color] of data.entries) {
      const key = `${at}|${text}`;
      if (!map.has(key)) map.set(key, { key, at, text, color });
    }
    for (const [key, item] of map) if (item.at + LIFETIME < clock.current - 30) { map.delete(key); delaysRef.current.delete(key); }
  }, [query.data]);

  // 重新排轨道：优先沿用上次的轨道，时间窗滚动时不会让已在屏上的弹幕换行
  useEffect(() => {
    const order = [...entriesRef.current.values()].sort((a, b) => a.at - b.at);
    const tracks = Math.max(1, Math.floor(CANVAS_HEIGHT * areaHeight / 100 / (fontSize * 1.2)));
    const free = new Array<number>(tracks).fill(0);
    const next = new Map<string, Placed>();
    for (const item of order) {
      const width = textWidth(item.text, fontSize);
      const previous = placementsRef.current.get(item.key);
      const track = previous !== undefined && previous.track < tracks && free[previous.track] <= item.at
        ? previous.track : free.findIndex(value => value <= item.at);
      if (track < 0) continue;
      free[track] = item.at + width / SCROLL_SPEED;
      next.set(item.key, { ...item, track, width });
    }
    placementsRef.current = next;
    for (const key of delaysRef.current.keys()) if (!next.has(key)) delaysRef.current.delete(key);
    setPlacements(next);
  }, [query.data, fontSize, areaHeight]);

  // 切换任务 / 切换切片：时间轴完全变了，清空缓存并从 0 重新取窗口
  useEffect(() => {
    entriesRef.current = new Map();
    placementsRef.current = new Map();
    activeRef.current = [];
    delaysRef.current.clear();
    chunkRef.current = -1;
    clock.current = 0;
    setChunk(0);
    setPlacements(new Map());
    setActive([]);
    setEpoch(value => value + 1);
  }, [jobId, offset]);

  // 拖动进度条：丢弃动画锚点，下一帧按新时间重算位置（不重新拉数据，条目时间轴仍然有效）
  useEffect(() => {
    const element = video.current;
    if (!element) return;
    const reset = () => {
      delaysRef.current.clear();
      activeRef.current = [];
      setActive([]);
      setEpoch(value => value + 1);
    };
    element.addEventListener('seeked', reset);
    return () => element.removeEventListener('seeked', reset);
  }, [video]);

  // 用 requestAnimationFrame 跟随视频时钟：只在「进入/离开画面」的集合变化时触发渲染
  useEffect(() => {
    const tick = () => {
      rafRef.current = requestAnimationFrame(tick);
      const element = video.current;
      const absolute = (element ? element.currentTime : 0) + offset;
      clock.current = absolute;

      const nextChunk = Math.max(0, Math.floor(Math.max(0, absolute + 8) / CHUNK));
      if (nextChunk !== chunkRef.current) {
        chunkRef.current = nextChunk;
        setChunk(nextChunk);
      }

      const keys: string[] = [];
      for (const item of placementsRef.current.values()) {
        if (item.at > absolute) break;                        // 已按时间升序，后面的都还没到
        if (absolute < item.at + LIFETIME) {
          keys.push(item.key);
          if (!delaysRef.current.has(item.key)) delaysRef.current.set(item.key, -(absolute - item.at));
          if (keys.length >= MAX_ACTIVE) break;
        }
      }
      if (!sameKeys(keys, activeRef.current)) {
        activeRef.current = keys;
        setActive(keys);
      }
    };
    rafRef.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(rafRef.current);
  }, [video, offset]);

  const items = useMemo(() => active.map(key => placements.get(key)).filter((item): item is Placed => !!item), [active, placements]);
  const scCards = items.filter(item => item.text.startsWith(SC_PREFIX));
  const rolling = items.filter(item => !item.text.startsWith(SC_PREFIX));

  if (!(box.width > 0)) return null;
  const pixelSize = Math.max(8, fontSize * scale);
  const areaHeightPx = box.height * areaHeight / 100;
  const scCardHeight = pixelSize * 2.6;

  return <div className="dm-layer" style={{ left: box.left, top: box.top, width: box.width, height: areaHeightPx }} aria-hidden="true">
    {rolling.map(item => {
      const width = item.width * scale;
      return <span key={`${item.key}#${epoch}`} className="dm-item"
        style={{
          top: item.track * fontSize * 1.2 * scale,
          fontSize: pixelSize,
          color: cssColor(item.color),
          // 锚点只在这里写一次：本帧之前已经播放了 (now - at) 秒
          animationDelay: `${(delaysRef.current.get(item.key) ?? 0).toFixed(3)}s`,
          animationDuration: `${((box.width + width) / (SCROLL_SPEED * scale)).toFixed(2)}s`,
          animationPlayState: paused ? 'paused' : 'running',
          ['--dm-start' as string]: `${box.width}px`,
          ['--dm-end' as string]: `${-width}px`,
        }}>{item.text}</span>;
    })}
    {scCards.map((item, index) => <div key={`${item.key}#${epoch}`} className="dm-sc"
      style={{ bottom: 8 + index * scCardHeight, fontSize: pixelSize * 0.85, maxWidth: box.width - 16 }}>
      <strong>¥{item.text.slice(SC_PREFIX.length).split('】')[0]}</strong>
      <span>{item.text.split('】').slice(1).join('】')}</span>
    </div>)}
  </div>;
}

export const DanmakuOverlay = memo(DanmakuLayer);
