import { useEffect, useRef, useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowDownToLine, Check, Film, Plus, Scissors, X } from "lucide-react";

interface Clip {
  video: string;
  subtitles: string;
  start: number;
  end: number;
  score: number | null;
  reasons: string[];
}
interface Segment { id: string; start_seconds: number; end_seconds: number; text: string }
interface Job {
  id: string;
  state: string;
  phase: string;
  message: string;
  error: string | null;
  started_at: number;
  duration: number | null;
  mode: "ranges" | "highlights";
  clips: Clip[];
  segments: Segment[];
  has_source: boolean;
  can_resume: boolean;
  language: string;
  bilingual_segments: Segment[];
  translation: { state: string; error: string | null; done: number; total: number; message: string | null; model?: string };
}
interface JobInput { url: string; ranges: [string, string][]; highlights: number | null; language: string }

async function api<T>(path: string, body?: object): Promise<T> {
  const response = await fetch(`/companion-api${path}`, body ? { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) } : undefined);
  const result: unknown = await response.json();
  if (!response.ok) {
    const detail = typeof result === "object" && result !== null && "detail" in result ? result.detail : null;
    throw new Error(typeof detail === "string" ? detail : "请求失败，请检查输入或本地服务");
  }
  return result as T;
}

function time(value: number): string {
  const seconds = Math.max(0, value);
  const hours = Math.floor(seconds / 3600);
  return `${hours ? `${String(hours).padStart(2, "0")}:` : ""}${String(Math.floor(seconds / 60) % 60).padStart(2, "0")}:${(seconds % 60).toFixed(1).padStart(4, "0")}`;
}
function parseTime(value: string): number {
  const parts = value.trim().replace(",", ".").split(":");
  if (parts.length > 3 || parts.some(part => !/^\d+(?:\.\d+)?$/.test(part)) || (parts.length > 1 && (parts.slice(1).some(part => Number(part) >= 60) || parts.slice(0, -1).some(part => part.includes("."))))) {
    throw new Error("时间请填写秒数、MM:SS 或 HH:MM:SS");
  }
  const result = parts.reduce((total, part) => total * 60 + Number(part), 0);
  if (!Number.isFinite(result)) throw new Error("时间必须为有限数值");
  return result;
}
const running = (job?: Job) => !!job && (! ["completed", "failed", "interrupted"].includes(job.state) || job.translation?.state === "translating");
const statusLabel = (job: Job) => ({ completed: "已完成", failed: "失败", interrupted: "已中断", preparing: "检查环境", downloading: "下载中", downloaded: "下载完成", transcribing: "识别中", subtitles_ready: "字幕已生成", exporting: "导出中" }[job.state] ?? "处理中");
const fileUrl = (id: string, name: string, download = false) => `/companion-api/jobs/${id}/files/${encodeURIComponent(name)}${download ? "?download=true" : ""}`;

