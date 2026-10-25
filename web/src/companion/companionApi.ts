export type LlmProvider = "deepseek" | "chatgpt";
export interface ChatGPTStatus {
  readonly connected: boolean;
  readonly sharing: boolean;
  readonly authorization_pending?: boolean;
  readonly account_label: string | null;
  readonly error: string | null;
  readonly manage_url: string;
}
export interface CompanionConfig {
  readonly ready: boolean;
  readonly missing: string[];
  readonly translation_configured: boolean;
  readonly translation_model?: string;
  readonly translation_config_error?: string | null;
  readonly llm_provider?: LlmProvider;
  readonly llm_model?: string;
  readonly llm_configured?: boolean;
  readonly chatgpt?: ChatGPTStatus;
  readonly glossary_collect_candidates?: boolean;
}
export interface ChatGPTModel { readonly slug: string; readonly display_name: string }

export type BurnVariant = "bilingual" | "zh" | "original";
export interface BurnEntry { state: string; file: string | null; error: string | null; sha256?: string; progress?: number; segments_done?: number; segments_total?: number }
export interface OutlineLayer { color: string; width: number }
export interface LegacyTextStyle {
  font_family: string;
  font_size: number;
  text_color: string;
  background_color: string;
  background_opacity: number;
  outlines: OutlineLayer[];
  pos_x: number;
  pos_y: number;
  align: "left" | "center" | "right";
}
export interface LegacyStyleConfig { original: LegacyTextStyle; translated: LegacyTextStyle }
export interface LegacyStyleStore { current: LegacyStyleConfig; templates: Record<string, LegacyStyleConfig>; shapes: Shape[] }
export type SubtitleMode = "bilingual" | "zh" | "original";

export interface Clip {
  video: string;
  subtitles: string;
  bilingual_subtitles?: string | null;
  start: number;
  end: number;
  score: number | null;
  reasons: string[];
  title?: string;
  burns?: Record<string, BurnEntry>;
}
export interface Segment { id: string; start_seconds: number; end_seconds: number; text: string }
export interface Job {
  id: string;
  state: string;
  subtitle_export_busy?: boolean;
  phase: string;
  message: string;
  error: string | null;
  started_at: number;
  duration: number | null;
  /** 新建任务时保留的来源链接，用于生成切片时自动拉取弹幕 */
  url?: string | null;
  mode: "ranges" | "highlights" | "saozi" | "full";
  live?: boolean;
  saozi_model?: string;
  llm_provider?: LlmProvider;
  can_stop?: boolean;
  capture_warning?: string | null;
  subtitle_template?: {name:string;style:import('./subtitleStyle').SubtitleStyle} | null;
  subtitle_style_error?: string | null;
  discontinuities?: number[];
  clips: Clip[];
  source_burns?: Record<string, BurnEntry>;
  /** 自定义时间段合成的记录：键为 range-<起点毫秒>-<终点毫秒> */
  range_burns?: Record<string, Record<string, BurnEntry>>;
  segments: Segment[];
  has_source: boolean;
  can_resume: boolean;
  language: string;
  bilingual_segments: Segment[];
  zh_segments: Segment[];
  bilingual_files?: string[];
  translation: { state: string; error: string | null; done: number; total: number; message: string | null; model?: string };
}
export interface JobInput { url: string; ranges: [string, string][]; highlights: number | null; language: string; saozi?: boolean; live?: boolean; subtitle_template_id?: string }

// 任务记录磁盘占用与批量清理／删除
export interface JobStorage { readonly total: number; readonly cleanable: number }
export interface StorageSnapshot { readonly jobs: Record<string, JobStorage>; readonly total: number; readonly cleanable: number }
export interface BatchResultItem { readonly id: string; readonly ok: boolean; readonly freed: number; readonly error?: string }
export interface BatchResult { readonly results: BatchResultItem[]; readonly freed: number }

export function bytes(value: number): string {
  if (!value) return "0 B";
  const units = ["B", "KB", "MB", "GB", "TB"];
  const index = Math.min(units.length - 1, Math.floor(Math.log(value) / Math.log(1024)));
  return `${(value / 1024 ** index).toFixed(index === 0 ? 0 : 1)} ${units[index]}`;
}

export async function api<T>(path: string, body?: object, method?: string): Promise<T> {
  const init: RequestInit = {};
  if (body) {
    init.method = method ?? "POST";
    init.headers = { "Content-Type": "application/json" };
    init.body = JSON.stringify(body);
  } else if (method) {
    init.method = method;
  }
  const response = await fetch(`/companion-api${path}`, init);
  const result: unknown = await response.json();
  if (!response.ok) {
    const detail = typeof result === "object" && result !== null && "detail" in result ? result.detail : null;
    throw new Error(typeof detail === "string" ? detail : "请求失败，请检查输入或本地服务");
  }
  return result as T;
}

