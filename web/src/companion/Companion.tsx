import { useEffect, useRef, useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowDownToLine, BookA, Captions, Check, Film, ListTree, Plus, Radio, Scissors, Shapes, SlidersHorizontal, Upload, X } from "lucide-react";

import { LlmSettings } from "./LlmSettings";
import { subtitleApi, type SubtitleSettings } from "./subtitleStyle";
import { SubtitlePreview } from "./SubtitlePreview";
import { StylePanel, useLegacyStyle } from "./StylePanel";
import { GlossaryPanel } from "./GlossaryPanel";
import { ShapesPanel, useShapes } from "./ShapesPanel";
import { TopicSegmentsPanel } from "./TopicSegmentsPanel";
import { PublishPanel } from "./PublishPanel";
import { LiveAutomationPanel } from "./LiveAutomationPanel";

import { api, time, parseTime, running, cancellable, statusLabel, fileUrl, clipSegments, bytes, type BurnVariant, type DanmakuBurnConfig, type DanmakuSummary, type Job, type JobInput, type CompanionConfig, type SubtitleMode, type StorageSnapshot, type BatchResult, type Segment } from "./companionApi";

const TOOLS = [
  { id: "subtitle", label: "字幕样式", icon: Captions },
  { id: "ai", label: "AI 设置", icon: SlidersHorizontal },
  { id: "glossary", label: "术语表", icon: BookA },
  { id: "shapes", label: "图形绘制", icon: Shapes },
  { id: "export", label: "导出", icon: ArrowDownToLine },
  { id: "topics", label: "内容切片", icon: ListTree },
  { id: "publish", label: "投稿", icon: Upload },
  { id: "automation", label: "自动化&录播", icon: Radio },
] as const;
type Tool = typeof TOOLS[number]["id"];
const SOURCES = [
  {id:"live",label:"实时录播"},
  {id:"replay",label:"下载视频"},
  {id:"file",label:"本地视频"},
] as const;
type Source = typeof SOURCES[number]["id"];

