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
  readonly unified_operations?: boolean;
  readonly runtime_id?: string | null;
  readonly engine_missing?: Partial<Record<'whisper.cpp' | 'whisperx', string[]>>;
  readonly ready: boolean;
  readonly missing: string[];
  readonly translation_configured: boolean;
  readonly translation_model?: string;
  readonly translation_config_error?: string | null;
  readonly llm_provider?: LlmProvider;
  readonly llm_model?: string;
  readonly llm_configured?: boolean;
  readonly chatgpt?: ChatGPTStatus;
}
export interface ChatGPTModel { readonly slug: string; readonly display_name: string }

export interface Clip {
  video: string;
  subtitles: string;
  bilingual_subtitles?: string | null;
  start: number;
  end: number;
  score: number | null;
  reasons: string[];
  title?: string;
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
  mode: "ranges" | "highlights" | "saozi";
  live?: boolean;
  saozi_model?: string;
  llm_provider?: LlmProvider;
  can_stop?: boolean;
  capture_warning?: string | null;
  capture_end_reason?: "live_ended" | "stopped" | "connection_lost" | null;
  subtitle_template?: {arctime_template_id?:string|null;name:string;style:import('./subtitleStyle').SubtitleStyle} | null;
  subtitle_style_error?: string | null;
  discontinuities?: number[];
  clips: Clip[];
  segments: Segment[];
  has_source: boolean;
  can_resume: boolean;
  language: string;
  readonly bilingual_suffix?: string;
  bilingual_segments: Segment[];
  bilingual_files?: string[];
  translation: { state: string; error: string | null; done: number; total: number; message: string | null; model?: string };
}
export interface JobInput { url: string; ranges: [string, string][]; highlights: number | null; language: string; saozi?: boolean; live?: boolean; subtitle_template_id?: string; engine?: 'whisper.cpp' | 'whisperx' }

export async function api<T>(path: string, body?: object): Promise<T> {
  const response = await fetch(`/companion-api${path}`, body ? { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) } : undefined);
  const result: unknown = await response.json();
  if (!response.ok) {
    const detail = typeof result === "object" && result !== null && "detail" in result ? result.detail : null;
    throw new Error(typeof detail === "string" ? detail : "请求失败，请检查输入或本地服务");
  }
  return result as T;
}

export function time(value: number): string {
  const tenths = Math.round(Math.max(0, value) * 10);
  const hours = Math.floor(tenths / 36000);
  return `${hours ? `${String(hours).padStart(2, "0")}:` : ""}${String(Math.floor(tenths / 600) % 60).padStart(2, "0")}:${((tenths % 600) / 10).toFixed(1).padStart(4, "0")}`;
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
export const running = (job?: Job) => !!job && (! ["completed", "failed", "interrupted", "cancelled", "queued", "paused"].includes(job.state) || job.translation?.state === "translating" || job.subtitle_export_busy);
export const statusLabel = (job: Job) => ({ queued: "等待队列", paused: "已暂停", cancelled: "已取消", completed: "已完成", failed: "失败", interrupted: "已中断", preparing: "检查环境", uploading: "导入中", recording: "实时录制", analyzing: "段落分析", downloading: "下载中", downloaded: "下载完成", transcribing: "识别中", subtitles_ready: "字幕已生成", exporting: "导出中" }[job.state] ?? "处理中");
export const fileUrl = (id: string, name: string, download = false) => `/companion-api/jobs/${id}/files/${encodeURIComponent(name)}${download ? "?download=true" : ""}`;

export function bilingualFile(job: Pick<Job, 'bilingual_suffix'> | undefined, name: string, extension: 'srt' | 'vtt' = 'srt'): string {
  return name.replace(/\.srt$/, `${job?.bilingual_suffix ?? '.ja-zh'}.${extension}`);
}