export function time(value: number): string {
  const seconds = Math.max(0, value);
  const hours = Math.floor(seconds / 3600);
  return `${hours ? `${String(hours).padStart(2, "0")}:` : ""}${String(Math.floor(seconds / 60) % 60).padStart(2, "0")}:${(seconds % 60).toFixed(1).padStart(4, "0")}`;
}
export function parseTime(value: string): number {
  const parts = value.trim().replace(",", ".").split(":");
  if (parts.length > 3 || parts.some(part => !/^\d+(?:\.\d+)?$/.test(part)) || (parts.length > 1 && (parts.slice(1).some(part => Number(part) >= 60) || parts.slice(0, -1).some(part => part.includes("."))))) {
    throw new Error("时间请填写秒数、MM:SS 或 HH:MM:SS");
  }
  const result = parts.reduce((total, part) => total * 60 + Number(part), 0);
  if (!Number.isFinite(result)) throw new Error("时间必须为有限数值");
  return result;
}
export const running = (job?: Job) => !!job && (! ["completed", "failed", "interrupted", "cancelled"].includes(job.state) || job.translation?.state === "translating" || job.subtitle_export_busy
  || Object.values(job.source_burns ?? {}).some(entry => entry.state === "burning")
  || Object.values(job.range_burns ?? {}).some(burns => Object.values(burns).some(entry => entry.state === "burning"))
  || job.clips.some(item => Object.values(item.burns ?? {}).some(entry => entry.state === "burning")));
export const cancellable = (job?: Job) => !!job && ["preparing", "downloading", "downloaded", "transcribing", "subtitles_ready", "exporting", "translating", "cancelling"].includes(job.state);
export const statusLabel = (job: Job) => ({ completed: "已完成", failed: "失败", interrupted: "已中断", cancelled: "已终止", cancelling: "正在终止", preparing: "检查环境", uploading: "导入中", recording: "实时录制", analyzing: "段落分析", downloading: "下载中", downloaded: "下载完成", transcribing: "识别中", subtitles_ready: "字幕已生成", exporting: "导出中" }[job.state] ?? "处理中");
export const fileUrl = (id: string, name: string, download = false) => `/companion-api/jobs/${id}/files/${encodeURIComponent(name)}${download ? "?download=true" : ""}`;

/** 切片本地时间轴字幕：取与 [start,end) 相交的段并减去 start 偏移 */
export function clipSegments(segments: Segment[], start: number, end: number): Segment[] {
  return segments
    .filter(s => s.end_seconds > start && s.start_seconds < end)
    .map(s => ({ ...s, start_seconds: Math.max(s.start_seconds, start) - start, end_seconds: Math.min(s.end_seconds, end) - start }));
}

// ---- 本地定制功能类型（术语表 / 内容切片 / 切片视频 / 图形绘制）----

export interface Shape {
  x: number; y: number; width: number; height: number; radius: number;
  fill_color: string; fill_opacity: number; outline_color: string; outline_width: number;
}
export type TermCategory = "人名" | "作品名" | "术语";
export const TERM_CATEGORIES: TermCategory[] = ["人名", "作品名", "术语"];
export interface GlossaryTerm { src: string; dst: string; category: TermCategory }
export interface GlossaryCandidate { src: string; dst: string; category: TermCategory }
export interface GlossaryStore { terms: GlossaryTerm[]; candidates: GlossaryCandidate[]; ignored: string[] }
export interface TopicSegment {
  index: number; start_id: number; end_id: number;
  start_seconds: number; end_seconds: number; cue_count: number;
  title: string; summary: string; preview: string; analyzed: boolean;
  /** 弹幕互动评分（未导入弹幕时为空） */
  dm_count?: number | null; dm_rate?: number | null; dm_users?: number | null;
  dm_peak?: number | null; dm_peak_time?: number | null; dm_repeat?: number | null;
  score?: number | null; grade?: string | null;
  /** 音频因子：切片内响度 95 分位（dBFS）与每分钟兴奋帧数（笑声/尖叫近似） */
  loudness_db?: number | null; laugh_rate?: number | null;
  /** 文本因子：本场动态热词命中次数/密度、命中词与风险词 */
  meme_hits?: number | null; meme_rate?: number | null;
  hot_words?: string[] | null;
  risk_terms?: string[] | null; risk?: boolean | null;
  /** 弹幕形态与 0–1 形态分 */
  dm_shape?: string | null; dm_shape_score?: number | null;
}
export interface TopicQuote { text: string; start?: number | null; score?: number | null }
export interface TopicSegmentStore {
  identity: Record<string, string>;
  state: "not_started" | "stale" | "completed" | string;
  error: string | null; created_at: number;
  total_cues: number; covered_cues: number; truncated: boolean;
  range_start?: number | null; range_end?: number | null;
  scored_at?: number | null;
  /** 本场从高分切片提取的热词与金句，streamer 为主播画像名 */
  streamer?: string | null;
  vocabulary?: string[] | null;
  quotes?: TopicQuote[] | null;
  segments: TopicSegment[];
}
export interface DanmakuSummary {
  count: number;
  source: string | null;
  span?: number;
  /** 自动拉取时记录的视频链接与稿件标题 */
  url?: string | null;
  title?: string | null;
}
export interface BiliAuthStatus {
  logged_in: boolean;
  name?: string | null;
  mid?: number | null;
}
export interface BiliLoginQrCode {
  key: string;
  url: string;
  /** 内联 SVG data URI，直接作为 img src */
  image: string;
  expires_in: number;
}
export interface BiliLoginPoll {
  state: "waiting" | "scanned" | "expired" | "success";
  message?: string;
  name?: string | null;
}
export interface TopicClipItem { index: number; file: string | null; state: "completed" | "failed" | string; error: string | null }
export interface TopicClipStore {
  state: "not_started" | "stale" | "running" | "completed" | "failed" | string;
  mode?: "separate" | "combined";
  variant?: "bilingual" | "zh" | "original";
  indices?: number[]; done?: number; total?: number;
  message?: string; error?: string | null;
  items?: TopicClipItem[];
  combined?: { file: string; state: string; error: string | null } | null;
  created_at?: number;
}