export function Companion() {
  const [tool, setTool] = useState<Tool | null>("subtitle");
  const toolbar = useRef<HTMLElement>(null);
  const drawer = useRef<HTMLElement>(null);
  useEffect(() => { if (drawer.current) drawer.current.scrollTop = 0; }, [tool]);
  const queryClient = useQueryClient();
  const [url, setUrl] = useState("");
  const [mode, setMode] = useState<"ranges" | "highlights" | "saozi" | "full">("ranges");
  const [source, setSource] = useState<Source>("replay");
  const [room, setRoom] = useState("");
  const [liveTemplate,setLiveTemplate] = useState<string | null>(null);
  const processingMode = source === "live" ? "saozi" : mode;
  const [localFile, setLocalFile] = useState<File | null>(null);
  const [ranges, setRanges] = useState<[string, string][]>([["00:00", "00:30"]]);
  const [highlights, setHighlights] = useState(3);
  const [language, setLanguage] = useState("auto");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [preview, setPreview] = useState<string>("source.mp4");
  const [seek, setSeek] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [subtitleMode, setSubtitleMode] = useState<SubtitleMode>("bilingual");
  const [burnVariant, setBurnVariant] = useState<Record<string, BurnVariant>>({});
  const [danmakuBurn, setDanmakuBurn] = useState<DanmakuBurnConfig>({ enabled: true, font_size: 40, area_height: 60 });
  const [rangeStart, setRangeStart] = useState("");
  const [rangeEnd, setRangeEnd] = useState("");
  const [rangePick, setRangePick] = useState<{ start: number | null; end: number | null }>({ start: null, end: null });
  const [rangeTarget, setRangeTarget] = useState<{ start: number; end: number } | null>(null);
  const [rangeError, setRangeError] = useState<string | null>(null);
  const [editCue, setEditCue] = useState<{ id: string; value: string } | null>(null);
  const [checked, setChecked] = useState<Set<string>>(new Set());
  const [confirmBatch, setConfirmBatch] = useState<"cleanup" | "delete" | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [translateClipIndex, setTranslateClipIndex] = useState<string>("all");
  const video = useRef<HTMLVideoElement>(null);
  const config = useQuery({ queryKey: ["companion", "config"], queryFn: () => api<CompanionConfig>("/config"), refetchInterval: 15000 });
  const history = useQuery({ queryKey: ["companion", "jobs"], queryFn: () => api<Job[]>("/jobs"), refetchInterval: 3000 });
  const detail = useQuery({ queryKey: ["companion", "job", selectedId], queryFn: () => api<Job>(`/jobs/${selectedId}`), enabled: selectedId !== null,
    refetchInterval: query => query.state.status === "error" ? 3000 : running(query.state.data) ? 1000 : false });
  const settings = useQuery({queryKey:["companion","subtitle-settings"],queryFn:()=>subtitleApi<SubtitleSettings>("/subtitle-settings")});
  const storage = useQuery({ queryKey: ["companion", "storage"], queryFn: () => api<StorageSnapshot>("/storage"), refetchInterval: 10000 });
  const liveTemplateId = liveTemplate ?? (settings.data?.templates?.some(item=>item.id==='nyaru') ? 'nyaru' : '');
  const legacyStyle = useLegacyStyle();
  const job = detail.data;
  const danmakuInfo = useQuery({ queryKey: ["companion", "danmaku", job?.id],
    queryFn: () => api<DanmakuSummary>(`/jobs/${job!.id}/danmaku`), enabled: !!job });
  const visibleJobs = history.data?.map(item => item.id === job?.id ? job : item);
  const busy = visibleJobs?.some(running) || running(job);
  const create = useMutation({ mutationFn: async (payload: JobInput & {file?:File}) => {
    if (!payload.file) return api<{id:string}>("/jobs", payload);
    const params = new URLSearchParams({language:payload.language,saozi:String(!!payload.saozi),ranges:JSON.stringify(payload.ranges)});
    if (payload.highlights !== null) params.set("highlights", String(payload.highlights));
    const response = await fetch(`/companion-api/jobs/upload?${params}`, {method:"POST",body:payload.file});
    const result: {id:string;detail?:string} = await response.json();
    if (!response.ok) throw new Error(result.detail ?? "录像导入失败，请检查磁盘空间");
    return result;
  },
    onSuccess: result => { setSelectedId(result.id); setPreview("source.mp4"); void queryClient.invalidateQueries({ queryKey: ["companion", "jobs"] }); },
    onError: err => setError(err.message) });
  const resume = useMutation({ mutationFn: async (id: string) => {
    const response = await fetch(`/companion-api/jobs/${id}/resume`, { method: "POST" });
    if (!response.ok) throw new Error("恢复失败，请检查是否已有任务运行");
  }, onSuccess: () => { void queryClient.invalidateQueries({ queryKey: ["companion"] }); }, onError: err => setError(err.message) });
  const translate = useMutation({ mutationFn: (payload: { id: string; clip_index?: number }) => api(`/jobs/${payload.id}/translate`, payload.clip_index === undefined ? {} : { clip_index: payload.clip_index }),
    onSuccess: () => { void queryClient.invalidateQueries({ queryKey: ["companion"] }); }, onError: err => setError(err.message) });
  const reasr = useMutation({ mutationFn: (id: string) => api(`/jobs/${id}/asr`, {}),
    onSuccess: () => { void queryClient.invalidateQueries({ queryKey: ["companion"] }); }, onError: err => setError(err.message) });
  const stop = useMutation({mutationFn:(id:string)=>api(`/jobs/${id}/stop`,{}),
    onSuccess:()=>{void queryClient.invalidateQueries({queryKey:["companion"]});},onError:err=>setError(err.message)});
  const cancel = useMutation({ mutationFn: (id: string) => api(`/jobs/${id}/cancel`, {}),
    onSuccess: () => { void queryClient.invalidateQueries({ queryKey: ["companion"] }); }, onError: err => setError(err.message) });
  const burn = useMutation({ mutationFn: (payload: { id: string; clip: string; variant: BurnVariant; start?: number; end?: number }) => api(`/jobs/${payload.id}/burn`, {
      clip: payload.clip, variant: payload.variant, danmaku: danmakuBurn, ...(payload.start === undefined ? {} : { start: payload.start, end: payload.end }) }),
    onSuccess: () => { void queryClient.invalidateQueries({ queryKey: ["companion", "job", selectedId] }); },
    onError: err => setError(err.message) });
  const editTranslation = useMutation({ mutationFn: (payload: { id: string; text: string }) => api(`/jobs/${selectedId}/translation/${payload.id}`, { text: payload.text }, "PUT"),
    onSuccess: () => { setEditCue(null); void queryClient.invalidateQueries({ queryKey: ["companion", "job", selectedId] }); },
    onError: err => setError(err.message) });
  const shapesQuery = useShapes();
  const glossarySettings = useMutation({ mutationFn: (collect: boolean) => api("/glossary-settings", { collect_candidates: collect }),
    onSuccess: () => { void queryClient.invalidateQueries({ queryKey: ["companion", "config"] }); },
    onError: err => setError(err.message) });
  const cleanupJobs = useMutation({ mutationFn: (ids: string[]) => api<BatchResult>("/jobs/cleanup", { ids }),
    onSuccess: result => finishBatch(result, false), onError: err => setError(err.message) });
  const deleteJobs = useMutation({ mutationFn: (ids: string[]) => api<BatchResult>("/jobs/delete", { ids }),
    onSuccess: result => finishBatch(result, true), onError: err => setError(err.message) });

  useEffect(() => { if (!selectedId && history.data?.length) setSelectedId(history.data[0].id); }, [selectedId, history.data]);
  useEffect(() => { setPreview("source.mp4"); setSeek(null); setEditCue(null); setRangeStart(""); setRangeEnd(""); setRangePick({ start: null, end: null }); setRangeTarget(null); setRangeError(null); }, [selectedId]);
  useEffect(() => { if (job?.live && !job.has_source && preview === "source.mp4" && job.clips.length) setPreview(job.clips[0].video); }, [job,preview]);
  useEffect(() => {
    if (seek !== null && video.current && video.current.readyState >= 1) { video.current.currentTime = seek; setSeek(null); }
  }, [seek, preview]);

  const llmConfigured = config.data?.llm_configured ?? (!!config.data?.translation_configured && (!config.data.translation_model || config.data.translation_model === "deepseek-flash"));
  const taskModel = job?.translation?.model ?? job?.saozi_model;
  const translationConfigured = taskModel ? taskModel.startsWith("chatgpt:")
    ? taskModel.length > "chatgpt:".length && !!config.data?.chatgpt?.connected && !!config.data.chatgpt.sharing
    : taskModel === "deepseek-flash" && !!config.data?.translation_configured && !config.data.translation_config_error
    : llmConfigured;
  const chatgptSelected = config.data?.llm_provider === "chatgpt";

  function submit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    try {
      if (processingMode === "ranges") ranges.forEach(([start, end], index) => { if (parseTime(start) >= parseTime(end)) throw new Error(`片段 ${index + 1}：结束时间必须大于开始时间`); });
      if (processingMode === "saozi" && !llmConfigured) throw new Error(chatgptSelected ? "臊子需要先连接 ChatGPT、授权订阅额度并保存可用模型" : "臊子需要先保存 DeepSeek API Key 并选择 Flash");
      if (source === "file" && !localFile) throw new Error("请选择本地视频文件");
      create.mutate({url:source === "live" ? room.trim() : url.trim(),ranges:processingMode === "ranges" ? ranges : [],
        highlights:processingMode === "highlights" ? highlights : null,language,
        ...(processingMode === "saozi" ? {saozi:true,live:source === "live"} : {}),
        ...(source === 'live' && liveTemplateId ? {subtitle_template_id:liveTemplateId} : {}),
        ...(source === "file" && localFile ? {file:localFile} : {})});
    } catch (err) { setError(err instanceof Error ? err.message : "请检查输入"); }
  }

  const clip = job?.clips.find(item => item.video === preview);
  const stage = job?.state === "completed" ? 4 : ({ preparing: 0, downloading: 1, download_failed: 1, downloaded: 2, transcribing: 2, subtitles_ready: 3, exporting: 3 }[job?.phase ?? ""] ?? 0);
  const unavailable = config.isError || history.isError || detail.isError;
  const hasBilingual = job?.translation?.state === "completed";
  const sourceChoice = burnVariant["source.mp4"] ?? "bilingual";
  const sourceVariant: BurnVariant = !hasBilingual && sourceChoice !== "original" ? "original" : sourceChoice;
  const sourceBurn = job?.source_burns?.[sourceVariant];
  const sourceBurning = sourceBurn?.state === "burning";
  const sourceBurnPercent = Math.round((sourceBurn?.progress ?? 0) * 100);
  const sourceResumable = !sourceBurning && sourceBurn?.state !== "completed" && (sourceBurn?.segments_done ?? 0) > 0;
  const rangeCues: Segment[] = (hasBilingual && job?.bilingual_segments?.length ? job.bilingual_segments : job?.segments) ?? [];
  const cueLabel = (cue: Segment) => `${time(cue.start_seconds)} → ${time(cue.end_seconds)} · ${cue.text.replace(/\n+/g, " ｜ ")}`;
  const rangeChoice = burnVariant.range ?? "bilingual";
  const rangeVariant: BurnVariant = !hasBilingual && rangeChoice !== "original" ? "original" : rangeChoice;
  const rangeKey = rangeTarget ? `range-${Math.round(rangeTarget.start * 1000)}-${Math.round(rangeTarget.end * 1000)}` : null;
  const rangeEntry = rangeKey ? job?.range_burns?.[rangeKey]?.[rangeVariant] : undefined;
  const rangeBurning = rangeEntry?.state === "burning";
  const rangePercent = Math.round((rangeEntry?.progress ?? 0) * 100);
  const rangeResumable = !rangeBurning && rangeEntry?.state !== "completed" && (rangeEntry?.segments_done ?? 0) > 0;
  const submitRange = () => {
    if (!job) return;
    setRangeError(null);
    let start: number;
    let end: number;
    try {
      start = parseTime(rangeStart);
      end = parseTime(rangeEnd);
    } catch (err) { setRangeError(err instanceof Error ? err.message : "时间格式无效"); return; }
    if (!(start < end)) { setRangeError("终点必须晚于起点"); return; }
    if (job.duration && end > job.duration + 0.05) { setRangeError(`终点不能超过视频时长 ${time(job.duration)}`); return; }
    setRangeTarget({ start, end });
    burn.mutate({ id: job.id, clip: "source.mp4", variant: rangeVariant, start, end });
  };
  const previewMode: SubtitleMode = hasBilingual ? subtitleMode : "original";
  const subtitleBase = (clip?.subtitles ?? "subtitles.srt").replace(/\.srt$/, "");
  const subtitleFile = previewMode === "bilingual" ? `${subtitleBase}.ja-zh.vtt` : previewMode === "zh" ? `${subtitleBase}.zh.vtt` : `${subtitleBase}.vtt`;
  const visibleSegments = (previewMode === "bilingual" ? job?.bilingual_segments : previewMode === "zh" ? job?.zh_segments : job?.segments) ?? [];
  const transcriptTitle = previewMode === "bilingual" ? "完整双语字幕" : previewMode === "zh" ? "完整译文字幕" : "完整字幕";
  const canEditTranslations = (previewMode === "zh" || previewMode === "bilingual") && job?.translation?.state === "completed";
  const zhPart = (text: string) => previewMode === "bilingual" ? text.split("\n").pop() ?? "" : text;
  const seekSource = (at: number) => {
    if (job?.has_source) { setPreview('source.mp4'); setSeek(at); }
    else { const target = job?.clips.find(item => item.start <= at && at < item.end); if (target) {setPreview(target.video);setSeek(at-target.start);} }
  };

  const selectable = (visibleJobs ?? []).filter(item => !running(item)).map(item => item.id);
  const allChecked = selectable.length > 0 && selectable.every(id => checked.has(id));
  const someChecked = selectable.some(id => checked.has(id));
  const batchPending = cleanupJobs.isPending || deleteJobs.isPending;

  function toggleCheck(id: string) {
    setChecked(current => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function toggleAll() {
    setChecked(current => {
      const next = new Set(current);
      if (allChecked) selectable.forEach(id => next.delete(id));
      else selectable.forEach(id => next.add(id));
      return next;
    });
  }

  function runBatch(mode: "cleanup" | "delete") {
    const ids = [...checked].filter(id => selectable.includes(id));
    setConfirmBatch(null);
    setError(null);
    setNotice(null);
    if (!ids.length) return;
    (mode === "cleanup" ? cleanupJobs : deleteJobs).mutate(ids);
  }

  function finishBatch(result: BatchResult, removed: boolean) {
    const failed = result.results.filter(item => !item.ok);
    const done = new Set(result.results.filter(item => item.ok).map(item => item.id));
    setChecked(current => new Set([...current].filter(id => !done.has(id))));
    if (removed && selectedId && done.has(selectedId)) setSelectedId(null);
    if (failed.length) setError(`${failed.length} 个任务未处理：${failed[0].error ?? "未知错误"}`);
    if (done.size) setNotice(`已${removed ? "彻底删除" : "清理"} ${done.size} 个任务，释放 ${bytes(result.freed)}`);
    void queryClient.invalidateQueries({ queryKey: ["companion"] });
  }

  function closeDrawer() {
    const trigger = toolbar.current?.querySelector<HTMLButtonElement>('[aria-expanded="true"]');
    setTool(null);
    trigger?.focus();
  }

  return <div className="ny-companion" onKeyDown={event => {
    if (event.key === "Escape" && tool && !document.fullscreenElement) {
      event.preventDefault();
      closeDrawer();
    }
  }}>
    <div className="companion-commandbar">
    <header className="companion-header">
      <a className="companion-brand" href="/" aria-label="Nyaru 本地视频工作台"><Scissors size={24} /><span>NYARU <small>本地视频工作台</small></span></a>
      <span className={`companion-runtime ${config.data?.ready ? "is-ready" : ""}`}><span />{config.data?.ready ? "本地引擎就绪" : config.isError ? "服务未连接" : "检查本地环境"}</span>
    </header>
    <nav ref={toolbar} className="companion-toolbar" aria-label="工作台工具">
      {TOOLS.map(({id, label, icon: Icon}) => <button key={id} type="button" className="ny-button companion-tool" aria-expanded={tool === id} aria-controls="companion-drawer" onClick={() => {
        setTool(current => current === id ? null : id);
      }}><Icon size={16} />{label}</button>)}
    </nav>
    </div>
    <main className={`companion-layout ${tool === "automation" ? "is-automation" : tool ? "has-drawer" : ""}`}>
      {tool === "automation" ? (
        <LiveAutomationPanel onOpenJob={id => { setSelectedId(id); setTool(null); }} />
      ) : (
        <>
      <aside className="companion-sidebar" aria-label="任务面板">
        <form id="companion-task" onSubmit={submit} onInvalid={event => {
          event.preventDefault();
          const invalid = Array.from(event.currentTarget.querySelectorAll("input")).find(input => input.willValidate && !input.validity.valid);
          if (!invalid || invalid !== event.target) return;
          setError(invalid.validationMessage);
          requestAnimationFrame(() => invalid.focus());
        }}>
        <section className="companion-panel">
          <div className="companion-panel-title"><h2>新建任务</h2></div>
          <p className="companion-muted">选择视频来源，生成字幕与时间轴，再导出你需要的片段。</p>
          <fieldset disabled={busy || create.isPending}>
            <div className="companion-task-fields">
              <div className="companion-sources" role="group" aria-label="视频来源">
                {SOURCES.map(({id,label}) => <button key={id} type="button" className="ny-button" aria-pressed={source === id} onClick={() => {setSource(id);setError(null);}}>{label}</button>)}
              </div>
              <label className="ny-field" hidden={source !== "live"}>直播间号<input className="ny-input" type="text" inputMode="numeric" disabled={source !== "live"} required={source === "live"} pattern="[1-9][0-9]*" title="只需输入数字直播间号，例如 12345" placeholder="例如：12345" value={room} onChange={event => setRoom(event.target.value)} /></label>
              <label className="ny-field" hidden={source !== "replay"}>视频链接 / BV 号<input className="ny-input" type="text" disabled={source !== "replay"} required={source === "replay"} pattern="(?:BV[A-Za-z0-9]{10}|https?://\S+)" title="支持 B 站 BV 号，以及 Bilibili / YouTube / Twitch 视频链接" placeholder="BV1xx411c7mD 或 https://youtube.com/watch?v=… 或 https://twitch.tv/…" value={url} onChange={event => setUrl(event.target.value)} /></label>
              <label className="ny-field" hidden={source !== "file"}>本地视频文件<input className="ny-input" type="file" disabled={source !== "file"} accept="video/*,.mkv,.flv,.ts" onChange={event=>setLocalFile(event.target.files?.[0] ?? null)} /></label>
              {source === "live" && <p className="companion-muted">录制正在直播的房间，按约 1–2 分钟连续处理；需要先配置 AI。点击停止后处理剩余内容。</p>}
              {source === 'live' && <>
                <label className="ny-field">实时切片字幕模板<select className="ny-input" value={liveTemplateId} onChange={event=>setLiveTemplate(event.target.value)} disabled={!settings.data || settings.isError}>
                  <option value="">不自动套用样式</option>{settings.data?.templates?.map(item=><option key={item.id} value={item.id}>{item.name}</option>)}
                </select></label>
                <p className="companion-footnote">选择后每段自动生成 ASS 和字幕视频；双语完成后补齐双语版本。样式固定为开播时的模板，烧录可能增加处理积压。</p>
                <button className="ny-button" type="button" onClick={()=>setTool('subtitle')}>导入 ASS 或管理字幕模板</button>
              </>}
              <label className="ny-field">视频语种<select className="ny-input" value={language} onChange={event => setLanguage(event.target.value)}><option value="auto">自动识别</option><option value="zh">中文</option><option value="en">英语</option><option value="ja">日语</option></select></label>
            </div>
          </fieldset>
        </section>
        <section className="companion-panel">
          <div className="companion-panel-title"><h2>切片方式</h2></div>
          <fieldset disabled={busy || create.isPending}>
            <div className="companion-task-fields">
              <fieldset className="companion-mode" disabled={source === "live"} aria-label="切片方式">
                <label className={processingMode === "ranges" ? "is-selected" : ""}><input type="radio" name="mode" checked={processingMode === "ranges"} onChange={() => setMode("ranges")} />指定时间段</label>
                <label className={processingMode === "highlights" ? "is-selected" : ""}><input type="radio" name="mode" checked={processingMode === "highlights"} onChange={() => setMode("highlights")} />高光自动切片</label>
                <label className={processingMode === "saozi" ? "is-selected" : ""}><input type="radio" name="mode" checked={processingMode === "saozi"} onChange={() => setMode("saozi")} />臊子</label>
                <label className={processingMode === "full" ? "is-selected" : ""}><input type="radio" name="mode" checked={processingMode === "full"} onChange={() => setMode("full")} />完整视频</label>
              </fieldset>
              {source === "live" && <p className="companion-muted">实时录播使用臊子连续处理；下载视频和本地视频可选择其他切片方式。</p>}
              {processingMode === "ranges" ? <div className="companion-ranges">
                <p className="companion-muted">支持秒数或时:分:秒，时间不能超过视频时长。</p>
                {ranges.map((range, index) => <div className="companion-range" key={index}>
                  <span className="companion-muted">{String(index + 1).padStart(2, "0")}</span>
                  <label>开始<input className="ny-input" aria-label={`开始时间 ${index + 1}`} required value={range[0]} onChange={event => setRanges(ranges.map((item, i) => i === index ? [event.target.value, item[1]] : item))} /></label>
                  <label>结束<input className="ny-input" aria-label={`结束时间 ${index + 1}`} required value={range[1]} onChange={event => setRanges(ranges.map((item, i) => i === index ? [item[0], event.target.value] : item))} /></label>
                  <button className="ny-button ny-button--quiet" type="button" aria-label={`移除时间段 ${index + 1}`} disabled={ranges.length === 1} onClick={() => setRanges(ranges.filter((_, i) => i !== index))}><X size={16} /></button>
                </div>)}
                <button className="ny-button" type="button" disabled={ranges.length >= 100} onClick={() => setRanges([...ranges, ["00:00", "00:30"]])}><Plus size={16} />添加时间段</button>
              </div> : processingMode === "highlights" ? <div className="companion-highlights">
                <label className="ny-field">最多导出片段数<input className="ny-input" type="number" min={1} max={100} required value={highlights} onChange={event => setHighlights(Number(event.target.value))} /></label>
                <p className="companion-muted">根据字幕密度、笑声与兴奋词筛选。达不到评分阈值时，会保留完整字幕并报告零切片。</p>
              </div> : processingMode === "full" ? <p className="companion-muted">对视频全程生成原文与双语字幕，不切片，转录完成即结束。适合想先拿到完整字幕再人工挑选片段的场景。</p> : <p className="companion-muted">连续切为约 1–2 分钟，{chatgptSelected ? "ChatGPT" : "DeepSeek Flash"} 根据字幕段落选择切点，并自动生成中日双语字幕，会使用{chatgptSelected ? "订阅" : " API "}额度。短尾段完整保留。{source === "live" ? "实时结果会有缓冲与处理延迟；停止后导出剩余内容。" : "原视频保留，切片按顺序覆盖全部内容。"}</p>}
            </div>
          </fieldset>
          <button className="ny-button ny-button--primary companion-start" type="submit" disabled={!config.data?.ready || !!busy || create.isPending || unavailable || (source === 'live' && !settings.data)}><Scissors size={16} />{create.isPending ? "正在提交…" : busy ? "已有任务处理中" : "开始处理"}</button>
          <p className="companion-footnote">识别和切片在本机完成 · 下载需要网络</p>
        </section>
        </form>
        <section className="companion-panel companion-history" aria-label="任务记录">
          <h2>任务记录 <span>{history.data?.length ?? 0}</span></h2>
          {storage.data && <p className="companion-muted">共占用 {bytes(storage.data.total)}，其中可清理的合成／切片视频约 {bytes(storage.data.cleanable)}。</p>}
          {!history.data?.length && <p className="companion-muted">开始第一个任务后，结果会保存在这里。</p>}
          {!!history.data?.length && <div className="companion-history-tools">
            <label className="companion-history-selectall"><input type="checkbox" checked={allChecked} ref={element => { if (element) element.indeterminate = someChecked && !allChecked; }} onChange={toggleAll} />全选</label>
            <span className="companion-muted">已选 {checked.size} 项</span>
            <button className="ny-button" type="button" disabled={!checked.size || batchPending} onClick={() => { setNotice(null); setConfirmBatch("cleanup"); }}>清理产物</button>
            <button className="ny-button ny-button--danger" type="button" disabled={!checked.size || batchPending} onClick={() => { setNotice(null); setConfirmBatch("delete"); }}>彻底删除</button>
          </div>}
          {confirmBatch && <div className="companion-history-confirm" role="alertdialog" aria-label={confirmBatch === "cleanup" ? "确认清理产物" : "确认彻底删除"}>
            <p className="companion-muted">{confirmBatch === "cleanup"
              ? `确认清理所选 ${checked.size} 个任务？将删除可重新生成的合成／切片视频与中断残留，保留原视频、切片原片与字幕翻译，之后可重新合成。`
              : `确认彻底删除所选 ${checked.size} 个任务？将连同任务记录、原视频与全部结果一起删除，无法恢复。`}</p>
            <div className="companion-history-confirm-actions">
              <button className={`ny-button ${confirmBatch === "delete" ? "ny-button--danger" : "ny-button--primary"}`} type="button" disabled={batchPending} onClick={() => runBatch(confirmBatch)}>{batchPending ? "处理中…" : "确认"}</button>
              <button className="ny-button" type="button" disabled={batchPending} onClick={() => setConfirmBatch(null)}>取消</button>
            </div>
          </div>}
          {notice && <p className="companion-history-notice" role="status">{notice}</p>}
          {visibleJobs?.map(item => {
            const info = storage.data?.jobs[item.id];
            const busyItem = running(item);
            return <div className="companion-history-row" key={item.id}>
              <label className="companion-history-check" title={busyItem ? "任务处理中，暂不能清理或删除" : "选择该任务"}>
                <input type="checkbox" checked={checked.has(item.id)} disabled={busyItem} onChange={() => toggleCheck(item.id)} aria-label={`选择任务 ${item.id.slice(0, 6)}`} />
              </label>
              <button className="companion-history-item" aria-pressed={item.id === selectedId} onClick={() => { setSelectedId(item.id); setError(null); setNotice(null); }}><span><strong>{item.mode === "saozi" ? item.live ? "臊子 · 实时" : "臊子" : item.mode === "highlights" ? "高光切片" : item.mode === "full" ? "完整视频" : "指定片段"}</strong><small>{new Date(item.started_at * 1000).toLocaleString("zh-CN", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" })} · {item.id.slice(0, 6)}{info ? ` · 占用 ${bytes(info.total)}${info.cleanable ? `（可清理 ${bytes(info.cleanable)}）` : ""}` : ""}</small></span><span>{statusLabel(item)}</span></button>
            </div>;
          })}
        </section>
      </aside>
      <aside ref={drawer} id="companion-drawer" className="companion-drawer" aria-label="工具选项" hidden={!tool}>
        <div className="companion-drawer-heading"><h2>{TOOLS.find(item => item.id === tool)?.label}</h2><button type="button" className="ny-button ny-button--quiet" aria-label="收起工具面板" onClick={closeDrawer}><X size={16} /></button></div>
        <div className="companion-drawer-content">
        <section className="companion-panel" hidden={tool !== "subtitle"}>
          <StylePanel style={legacyStyle} />
        </section>
        <section className="companion-panel" aria-label="AI 设置" hidden={tool !== "ai"}>
          <LlmSettings config={config.data} busy={!!busy} />
          {taskModel && <p className="companion-footnote">当前任务模型：{taskModel}</p>}
        </section>
        {tool === "glossary" && <GlossaryPanel />}
        {tool === "shapes" && <ShapesPanel />}
        <section className="companion-panel companion-results" aria-label="导出结果" hidden={tool !== "export"}>
          {job?.segments.length ? <div className="companion-downloads">
            <a className="ny-button" href={fileUrl(job.id, "subtitles.srt", true)}><ArrowDownToLine size={16} />完整字幕 SRT</a>
            {hasBilingual && <a className="ny-button" href={fileUrl(job.id, "subtitles.zh.srt", true)}><ArrowDownToLine size={16} />完整译文字幕 SRT</a>}
            {hasBilingual && <a className="ny-button" href={fileUrl(job.id, "subtitles.ja-zh.srt", true)}><ArrowDownToLine size={16} />完整双语字幕 SRT</a>}
            <a className="ny-button" href={fileUrl(job.id, "transcript.txt", true)}><ArrowDownToLine size={16} />字幕文字 TXT</a>
          </div> : <p className="companion-muted">生成的字幕和视频将出现在这里，可直接下载。</p>}
          {job?.state === "completed" && !job.clips.length && <p className="companion-muted">没有达到阈值的高光，已保留完整字幕。</p>}
          {job?.state === "completed" && <div className="companion-result companion-danmaku">
            <div>
              <strong>切片弹幕</strong>
              <p>{danmakuInfo.data?.count
                ? `任务弹幕 ${danmakuInfo.data.count} 条，合成时叠加对应时间段的弹幕`
                : "任务暂无弹幕文件；导入弹幕后重新合成即可叠加"}</p>
            </div>
            <div className="companion-burn">
              <button type="button" className={`ny-button${danmakuBurn.enabled ? "" : " is-off"}`}
                onClick={() => setDanmakuBurn(current => ({ ...current, enabled: !current.enabled }))}>
                {danmakuBurn.enabled ? "弹幕已开启" : "弹幕已关闭"}
              </button>
              <label className="companion-danmaku-field">字号
                <input className="ny-input" type="number" min={12} max={96} value={danmakuBurn.font_size}
                  aria-label="弹幕字号" disabled={!danmakuBurn.enabled}
                  onChange={event => setDanmakuBurn(current => ({ ...current, font_size: Math.max(12, Math.min(96, Number(event.target.value) || 40)) }))} />
              </label>
              <label className="companion-danmaku-field">区域高度
                <input className="ny-input" type="number" min={10} max={100} value={danmakuBurn.area_height}
                  aria-label="弹幕区域高度百分比" disabled={!danmakuBurn.enabled}
                  onChange={event => setDanmakuBurn(current => ({ ...current, area_height: Math.max(10, Math.min(100, Number(event.target.value) || 60)) }))} />%
              </label>
            </div>
          </div>}
          {job?.state === "completed" && job.has_source && <div className="companion-result">
            <div><strong>完整视频</strong><p>{job.duration ? time(job.duration) : ""} <span>· 全部字幕 — {job.clips.length} 个切片</span></p></div>
            <div className="companion-result-actions">
              <a className="ny-button" aria-label="下载完整视频" href={fileUrl(job.id, "source.mp4", true)}><ArrowDownToLine size={16} />原视频 MP4</a>
              <div className="companion-burn">
                <select className="ny-input" aria-label="完整视频合成字幕内容" value={sourceVariant} onChange={event => setBurnVariant({ ...burnVariant, "source.mp4": event.target.value as BurnVariant })}>
                  <option value="bilingual" disabled={!hasBilingual}>双语字幕</option>
                  <option value="zh" disabled={!hasBilingual}>仅译文</option>
                  <option value="original">仅原文</option>
                </select>
                <button className="ny-button" type="button" disabled={sourceBurning || burn.isPending || !job.segments.length} onClick={() => { setError(null); burn.mutate({ id: job.id, clip: "source.mp4", variant: sourceVariant }); }}>
                  {sourceBurning ? "正在合成…" : sourceBurn?.state === "completed" ? "重新合成视频" : sourceResumable ? "继续合成视频" : "合成完整视频"}
                </button>
                {sourceBurning && <span className="companion-burn-progress" role="status" aria-label={`完整视频合成进度 ${sourceBurnPercent}%`}>
                  <span className="companion-burn-bar"><span style={{ width: `${sourceBurnPercent}%` }} /></span>
                  <span className="companion-burn-percent">{sourceBurnPercent}%{sourceBurn?.segments_total ? `（${sourceBurn.segments_done ?? 0}/${sourceBurn.segments_total} 段）` : ""}</span>
                </span>}
                {sourceBurn?.state === "completed" && sourceBurn.file && <a className="ny-button" href={fileUrl(job.id, sourceBurn.file, true)}><ArrowDownToLine size={16} />下载合成版</a>}
                {sourceBurn?.state === "failed" && <span className="companion-error" role="alert">{sourceBurn.error ?? "合成失败，请重试"}</span>}
                {!hasBilingual && <span className="companion-muted">生成双语字幕后可合成译文版本</span>}
              </div>
            </div>
          </div>}
          {job?.state === "completed" && job.has_source && rangeCues.length > 0 && <div className="companion-result">
            <div className="companion-range">
              <div className="companion-range-row">
                <input className="ny-input" aria-label="合成起始时间" placeholder="00:00 或秒数" value={rangeStart}
                  onChange={event => { setRangeStart(event.target.value); setRangePick({ ...rangePick, start: null }); }} />
                <select className="ny-input" aria-label="从字幕选择起始时间" value={rangePick.start ?? ""}
                  onChange={event => { const index = Number(event.target.value); const cue = rangeCues[index]; if (!cue) return;
                    setRangeStart(time(cue.start_seconds)); setRangePick({ ...rangePick, start: index }); }}>
                  <option value="">从字幕选择起点…</option>
                  {rangeCues.map((cue, index) => <option key={`rs${index}`} value={index}>{cueLabel(cue)}</option>)}
                </select>
              </div>
              <div className="companion-range-row">
                <input className="ny-input" aria-label="合成结束时间" placeholder="00:30 或秒数" value={rangeEnd}
                  onChange={event => { setRangeEnd(event.target.value); setRangePick({ ...rangePick, end: null }); }} />
                <select className="ny-input" aria-label="从字幕选择结束时间" value={rangePick.end ?? ""}
                  onChange={event => { const index = Number(event.target.value); const cue = rangeCues[index]; if (!cue) return;
                    setRangeEnd(time(cue.end_seconds)); setRangePick({ ...rangePick, end: index }); }}>
                  <option value="">从字幕选择终点…</option>
                  {rangeCues.map((cue, index) => <option key={`re${index}`} value={index}>{cueLabel(cue)}</option>)}
                </select>
              </div>
              <div className="companion-burn">
                <select className="ny-input" aria-label="时间段合成字幕内容" value={rangeVariant} onChange={event => setBurnVariant({ ...burnVariant, range: event.target.value as BurnVariant })}>
                  <option value="bilingual" disabled={!hasBilingual}>双语字幕</option>
                  <option value="zh" disabled={!hasBilingual}>仅译文</option>
                  <option value="original">仅原文</option>
                </select>
                <button className="ny-button" type="button" disabled={!rangeStart.trim() || !rangeEnd.trim() || rangeBurning || burn.isPending || !!busy} onClick={submitRange}>
                  {rangeBurning ? "正在合成…" : rangeEntry?.state === "completed" ? "重新合成这一段" : rangeResumable ? "继续合成这一段" : "合成所选时间段"}
                </button>
                {rangeBurning && <span className="companion-burn-progress" role="status" aria-label={`时间段合成进度 ${rangePercent}%`}>
                  <span className="companion-burn-bar"><span style={{ width: `${rangePercent}%` }} /></span>
                  <span className="companion-burn-percent">{rangePercent}%{rangeEntry?.segments_total ? `（${rangeEntry.segments_done ?? 0}/${rangeEntry.segments_total} 段）` : ""}</span>
                </span>}
                {rangeEntry?.state === "completed" && rangeEntry.file && <a className="ny-button" href={fileUrl(job.id, rangeEntry.file, true)}><ArrowDownToLine size={16} />下载合成版</a>}
                {rangeEntry?.state === "failed" && <span className="companion-error" role="alert">{rangeEntry.error ?? "合成失败，请重试"}</span>}
                {rangeError && <span className="companion-error" role="alert">{rangeError}</span>}
              </div>
            </div>
          </div>}
          {job?.clips.map((item, index) => {
            const chosen = burnVariant[item.video] ?? "bilingual";
            const variant: BurnVariant = !hasBilingual && chosen !== "original" ? "original" : chosen;
            const entry = item.burns?.[variant];
            const burningThis = entry?.state === "burning";
            const doneSegments = entry?.segments_done ?? 0;
            const resumable = !burningThis && entry?.state !== "completed" && doneSegments > 0;
            const burnPercent = Math.round((entry?.progress ?? 0) * 100);
            return <div className="companion-result" key={item.video}>
              <div><strong>{item.title ? "臊子 · " + item.title : "切片 " + String(index + 1).padStart(2, "0")}</strong><p>{time(item.start)} — {time(item.end)} <span>· {(item.end - item.start).toFixed(1)} 秒{item.score !== null ? ` · 高光评分 ${item.score.toFixed(2)}` : ""}</span></p>{job.mode === "saozi" && <p className="companion-muted">{item.reasons.join("；")}</p>}</div>
              <div>
                <a className="ny-button" aria-label={`下载切片 ${index + 1} 视频`} href={fileUrl(job.id, item.video, true)}><ArrowDownToLine size={16} />MP4</a>
                <a className="ny-button" aria-label={`下载切片 ${index + 1} 字幕`} href={fileUrl(job.id, item.subtitles, true)}>SRT</a>
                {(item.bilingual_subtitles || hasBilingual) && <a className="ny-button" aria-label={`下载切片 ${index + 1} 译文字幕`} href={fileUrl(job.id, item.subtitles.replace(/\.srt$/, ".zh.srt"), true)}>译文 SRT</a>}
                {(item.bilingual_subtitles || hasBilingual) && <a className="ny-button" aria-label={`下载切片 ${index + 1} 双语字幕`} href={fileUrl(job.id, item.bilingual_subtitles ?? item.subtitles.replace(/\.srt$/, ".ja-zh.srt"), true)}>双语 SRT</a>}
              </div>
              <div className="companion-burn">
                <select className="ny-input" aria-label={`切片 ${index + 1} 合成字幕内容`} value={variant} onChange={event => setBurnVariant({ ...burnVariant, [item.video]: event.target.value as BurnVariant })}>
                  <option value="bilingual" disabled={!hasBilingual}>双语字幕</option>
                  <option value="zh" disabled={!hasBilingual}>仅译文</option>
                  <option value="original">仅原文</option>
                </select>
                <button className="ny-button" type="button" disabled={burningThis || burn.isPending} onClick={() => { setError(null); burn.mutate({ id: job.id, clip: item.video, variant }); }}>
                  {burningThis ? "正在合成…" : entry?.state === "completed" ? "重新合成视频" : resumable ? "继续合成视频" : "合成视频"}
                </button>
                {burningThis && <span className="companion-burn-progress" role="status" aria-label={`合成进度 ${burnPercent}%`}>
                  <span className="companion-burn-bar"><span style={{ width: `${burnPercent}%` }} /></span>
                  <span className="companion-burn-percent">{burnPercent}%{entry?.segments_total ? `（${doneSegments}/${entry.segments_total} 段）` : ""}</span>
                </span>}
                {entry?.state === "completed" && entry.file && <a className="ny-button" href={fileUrl(job.id, entry.file, true)}><ArrowDownToLine size={16} />下载合成版</a>}
                {entry?.state === "failed" && <span className="companion-error" role="alert">{entry.error ?? "合成失败，请重试"}</span>}
                {!hasBilingual && <span className="companion-muted">生成双语字幕后可合成译文版本</span>}
              </div>
            </div>;
          })}
          {!!job?.clips.length && <p className="companion-footnote">切片字幕从零开始计时；合成视频把所选字幕按当前样式直接烧进画面。</p>}
        </section>
        {tool === "topics" && <TopicSegmentsPanel job={job} onSeek={seekSource} />}
        {tool === "publish" && <PublishPanel job={job} />}
        </div>
      </aside>
      <div className="companion-workspace">
        <section className="companion-panel companion-progress" aria-label="处理进度">
          <div className="companion-section-heading"><div className="companion-panel-title"><h2>处理进度</h2></div>{job && <span className={`ny-stamp ny-stamp--${job.state === "completed" ? "success" : ["failed", "interrupted", "cancelled"].includes(job.state) ? "failed" : "running"}`}>{statusLabel(job)}</span>}</div>
          {unavailable && <div className="companion-error" role="alert">本地服务连接中断，正在重试。请确认启动窗口仍在运行。</div>}
          <ol className="ny-progress companion-stages" aria-label="处理阶段">{(job?.live ? ["检查环境", "录制直播", "字幕段落分析", "连续输出切片"] : ["检查环境", "下载／导入", "字幕与段落", "导出片段"]).map((label, index) => <li className={`ny-progress__stage ${job && index < stage ? "ny-progress__stage--complete" : job && index === stage ? ["failed", "interrupted", "cancelled"].includes(job.state) ? "ny-progress__stage--failed" : "ny-progress__stage--running" : ""}`} key={label}>{job && index < stage ? <Check size={14} /> : <span>{index + 1}</span>}{label}</li>)}</ol>
          <p className="companion-status" role="status">{job?.message ?? "等待创建任务"}</p>
          {error && <div className="companion-error" role="alert">{error}</div>}
          {config.data && !config.data.ready && <p className="companion-error" role="alert">缺少：{config.data.missing.join("、")}。请按使用指南准备环境。</p>}
          {job?.can_stop && <button className="ny-button" disabled={stop.isPending} onClick={()=>stop.mutate(job.id)}>停止直播并导出剩余内容</button>}
          {job?.error && <p className="companion-error" role="alert">{job.error}</p>}
          {job?.capture_warning && <p className="companion-error" role="alert">{job.capture_warning}</p>}
          {job?.subtitle_template && <p className="companion-muted">实时字幕模板：{job.subtitle_template.name}（任务创建时的样式）</p>}
          {job?.live && job.subtitle_template && job.state !== 'completed' && <p className="companion-footnote">录制中的播放器预览采用浏览器排版；精确样式以导出的 ASS 和字幕视频为准。</p>}
          {job?.subtitle_style_error && <p className="companion-error" role="alert">{job.subtitle_style_error}</p>}
          {!!job?.discontinuities?.length && <p className="companion-muted">发生 {job.discontinuities.length} 次断流，缺失内容无法恢复；已分别保留断流前后片段。</p>}
          {job?.state === "failed" && !job.can_resume && <p className="companion-muted">下载未完成，请检查链接后重新创建任务。</p>}
          {job?.can_resume && <button className="ny-button" disabled={!!busy || resume.isPending} onClick={() => { setError(null); resume.mutate(job.id); }}>恢复处理</button>}
          {job?.state === "failed" && job.has_source && <button className="ny-button" disabled={!!busy || reasr.isPending || unavailable} onClick={() => { setError(null); reasr.mutate(job.id); }}>{reasr.isPending ? "正在重新识别…" : "重新识别"}</button>}
          {cancellable(job ?? undefined) && <button className="ny-button" disabled={cancel.isPending || job?.state === "cancelling"} onClick={() => { setError(null); cancel.mutate(job!.id); }}>{job?.state === "cancelling" ? "正在终止…" : "终止任务"}</button>}
          {job?.state === "completed" && <>
            <span className="translate-actions">
              <button className="ny-button" disabled={!job.has_source || !!busy || reasr.isPending || unavailable} onClick={() => { setError(null); reasr.mutate(job.id); }}>{reasr.isPending ? "正在重新识别…" : "重新识别"}</button>
              <button className="ny-button" disabled={!translationConfigured || !!busy || translate.isPending || unavailable} onClick={() => { setError(null); translate.mutate({ id: job.id, clip_index: translateClipIndex === "all" ? undefined : Number(translateClipIndex) }); }}>{hasBilingual ? "重新翻译" : ["failed", "interrupted"].includes(job.translation?.state) ? "继续翻译" : "生成翻译"}</button>
              <button className={`ny-button ${config.data?.glossary_collect_candidates ? "ny-button--primary" : ""}`} disabled={glossarySettings.isPending || unavailable} onClick={() => glossarySettings.mutate(!(config.data?.glossary_collect_candidates ?? true))}>{config.data?.glossary_collect_candidates ? "收集术语✓" : "收集术语"}</button>
              <select className="ny-input translate-range" aria-label="翻译范围" value={translateClipIndex} onChange={event => setTranslateClipIndex(event.target.value)} disabled={translate.isPending || unavailable}>
                <option value="all">全部切片</option>
                {job.clips.map((item, index) => <option key={item.video} value={String(index)}>切片 {index + 1}（{time(item.start)} — {time(item.end)}）</option>)}
              </select>
            </span>
            {job.translation && job.translation.state !== "not_started" && <p role="status">{job.translation.message ?? `翻译 ${job.translation.done}/${job.translation.total} 条`}{hasBilingual ? " · 已完成" : job.translation.state === "interrupted" ? " · 已中断，可继续" : ""}</p>}
            {job.translation?.error && <p className="companion-error" role="alert">{job.translation.error}</p>}
          </>}
        </section>
        <section className="companion-panel companion-preview" aria-label="视频预览">
          <div className="companion-section-heading"><div className="companion-panel-title"><h1>预览与时间轴</h1></div><span className="companion-muted">{job?.duration ? `原视频 ${time(job.duration)}` : ""}</span></div>
          {job && (job.has_source || job.clips.length > 0) ? <>
            <div className="companion-preview-tabs">{job.has_source && <button className="ny-button" aria-pressed={!clip} onClick={() => setPreview("source.mp4")}>完整视频</button>}{job.clips.map((item, index) => <button className="ny-button" key={item.video} aria-label={`预览切片 ${index + 1}`} aria-pressed={preview === item.video} onClick={() => setPreview(item.video)}>切片 {index + 1}</button>)}</div>
            {hasBilingual && <label className="ny-field">预览字幕<select className="ny-input" value={subtitleMode} onChange={event => setSubtitleMode(event.target.value as SubtitleMode)}><option value="bilingual">中日双语</option><option value="zh">仅译文（中文）</option><option value="original">仅原文</option></select></label>}
            <SubtitlePreview video={video} source={`${job.id}/${preview}`}
              segments={clip ? clipSegments(job.segments, clip.start, clip.end) : job.segments}
              zhSegments={clip ? clipSegments(job.zh_segments, clip.start, clip.end) : job.zh_segments}
              bilingualSegments={clip ? clipSegments(job.bilingual_segments, clip.start, clip.end) : job.bilingual_segments}
              style={legacyStyle.currentStyle} mode={previewMode} shapes={shapesQuery.data?.shapes ?? []}
              danmaku={danmakuInfo.data?.count && danmakuBurn.enabled ? {
                jobId: job.id, offset: clip ? clip.start : 0,
                fontSize: danmakuBurn.font_size, areaHeight: danmakuBurn.area_height,
              } : null}><video key={`${job.id}/${preview}`} ref={video} src={fileUrl(job.id, preview)} controls preload="metadata" aria-label={clip ? "切片预览" : "完整视频预览"} onLoadedMetadata={() => { if (seek !== null && video.current) { video.current.currentTime = seek; setSeek(null); } }}>
              {(clip || job.segments.length > 0) && <track key={subtitleFile} kind="subtitles" src={fileUrl(job.id, subtitleFile)} srcLang={previewMode === "original" ? (job.language === "auto" ? "und" : job.language) : "zh"} label={previewMode === "bilingual" ? "中日双语" : previewMode === "zh" ? "译文字幕" : "识别字幕"} default />}
            </video></SubtitlePreview>
            <div className="companion-ruler"><span>00:00</span><span>{time((job.duration ?? 0) / 2)}</span><span>{time(job.duration ?? 0)}</span></div>
            <div className="companion-timeline" aria-label="切片时间轴">{job.clips.map((item, index) => <button key={item.video} aria-label={`在时间轴预览切片 ${index + 1}`} aria-pressed={preview === item.video} onClick={() => setPreview(item.video)}><span className="companion-timeline-fill" style={{ left: `${item.start / (job.duration ?? 1) * 100}%`, width: `${(item.end - item.start) / (job.duration ?? 1) * 100}%` }} /><span>切片 {index + 1} · {time(item.start)} — {time(item.end)}</span></button>)}</div>
          </> : <div className="companion-empty-preview"><Film size={42} strokeWidth={1} /><strong>你的下一段精彩，从这里开始</strong><p>下载完成后可以预览视频<br />字幕和切片会随处理进度出现</p></div>}
          {job && visibleSegments.length > 0 && <details className="companion-transcript" open><summary>{transcriptTitle} <span>{visibleSegments.length} 条 · 点击时间跳转{canEditTranslations ? " · 点「修改」可改译文" : ""}</span></summary><div>{visibleSegments.map((segment, index) => {
            if (editCue?.id === segment.id) return <div key={`${segment.id}/${index}`} className="transcript-editing">
              <time>{time(segment.start_seconds)}</time>
              <textarea value={editCue.value} rows={2} autoFocus onChange={event => setEditCue({ id: segment.id, value: event.target.value })} />
              <span className="transcript-edit-actions">
                <button className="ny-button" type="button" disabled={editTranslation.isPending} onClick={() => editTranslation.mutate({ id: segment.id, text: editCue.value })}>保存</button>
                <button className="ny-button ny-button--quiet" type="button" onClick={() => setEditCue(null)}>取消</button>
              </span>
            </div>;
            return <button key={`${segment.id}/${index}`} onClick={() => seekSource(segment.start_seconds)}><time>{time(segment.start_seconds)}</time><span style={{ whiteSpace: "pre-line" }}>{segment.text}</span>{canEditTranslations && <span className="transcript-edit" onClick={event => { event.stopPropagation(); setEditCue({ id: segment.id, value: zhPart(segment.text) }); }}>修改</span>}</button>;
          })}</div></details>}
        </section>
      </div>
        </>
      )}
    </main>
  </div>;
}