export function Companion() {
  const queryClient = useQueryClient();
  const [url, setUrl] = useState("");
  const [mode, setMode] = useState<"ranges" | "highlights">("ranges");
  const [ranges, setRanges] = useState<[string, string][]>([["00:00", "00:30"]]);
  const [highlights, setHighlights] = useState(3);
  const [language, setLanguage] = useState("auto");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [preview, setPreview] = useState<string>("source.mp4");
  const [seek, setSeek] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [apiKey, setApiKey] = useState("");
  const [modelDraft, setModelDraft] = useState<string | null>(null);
  const [subtitleMode, setSubtitleMode] = useState("bilingual");
  const video = useRef<HTMLVideoElement>(null);
  const config = useQuery({ queryKey: ["companion", "config"], queryFn: () => api<{ ready: boolean; missing: string[]; translation_configured: boolean; translation_model: string; translation_models?: string[]; translation_config_error?: string | null }>("/config"), refetchInterval: 15000 });
  const history = useQuery({ queryKey: ["companion", "jobs"], queryFn: () => api<Job[]>("/jobs"), refetchInterval: 3000 });
  const detail = useQuery({ queryKey: ["companion", "job", selectedId], queryFn: () => api<Job>(`/jobs/${selectedId}`), enabled: selectedId !== null,
    refetchInterval: query => query.state.status === "error" ? 3000 : running(query.state.data) ? 1000 : false });
  const job = detail.data;
  const visibleJobs = history.data?.map(item => item.id === job?.id ? job : item);
  const busy = visibleJobs?.some(running) || running(job);
  const create = useMutation({ mutationFn: (payload: JobInput) => api<{ id: string }>("/jobs", payload),
    onSuccess: result => { setSelectedId(result.id); setPreview("source.mp4"); void queryClient.invalidateQueries({ queryKey: ["companion", "jobs"] }); },
    onError: err => setError(err.message) });
  const resume = useMutation({ mutationFn: async (id: string) => {
    const response = await fetch(`/companion-api/jobs/${id}/resume`, { method: "POST" });
    if (!response.ok) throw new Error("恢复失败，请检查是否已有任务运行");
  }, onSuccess: () => { void queryClient.invalidateQueries({ queryKey: ["companion"] }); }, onError: err => setError(err.message) });
  const saveKey = useMutation({ mutationFn: () => api("/translation-config", { api_key: apiKey.trim() }),
    onSuccess: () => { setApiKey(""); void queryClient.invalidateQueries({ queryKey: ["companion", "config"] }); },
    onError: err => setError(err.message) });
  const translate = useMutation({ mutationFn: (id: string) => api(`/jobs/${id}/translate`, {}),
    onSuccess: () => { void queryClient.invalidateQueries({ queryKey: ["companion"] }); }, onError: err => setError(err.message) });
  const saveModel = useMutation({ mutationFn: () => api("/translation-config", { model: modelDraft }),
    onSuccess: async () => { await queryClient.invalidateQueries({ queryKey: ["companion", "config"] }); setModelDraft(null); },
    onError: err => setError(err.message) });

  useEffect(() => { if (!selectedId && history.data?.length) setSelectedId(history.data[0].id); }, [selectedId, history.data]);
  useEffect(() => { setPreview("source.mp4"); setSeek(null); }, [selectedId]);
  useEffect(() => {
    if (seek !== null && video.current && video.current.readyState >= 1) { video.current.currentTime = seek; setSeek(null); }
  }, [seek, preview]);

  function submit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    try {
      if (mode === "ranges") ranges.forEach(([start, end], index) => { if (parseTime(start) >= parseTime(end)) throw new Error(`片段 ${index + 1}：结束时间必须大于开始时间`); });
      create.mutate({ url: url.trim(), ranges: mode === "ranges" ? ranges : [], highlights: mode === "highlights" ? highlights : null, language });
    } catch (err) { setError(err instanceof Error ? err.message : "请检查输入"); }
  }

  const clip = job?.clips.find(item => item.video === preview);
  const stage = job?.state === "completed" ? 4 : ({ preparing: 0, downloading: 1, download_failed: 1, downloaded: 2, transcribing: 2, subtitles_ready: 3, exporting: 3 }[job?.phase ?? ""] ?? 0);
  const unavailable = config.isError || history.isError || detail.isError;
  const hasBilingual = job?.translation?.state === "completed";
  const showBilingual = hasBilingual && subtitleMode === "bilingual";
  const subtitleFile = (clip?.subtitles ?? "subtitles.srt").replace(/\.srt$/, showBilingual ? ".ja-zh.vtt" : ".vtt");
  const visibleSegments = (showBilingual ? job?.bilingual_segments : job?.segments) ?? [];

  return <div className="ny-companion">
    <header className="companion-header">
      <a className="companion-brand" href="/" aria-label="Nyaru 本地视频工作台"><Scissors size={24} /><span>NYARU <small>本地视频工作台</small></span></a>
      <span className={`companion-runtime ${config.data?.ready ? "is-ready" : ""}`}><span />{config.data?.ready ? "本地引擎就绪" : config.isError ? "服务未连接" : "检查本地环境"}</span>
    </header>
    <main className="companion-layout">
      <aside className="companion-sidebar">
        <section className="companion-panel">
          <div className="companion-panel-title"><span className="companion-number">01</span><h1>创建视频任务</h1></div>
          <p className="companion-muted">粘贴链接，生成字幕与时间轴，再导出你需要的片段。</p>
          <form onSubmit={submit}>
            <fieldset disabled={busy || create.isPending}>
              <label className="ny-field">视频链接<input className="ny-input" type="url" required placeholder="https://…" value={url} onChange={event => setUrl(event.target.value)} /></label>
              <label className="ny-field">视频语种<select className="ny-input" value={language} onChange={event => setLanguage(event.target.value)}><option value="auto">自动识别</option><option value="zh">中文</option><option value="en">英语</option><option value="ja">日语</option></select></label>
              <fieldset className="companion-mode"><legend>切片方式</legend>
                <label className={mode === "ranges" ? "is-selected" : ""}><input type="radio" name="mode" checked={mode === "ranges"} onChange={() => setMode("ranges")} />指定时间段</label>
                <label className={mode === "highlights" ? "is-selected" : ""}><input type="radio" name="mode" checked={mode === "highlights"} onChange={() => setMode("highlights")} />高光自动切片</label>
              </fieldset>
              {mode === "ranges" ? <div className="companion-ranges">
                <p className="companion-muted">支持秒数或时:分:秒，时间不能超过视频时长。</p>
                {ranges.map((range, index) => <div className="companion-range" key={index}>
                  <span className="companion-muted">{String(index + 1).padStart(2, "0")}</span>
                  <label>开始<input className="ny-input" aria-label={`开始时间 ${index + 1}`} required value={range[0]} onChange={event => setRanges(ranges.map((item, i) => i === index ? [event.target.value, item[1]] : item))} /></label>
                  <label>结束<input className="ny-input" aria-label={`结束时间 ${index + 1}`} required value={range[1]} onChange={event => setRanges(ranges.map((item, i) => i === index ? [item[0], event.target.value] : item))} /></label>
                  <button className="ny-button ny-button--quiet" type="button" aria-label={`移除时间段 ${index + 1}`} disabled={ranges.length === 1} onClick={() => setRanges(ranges.filter((_, i) => i !== index))}><X size={16} /></button>
                </div>)}
                <button className="ny-button" type="button" disabled={ranges.length >= 100} onClick={() => setRanges([...ranges, ["00:00", "00:30"]])}><Plus size={16} />添加时间段</button>
              </div> : <div className="companion-highlights">
                <label className="ny-field">最多导出片段数<input className="ny-input" type="number" min={1} max={100} required value={highlights} onChange={event => setHighlights(Number(event.target.value))} /></label>
                <p className="companion-muted">根据字幕密度、笑声与兴奋词筛选。达不到评分阈值时，会保留完整字幕并报告零切片。</p>
              </div>}
            </fieldset>
            {error && <div className="companion-error" role="alert">{error}</div>}
            {config.data && !config.data.ready && <p className="companion-error" role="alert">缺少：{config.data.missing.join("、")}。请按使用指南准备环境。</p>}
            <button className="ny-button ny-button--primary companion-start" type="submit" disabled={!config.data?.ready || !!busy || create.isPending || unavailable}><Scissors size={16} />{create.isPending ? "正在提交…" : busy ? "已有任务处理中" : "开始处理"}</button>
          </form>
          <p className="companion-footnote">识别和切片在本机完成 · 下载需要网络</p>
        </section>
        <section className="companion-panel" aria-label="中日双语字幕">
          <h2>日语 → 中文 · 双语字幕</h2>
          <p className="companion-muted">DeepSeek 翻译只发送字幕文字，会使用你的 API 额度。视频和识别在本机完成。</p>
          <form onSubmit={event => { event.preventDefault(); setError(null); saveKey.mutate(); }}>
            <label className="ny-field">DeepSeek API Key<input className="ny-input" type="password" autoComplete="off" value={apiKey} onChange={event => setApiKey(event.target.value)} placeholder="保存后重启自动加载" /></label>
            <button className="ny-button" type="submit" disabled={!apiKey.trim() || saveKey.isPending || saveModel.isPending}>保存 Key 到配置文件</button>
          </form>
          <p className="companion-footnote">{config.data?.translation_configured ? "Key 已保存 · 重启自动加载" : "Key 尚未设置 · 保存到 runs/config.json"} · {config.data?.translation_model ?? "deepseek-flash"}</p>
          <form onSubmit={event => { event.preventDefault(); setError(null); saveModel.mutate(); }}>
            <label className="ny-field">翻译模型<select className="ny-input" value={modelDraft ?? config.data?.translation_model ?? "deepseek-flash"} onChange={event => setModelDraft(event.target.value)}>
              {(config.data?.translation_models ?? ["deepseek-flash", "deepseek-v4-pro"]).map(model => <option key={model} value={model}>{model === "deepseek-flash" ? "DeepSeek Flash（默认）" : "DeepSeek V4 Pro"}</option>)}
            </select></label>
            <button className="ny-button" type="submit" disabled={!modelDraft || modelDraft === config.data?.translation_model || saveModel.isPending || saveKey.isPending}>保存模型</button>
          </form>
          <p className="companion-footnote">模型选择重启后保留；已开始的翻译继续使用原模型。</p>
          {job?.translation?.model && job.translation.state !== "not_started" && <p className="companion-footnote">当前任务模型：{job.translation.model}</p>}
          {config.data?.translation_config_error && <p role="alert">{config.data.translation_config_error}</p>}
          {job?.state === "completed" && <>
            <button className="ny-button ny-button--primary" disabled={!config.data?.translation_configured || !!busy || translate.isPending || !!hasBilingual || unavailable} onClick={() => { setError(null); translate.mutate(job.id); }}>{hasBilingual ? "中日双语字幕已生成" : ["failed", "interrupted"].includes(job.translation?.state) ? "继续生成中日双语字幕" : "生成中日双语字幕"}</button>
            <p className="companion-footnote">复用当前任务的字幕与时间轴，保留原视频和原字幕。</p>
            {job.translation && job.translation.state !== "not_started" && <p role="status">{job.translation.message ?? `翻译 ${job.translation.done}/${job.translation.total} 条`}{hasBilingual ? " · 已完成" : job.translation.state === "interrupted" ? " · 已中断，可继续" : ""}</p>}
            {job.translation?.error && <p className="companion-error" role="alert">{job.translation.error}</p>}
          </>}
        </section>
        <section className="companion-panel companion-history" aria-label="任务记录">
          <h2>任务记录 <span>{history.data?.length ?? 0}</span></h2>
          {!history.data?.length && <p className="companion-muted">开始第一个任务后，结果会保存在这里。</p>}
          {visibleJobs?.map(item => <button className="companion-history-item" key={item.id} aria-pressed={item.id === selectedId} onClick={() => { setSelectedId(item.id); setError(null); }}><span><strong>{item.mode === "highlights" ? "高光切片" : "指定片段"}</strong><small>{new Date(item.started_at * 1000).toLocaleString("zh-CN", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" })} · {item.id.slice(0, 6)}</small></span><span>{statusLabel(item)}</span></button>)}
        </section>
      </aside>
      <div className="companion-workspace">
        <section className="companion-panel companion-progress" aria-label="处理进度">
          <div className="companion-section-heading"><div className="companion-panel-title"><span className="companion-number">02</span><h2>处理进度</h2></div>{job && <span className={`ny-stamp ny-stamp--${job.state === "completed" ? "success" : ["failed", "interrupted"].includes(job.state) ? "failed" : "running"}`}>{statusLabel(job)}</span>}</div>
          {unavailable && <div className="companion-error" role="alert">本地服务连接中断，正在重试。请确认启动窗口仍在运行。</div>}
          <ol className="ny-progress companion-stages" aria-label="处理阶段">{["检查环境", "下载视频", "字幕与时间轴", "导出片段"].map((label, index) => <li className={`ny-progress__stage ${job && index < stage ? "ny-progress__stage--complete" : job && index === stage ? ["failed", "interrupted"].includes(job.state) ? "ny-progress__stage--failed" : "ny-progress__stage--running" : ""}`} key={label}>{job && index < stage ? <Check size={14} /> : <span>{index + 1}</span>}{label}</li>)}</ol>
          <p className="companion-status" role="status">{job?.message ?? "等待创建任务"}</p>
          {job?.error && <p className="companion-error" role="alert">{job.error}</p>}
          {job?.state === "failed" && !job.can_resume && <p className="companion-muted">下载未完成，请检查链接后重新创建任务。</p>}
          {job?.can_resume && <button className="ny-button" disabled={!!busy || resume.isPending} onClick={() => { setError(null); resume.mutate(job.id); }}>恢复处理</button>}
        </section>
        <section className="companion-panel companion-preview" aria-label="视频预览">
          <div className="companion-section-heading"><div className="companion-panel-title"><span className="companion-number">03</span><h2>预览与时间轴</h2></div><span className="companion-muted">{job?.duration ? `原视频 ${time(job.duration)}` : ""}</span></div>
          {job?.has_source ? <>
            <div className="companion-preview-tabs"><button className="ny-button" aria-pressed={!clip} onClick={() => setPreview("source.mp4")}>完整视频</button>{job.clips.map((item, index) => <button className="ny-button" key={item.video} aria-label={`预览切片 ${index + 1}`} aria-pressed={preview === item.video} onClick={() => setPreview(item.video)}>切片 {index + 1}</button>)}</div>
            {hasBilingual && <label className="ny-field">预览字幕<select className="ny-input" value={subtitleMode} onChange={event => setSubtitleMode(event.target.value)}><option value="bilingual">中日双语</option><option value="original">原文字幕</option></select></label>}
            <video key={`${job.id}/${preview}`} ref={video} src={fileUrl(job.id, preview)} controls preload="metadata" aria-label={clip ? "切片预览" : "完整视频预览"} onLoadedMetadata={() => { if (seek !== null && video.current) { video.current.currentTime = seek; setSeek(null); } }}>
              {(clip || job.segments.length > 0) && <track key={subtitleFile} kind="subtitles" src={fileUrl(job.id, subtitleFile)} srcLang={showBilingual ? "zh" : job.language === "auto" ? "und" : job.language} label={showBilingual ? "中日双语" : "识别字幕"} default />}
            </video>
            <div className="companion-ruler"><span>00:00</span><span>{time((job.duration ?? 0) / 2)}</span><span>{time(job.duration ?? 0)}</span></div>
            <div className="companion-timeline" aria-label="切片时间轴">{job.clips.map((item, index) => <button key={item.video} aria-label={`在时间轴预览切片 ${index + 1}`} aria-pressed={preview === item.video} onClick={() => setPreview(item.video)}><span className="companion-timeline-fill" style={{ left: `${item.start / (job.duration ?? 1) * 100}%`, width: `${(item.end - item.start) / (job.duration ?? 1) * 100}%` }} /><span>切片 {index + 1} · {time(item.start)} — {time(item.end)}</span></button>)}</div>
          </> : <div className="companion-empty-preview"><Film size={42} strokeWidth={1} /><strong>你的下一段精彩，从这里开始</strong><p>下载完成后可以预览视频<br />字幕和切片会随处理进度出现</p></div>}
          {job && visibleSegments.length > 0 && <details className="companion-transcript" open><summary>{showBilingual ? "完整双语字幕" : "完整字幕"} <span>{visibleSegments.length} 条 · 点击时间跳转原视频</span></summary><div>{visibleSegments.map((segment, index) => <button key={`${segment.id}/${index}`} onClick={() => { setPreview("source.mp4"); setSeek(segment.start_seconds); }}><time>{time(segment.start_seconds)}</time><span style={{ whiteSpace: "pre-line" }}>{segment.text}</span></button>)}</div></details>}
        </section>
        <section className="companion-panel companion-results" aria-label="导出结果">
          <div className="companion-section-heading"><div className="companion-panel-title"><span className="companion-number">04</span><h2>导出结果</h2></div><span className="companion-muted">{job?.clips.length ?? 0} 个切片</span></div>
          {job?.segments.length ? <div className="companion-downloads"><a className="ny-button" href={fileUrl(job.id, "subtitles.srt", true)}><ArrowDownToLine size={16} />完整字幕 SRT</a><a className="ny-button" href={fileUrl(job.id, "transcript.txt", true)}><ArrowDownToLine size={16} />字幕文字 TXT</a></div> : <p className="companion-muted">生成的字幕和视频将出现在这里，可直接下载。</p>}
          {job && hasBilingual && <a className="ny-button" href={fileUrl(job.id, "subtitles.ja-zh.srt", true)}>完整双语字幕 SRT</a>}
          {job?.state === "completed" && !job.clips.length && <p className="companion-muted">没有达到阈值的高光，已保留完整字幕。</p>}
          {job?.clips.map((item, index) => <div className="companion-result" key={item.video}><div><strong>切片 {String(index + 1).padStart(2, "0")}</strong><p>{time(item.start)} — {time(item.end)} <span>· {(item.end - item.start).toFixed(1)} 秒{item.score !== null ? ` · 高光评分 ${item.score.toFixed(2)}` : ""}</span></p></div><div><a className="ny-button" aria-label={`下载切片 ${index + 1} 视频`} href={fileUrl(job.id, item.video, true)}><ArrowDownToLine size={16} />MP4</a><a className="ny-button" aria-label={`下载切片 ${index + 1} 字幕`} href={fileUrl(job.id, item.subtitles, true)}>SRT</a>{hasBilingual && <a className="ny-button" aria-label={`下载切片 ${index + 1} 双语字幕`} href={fileUrl(job.id, item.subtitles.replace(/\.srt$/, ".ja-zh.srt"), true)}>双语 SRT</a>}</div></div>)}
          {!!job?.clips.length && <p className="companion-footnote">切片字幕从零开始计时，下载视频与同名 SRT 即可继续编辑。</p>}
        </section>
      </div>
    </main>
  </div>;
}
