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
  discontinuities?: number[];
  clips: Clip[];
  segments: Segment[];
  has_source: boolean;
  can_resume: boolean;
  language: string;
  bilingual_segments: Segment[];
  bilingual_files?: string[];
  translation: { state: string; error: string | null; done: number; total: number; message: string | null; model?: string };
}
export interface JobInput { url: string; ranges: [string, string][]; highlights: number | null; language: string; saozi?: boolean; live?: boolean }

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
export const running = (job?: Job) => !!job && (! ["completed", "failed", "interrupted"].includes(job.state) || job.translation?.state === "translating" || job.subtitle_export_busy);
export const statusLabel = (job: Job) => ({ completed: "已完成", failed: "失败", interrupted: "已中断", preparing: "检查环境", uploading: "导入中", recording: "实时录制", analyzing: "段落分析", downloading: "下载中", downloaded: "下载完成", transcribing: "识别中", subtitles_ready: "字幕已生成", exporting: "导出中" }[job.state] ?? "处理中");
export const fileUrl = (id: string, name: string, download = false) => `/companion-api/jobs/${id}/files/${encodeURIComponent(name)}${download ? "?download=true" : ""}`;
