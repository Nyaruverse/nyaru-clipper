import { useEffect, useRef, useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowDownToLine, Captions, Check, Film, History, Plus, Scissors, SlidersHorizontal, X } from "lucide-react";

import { LlmSettings } from "./LlmSettings";
import { SubtitleEditor } from "./SubtitleEditor";
import { CueEditor } from "./CueEditor";
import { useSubtitleDocument } from "./useSubtitleDocument";
import { documentProblem, nudgeCueStyle, patchCues, type Language } from "./subtitleDocument";
import type { FontCatalog } from './TextStyleFields';
import { SubtitlePreview } from "./SubtitlePreview";
import { SubtitleExports, useSubtitleExports } from "./SubtitleExports";
import { defaultStyle, subtitleApi, type SubtitleStyle, type SubtitleSettings } from "./subtitleStyle";

import { api, time, parseTime, running, statusLabel, fileUrl, type Job, type JobInput, type CompanionConfig } from "./companionApi";

const TOOLS = [
  { id: "create", label: "新建任务", icon: Plus },
  { id: "slice", label: "切片方式", icon: Scissors },
  { id: "subtitle", label: "字幕样式", icon: Captions },
  { id: "ai", label: "AI 设置", icon: SlidersHorizontal },
  { id: "history", label: "任务记录", icon: History },
  { id: "export", label: "导出", icon: ArrowDownToLine },
] as const;
type Tool = typeof TOOLS[number]["id"];

export function Companion() {
  const [tool, setTool] = useState<Tool | null>(null);
  const toolbar = useRef<HTMLElement>(null);
  const drawer = useRef<HTMLElement>(null);
  useEffect(() => { if (drawer.current) drawer.current.scrollTop = 0; }, [tool]);
  const queryClient = useQueryClient();
  const [url, setUrl] = useState("");
  const [mode, setMode] = useState<"ranges" | "highlights" | "saozi">("ranges");
  const [source, setSource] = useState("replay");
  const [localFile, setLocalFile] = useState<File | null>(null);
  const [ranges, setRanges] = useState<[string, string][]>([["00:00", "00:30"]]);
  const [highlights, setHighlights] = useState(3);
  const [language, setLanguage] = useState("auto");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [preview, setPreview] = useState<string>("source.mp4");
  const [seek, setSeek] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [subtitleMode, setSubtitleMode] = useState("bilingual");
  const video = useRef<HTMLVideoElement>(null);
  const config = useQuery({ queryKey: ["companion", "config"], queryFn: () => api<CompanionConfig>("/config"), refetchInterval: 15000 });
  const history = useQuery({ queryKey: ["companion", "jobs"], queryFn: () => api<Job[]>("/jobs"), refetchInterval: 3000 });
  const detail = useQuery({ queryKey: ["companion", "job", selectedId], queryFn: () => api<Job>(`/jobs/${selectedId}`), enabled: selectedId !== null,
    refetchInterval: query => query.state.status === "error" ? 3000 : running(query.state.data) ? 1000 : false });
  const settings = useQuery({queryKey:["companion","subtitle-settings"],queryFn:()=>subtitleApi<SubtitleSettings>("/subtitle-settings")});
  const fonts = useQuery({queryKey:['companion','subtitle-fonts'],queryFn:()=>subtitleApi<FontCatalog>('/subtitle-fonts'),staleTime:Infinity});
  const [styleDraft,setStyleDraft] = useState<SubtitleStyle | null>(null);
  const [project,setProject] = useState<string | null>(null);
  const editing = useSubtitleDocument(selectedId, detail.data?.state === 'completed', detail.data?.translation?.state);
  const documentDraft = editing.document;
  const style = documentDraft?.style ?? styleDraft ?? settings.data?.style ?? defaultStyle;
  const [cueSelection,setCueSelection] = useState<string[]>([]);
  const [cueLanguage,setCueLanguage] = useState<Language>('original');
  const [linked,setLinked] = useState(false);
  const [currentTime,setCurrentTime] = useState(0);
  const [loopCue,setLoopCue] = useState(false);
  const selectedCue = documentDraft?.cues.find(cue => cueSelection.includes(cue.id));
  const loop = loopCue && selectedCue ? {start:selectedCue.start_seconds,end:selectedCue.end_seconds} : null;
  useEffect(() => { setCueSelection([]); setLoopCue(false); },[selectedId]);
  useEffect(() => { if (documentDraft?.cues.length && !cueSelection.some(id => documentDraft.cues.some(cue => cue.id === id))) setCueSelection([documentDraft.cues[0].id]); },[documentDraft,cueSelection]);
  const updateStyle = (next: SubtitleStyle) => { if (documentDraft) editing.change(current => ({...current,style:next})); else setStyleDraft(next); };
  const moveCues = (dx: number,dy: number) => editing.change(current => patchCues(current,cueSelection,cue => ({...cue,
    [`${cueLanguage}_style`]:nudgeCueStyle(current,cue,cueLanguage,dx,dy,subtitleMode === 'bilingual'),
    ...(linked ? {[`${cueLanguage === 'original' ? 'translation' : 'original'}_style`]:nudgeCueStyle(current,cue,cueLanguage === 'original' ? 'translation' : 'original',dx,dy,subtitleMode === 'bilingual')} : {}),
  })));
  const exports = useSubtitleExports(selectedId);
  const exportBusy = exports.data?.active?.state === "exporting";
  const job = detail.data;
  const visibleJobs = history.data?.map(item => item.id === job?.id ? job : item);
  const busy = visibleJobs?.some(running) || running(job) || exportBusy;
  const create = useMutation({ mutationFn: async (payload: JobInput | {file:File;language:string}) => {
    if (!("file" in payload)) return api<{id:string}>("/jobs", payload);
    const response = await fetch(`/companion-api/saozi/upload?language=${encodeURIComponent(payload.language)}`, {method:"POST",body:payload.file});
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
  const translate = useMutation({ mutationFn: (id: string) => api(`/jobs/${id}/translate`, {}),
    onSuccess: () => { void queryClient.invalidateQueries({ queryKey: ["companion"] }); }, onError: err => setError(err.message) });
  const stop = useMutation({mutationFn:(id:string)=>api(`/jobs/${id}/stop`,{}),
    onSuccess:()=>{void queryClient.invalidateQueries({queryKey:["companion"]});},onError:err=>setError(err.message)});

  useEffect(() => { if (!selectedId && history.data?.length) setSelectedId(history.data[0].id); }, [selectedId, history.data]);
  useEffect(() => { setPreview("source.mp4"); setSeek(null); }, [selectedId]);
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
      if (mode === "ranges") ranges.forEach(([start, end], index) => { if (parseTime(start) >= parseTime(end)) throw new Error(`片段 ${index + 1}：结束时间必须大于开始时间`); });
      if (mode === "saozi" && !llmConfigured) throw new Error(chatgptSelected ? "臊子需要先连接 ChatGPT、授权订阅额度并保存可用模型" : "臊子需要先保存 DeepSeek API Key 并选择 Flash");
      if (mode === "saozi" && source === "file") {
        if (!localFile) throw new Error("请选择本地录像");
        create.mutate({file:localFile,language});
      } else create.mutate({ url: url.trim(), ranges: mode === "ranges" ? ranges : [], highlights: mode === "highlights" ? highlights : null, language,
        ...(mode === "saozi" ? {saozi:true,live:source === "live"} : {}) });
    } catch (err) { setError(err instanceof Error ? err.message : "请检查输入"); }
  }

  const clip = job?.clips.find(item => item.video === preview);
  const stage = job?.state === "completed" ? 4 : ({ preparing: 0, downloading: 1, download_failed: 1, downloaded: 2, transcribing: 2, subtitles_ready: 3, exporting: 3 }[job?.phase ?? ""] ?? 0);
  const unavailable = config.isError || history.isError || detail.isError;
  const hasBilingual = job?.translation?.state === "completed";
  const hasPreviewBilingual = job?.bilingual_files?.includes((clip?.subtitles ?? "subtitles.srt").replace(/\.srt$/, ".ja-zh.srt")) ?? hasBilingual;
  const showBilingual = (documentDraft ? documentDraft.cues.some(cue => !!cue.translation) : hasPreviewBilingual) && subtitleMode === "bilingual";
  const subtitleFile = (clip?.subtitles ?? "subtitles.srt").replace(/\.srt$/, showBilingual ? ".ja-zh.vtt" : ".vtt");
  const visibleSegments = documentDraft ? documentDraft.cues.map(cue => ({...cue,text:showBilingual && cue.translation ? `${cue.text}\n${cue.translation}` : cue.text})) : (showBilingual ? job?.bilingual_segments : job?.segments) ?? [];
  const seekSource = (at: number) => {
    if (job?.has_source) { setPreview('source.mp4'); setSeek(at); }
    else { const target = job?.clips.find(item => item.start <= at && at < item.end); if (target) {setPreview(target.video);setSeek(at-target.start);} }
  };

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
    <main className={`companion-layout ${tool ? "has-drawer" : ""}`}>
      <aside ref={drawer} id="companion-drawer" className="companion-drawer" aria-label="工具选项" hidden={!tool}>
        <div className="companion-drawer-heading"><h2>{TOOLS.find(item => item.id === tool)?.label}</h2><button type="button" className="ny-button ny-button--quiet" aria-label="收起工具面板" onClick={closeDrawer}><X size={16} /></button></div>
        <div className="companion-drawer-content">
        <section className="companion-panel" hidden={tool !== "create" && tool !== "slice"}>
          <p className="companion-muted" hidden={tool !== "create"}>粘贴链接，生成字幕与时间轴，再导出你需要的片段。</p>
          <form onSubmit={submit} onInvalid={event => {
            event.preventDefault();
            const invalid = Array.from(event.currentTarget.querySelectorAll("input")).find(input => input.willValidate && !input.validity.valid);
            if (!invalid || invalid !== event.target) return;
            setTool(invalid.closest('[data-tool-pane="slice"]') ? "slice" : "create");
            setError(invalid.validationMessage);
            requestAnimationFrame(() => invalid.focus());
          }}>
            <fieldset disabled={busy || create.isPending}>
              <div className="companion-task-fields" data-tool-pane="create" hidden={tool !== "create"}>
              {mode === "saozi" && <label className="ny-field">臊子输入<select className="ny-input" value={source} onChange={event=>setSource(event.target.value)}><option value="replay">直播回放链接</option><option value="file">本地录像</option><option value="live">Bilibili 实时直播</option></select></label>}
              {mode === "saozi" && source === "file" ? <label key="file" className="ny-field">本地录像<input className="ny-input" type="file" accept="video/*,.mkv,.flv,.ts" onChange={event=>setLocalFile(event.target.files?.[0] ?? null)} /></label> : <label key="url" className="ny-field">视频链接<input className="ny-input" type="url" required placeholder={mode === "saozi" && source === "live" ? "https://live.bilibili.com/直播间号" : "https://…"} value={url} onChange={event => setUrl(event.target.value)} /></label>}
              <label className="ny-field">视频语种<select className="ny-input" value={language} onChange={event => setLanguage(event.target.value)}><option value="auto">自动识别</option><option value="zh">中文</option><option value="en">英语</option><option value="ja">日语</option></select></label>
              <button className="ny-button" type="button" onClick={() => setTool("slice")}><Scissors size={16} />{mode === "ranges" ? `指定时间段 · ${ranges.length} 段` : mode === "saozi" ? "臊子" : `高光自动切片 · 最多 ${highlights} 段`}</button>
              </div>
              <div className="companion-task-fields" data-tool-pane="slice" hidden={tool !== "slice"}>
              <fieldset className="companion-mode"><legend>切片方式</legend>
                <label className={mode === "ranges" ? "is-selected" : ""}><input type="radio" name="mode" checked={mode === "ranges"} onChange={() => setMode("ranges")} />指定时间段</label>
                <label className={mode === "highlights" ? "is-selected" : ""}><input type="radio" name="mode" checked={mode === "highlights"} onChange={() => setMode("highlights")} />高光自动切片</label>
                <label className={mode === "saozi" ? "is-selected" : ""}><input type="radio" name="mode" checked={mode === "saozi"} onChange={() => setMode("saozi")} />臊子</label>
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
              </div> : mode === "highlights" ? <div className="companion-highlights">
                <label className="ny-field">最多导出片段数<input className="ny-input" type="number" min={1} max={100} required value={highlights} onChange={event => setHighlights(Number(event.target.value))} /></label>
                <p className="companion-muted">根据字幕密度、笑声与兴奋词筛选。达不到评分阈值时，会保留完整字幕并报告零切片。</p>
              </div> : <p className="companion-muted">连续切为约 1–2 分钟，{chatgptSelected ? "ChatGPT" : "DeepSeek Flash"} 根据字幕段落选择切点，并自动生成中日双语字幕，会使用{chatgptSelected ? "订阅" : " API "}额度。短尾段完整保留。{source === "live" ? "实时结果会有缓冲与处理延迟；停止后导出剩余内容。" : "原视频保留，切片按顺序覆盖全部内容。"}</p>}
              </div>
            </fieldset>
            <button className="ny-button ny-button--primary companion-start" type="submit" disabled={!config.data?.ready || !!busy || create.isPending || unavailable}><Scissors size={16} />{create.isPending ? "正在提交…" : busy ? "已有任务处理中" : "开始处理"}</button>
          </form>
          <p className="companion-footnote">识别和切片在本机完成 · 下载需要网络</p>
        </section>
        <section className="companion-panel" hidden={tool !== "subtitle"}>
          {job?.state === 'completed' && <div className="cue-session-status">
            <p role="status">{editing.saving ? '正在保存字幕编辑稿…' : editing.dirty ? '有未保存修改，稍候自动保存' : documentDraft ? `字幕编辑稿已保存 · 第 ${documentDraft.revision} 版` : '载入字幕编辑稿…'}</p>
            {editing.error && <p role="alert" className="companion-error">{editing.error}</p>}
            {editing.error && documentDraft && <details><summary>保留当前编辑稿（JSON，可复制）</summary><textarea className="ny-input" aria-label="当前编辑稿 JSON" rows={8} readOnly value={JSON.stringify(documentDraft,null,2)} /></details>}
            {documentDraft && documentProblem(documentDraft) && <p role="alert" className="companion-error">{documentProblem(documentDraft)}</p>}
            {(editing.error || editing.dirty) && <button className="ny-button" disabled={editing.saving || !!busy} onClick={editing.retry}>重试保存／载入</button>}
            {editing.error && <button className="ny-button" disabled={editing.saving || !!busy} onClick={() => {if (window.confirm('从当前源字幕重新开始编辑？原始字幕和旧导出会保留；旧编辑稿由服务备份。')) editing.resetSource();}}>从当前源字幕重新开始</button>}
          </div>}
          {documentDraft && <fieldset disabled={!!busy}><CueEditor document={documentDraft} selected={cueSelection} onSelect={setCueSelection} change={editing.change} language={cueLanguage} onLanguage={setCueLanguage} currentTime={currentTime} onSeek={seekSource} undo={editing.undo} redo={editing.redo} canUndo={editing.canUndo} canRedo={editing.canRedo} linked={linked} onLinked={setLinked} fonts={fonts.data} bilingual={!!showBilingual} />
            <label className="cue-toggle"><input type="checkbox" checked={loopCue} onChange={event => {setLoopCue(event.target.checked); if (event.target.checked && selectedCue) seekSource(selectedCue.start_seconds);}} />循环播放当前字幕（点击视频播放）</label></fieldset>}
          {!documentDraft && <p className="companion-footnote">任务完成后可逐条编辑字幕；原始识别、翻译和旧导出会保留。</p>}
          <details className="cue-global-style" open={!documentDraft}><summary>全局默认样式与模板</summary><SubtitleEditor embedded settings={settings.data} error={settings.error} style={style} onStyle={updateStyle} project={project} onProject={setProject} busy={!!busy} fonts={fonts.data} /></details>
        </section>
        <section className="companion-panel" aria-label="AI 设置" hidden={tool !== "ai"}>
          <LlmSettings config={config.data} busy={!!busy} />
          {taskModel && <p className="companion-footnote">当前任务模型：{taskModel}</p>}
        </section>
        <section className="companion-panel companion-history" aria-label="任务记录" hidden={tool !== "history"}>
          <h2>任务记录 <span>{history.data?.length ?? 0}</span></h2>
          {!history.data?.length && <p className="companion-muted">开始第一个任务后，结果会保存在这里。</p>}
          {visibleJobs?.map(item => <button className="companion-history-item" key={item.id} aria-pressed={item.id === selectedId} onClick={() => { setSelectedId(item.id); setError(null); }}><span><strong>{item.mode === "saozi" ? item.live ? "臊子 · 实时" : "臊子" : item.mode === "highlights" ? "高光切片" : "指定片段"}</strong><small>{new Date(item.started_at * 1000).toLocaleString("zh-CN", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" })} · {item.id.slice(0, 6)}</small></span><span>{statusLabel(item)}</span></button>)}
        </section>
        <section className="companion-panel companion-results" aria-label="导出结果" hidden={tool !== "export"}>
          <p className="companion-muted">{job?.clips.length ?? 0} 个切片</p>
          {job?.segments.length ? <div className="companion-downloads"><a className="ny-button" href={fileUrl(job.id, "subtitles.srt", true)}><ArrowDownToLine size={16} />完整字幕 SRT</a><a className="ny-button" href={fileUrl(job.id, "transcript.txt", true)}><ArrowDownToLine size={16} />字幕文字 TXT</a></div> : <p className="companion-muted">生成的字幕和视频将出现在这里，可直接下载。</p>}
          {job && hasBilingual && <a className="ny-button" href={fileUrl(job.id, "subtitles.ja-zh.srt", true)}>完整双语字幕 SRT</a>}
          {job?.state === "completed" && !job.clips.length && <p className="companion-muted">没有达到阈值的高光，已保留完整字幕。</p>}
          {job?.clips.map((item, index) => <div className="companion-result" key={item.video}><div><strong>{item.title ? "臊子 · " + item.title : "切片 " + String(index + 1).padStart(2, "0")}</strong><p>{time(item.start)} — {time(item.end)} <span>· {(item.end - item.start).toFixed(1)} 秒{item.score !== null ? ` · 高光评分 ${item.score.toFixed(2)}` : ""}</span></p>{job.mode === "saozi" && <p className="companion-muted">{item.reasons.join("；")}</p>}</div><div><a className="ny-button" aria-label={`下载切片 ${index + 1} 视频`} href={fileUrl(job.id, item.video, true)}><ArrowDownToLine size={16} />MP4</a><a className="ny-button" aria-label={`下载切片 ${index + 1} 字幕`} href={fileUrl(job.id, item.subtitles, true)}>SRT</a>{(item.bilingual_subtitles || (hasBilingual && !job.bilingual_files)) && <a className="ny-button" aria-label={`下载切片 ${index + 1} 双语字幕`} href={fileUrl(job.id, item.bilingual_subtitles ?? item.subtitles.replace(/\.srt$/, ".ja-zh.srt"), true)}>双语 SRT</a>}</div></div>)}
          {job && job.segments.length > 0 && <SubtitleExports id={job.id} video={preview} bilingual={!!showBilingual} style={style} project={project} document={documentDraft} busy={!!busy || !settings.data?.style || editing.dirty || !!editing.error} burnAvailable={!!settings.data?.burn_available} nativeAvailable={!!settings.data?.native_handoff_available} status={exports.data} error={exports.error} />}
          {!!job?.clips.length && <p className="companion-footnote">切片字幕从零开始计时，下载视频与同名 SRT 即可继续编辑。</p>}
        </section>
        </div>
      </aside>
      <div className="companion-workspace">
        <section className="companion-panel companion-progress" aria-label="处理进度">
          <div className="companion-section-heading"><div className="companion-panel-title"><h2>处理进度</h2></div>{job && <span className={`ny-stamp ny-stamp--${job.state === "completed" ? "success" : ["failed", "interrupted"].includes(job.state) ? "failed" : "running"}`}>{statusLabel(job)}</span>}</div>
          {unavailable && <div className="companion-error" role="alert">本地服务连接中断，正在重试。请确认启动窗口仍在运行。</div>}
          <ol className="ny-progress companion-stages" aria-label="处理阶段">{(job?.live ? ["检查环境", "录制直播", "字幕段落分析", "连续输出切片"] : ["检查环境", "下载／导入", "字幕与段落", "导出片段"]).map((label, index) => <li className={`ny-progress__stage ${job && index < stage ? "ny-progress__stage--complete" : job && index === stage ? ["failed", "interrupted"].includes(job.state) ? "ny-progress__stage--failed" : "ny-progress__stage--running" : ""}`} key={label}>{job && index < stage ? <Check size={14} /> : <span>{index + 1}</span>}{label}</li>)}</ol>
          <p className="companion-status" role="status">{job?.message ?? "等待创建任务"}</p>
          {error && <div className="companion-error" role="alert">{error}</div>}
          {config.data && !config.data.ready && <p className="companion-error" role="alert">缺少：{config.data.missing.join("、")}。请按使用指南准备环境。</p>}
          {job?.can_stop && <button className="ny-button" disabled={stop.isPending} onClick={()=>stop.mutate(job.id)}>停止直播并导出剩余内容</button>}
          {job?.error && <p className="companion-error" role="alert">{job.error}</p>}
          {job?.capture_warning && <p className="companion-error" role="alert">{job.capture_warning}</p>}
          {!!job?.discontinuities?.length && <p className="companion-muted">发生 {job.discontinuities.length} 次断流，缺失内容无法恢复；已分别保留断流前后片段。</p>}
          {job?.state === "failed" && !job.can_resume && <p className="companion-muted">下载未完成，请检查链接后重新创建任务。</p>}
          {job?.can_resume && <button className="ny-button" disabled={!!busy || resume.isPending} onClick={() => { setError(null); resume.mutate(job.id); }}>恢复处理</button>}
          {job?.state === "completed" && <>
            <button className="ny-button" disabled={!translationConfigured || !!busy || translate.isPending || !!hasBilingual || unavailable} onClick={() => { setError(null); translate.mutate(job.id); }}>{hasBilingual ? "中日双语字幕已生成" : ["failed", "interrupted"].includes(job.translation?.state) ? "继续生成中日双语字幕" : "生成中日双语字幕"}</button>
            {job.translation && job.translation.state !== "not_started" && <p role="status">{job.translation.message ?? `翻译 ${job.translation.done}/${job.translation.total} 条`}{hasBilingual ? " · 已完成" : job.translation.state === "interrupted" ? " · 已中断，可继续" : ""}</p>}
            {job.translation?.error && <p className="companion-error" role="alert">{job.translation.error}</p>}
          </>}
          {exports.data?.active && <p role="status">{exports.data.active.message}</p>}
        </section>
        <section className="companion-panel companion-preview" aria-label="视频预览">
          <div className="companion-section-heading"><div className="companion-panel-title"><h1>预览与时间轴</h1></div><span className="companion-muted">{job?.duration ? `原视频 ${time(job.duration)}` : ""}</span></div>
          {job && (job.has_source || job.clips.length > 0) ? <>
            <div className="companion-preview-tabs">{job.has_source && <button className="ny-button" aria-pressed={!clip} onClick={() => setPreview("source.mp4")}>完整视频</button>}{job.clips.map((item, index) => <button className="ny-button" key={item.video} aria-label={`预览切片 ${index + 1}`} aria-pressed={preview === item.video} onClick={() => setPreview(item.video)}>切片 {index + 1}</button>)}</div>
            {(hasPreviewBilingual || documentDraft?.cues.some(cue => cue.translation)) && <label className="ny-field">预览字幕<select className="ny-input" value={subtitleMode} onChange={event => setSubtitleMode(event.target.value)}><option value="bilingual">中日双语</option><option value="original">原文字幕</option></select></label>}
            <SubtitlePreview video={video} source={`${job.id}/${preview}`} segments={job.segments} bilingual={showBilingual ? job.bilingual_segments : []} offset={clip?.start ?? 0} style={style} document={documentDraft} jobId={job.id} selected={cueSelection} language={cueLanguage} editing={tool === 'subtitle' && !busy} showBilingual={subtitleMode === 'bilingual'} onMove={moveCues} onTime={setCurrentTime} loop={loop}><video key={`${job.id}/${preview}`} ref={video} src={fileUrl(job.id, preview)} controls preload="metadata" aria-label={clip ? "切片预览" : "完整视频预览"} onLoadedMetadata={() => { if (seek !== null && video.current) { video.current.currentTime = seek; setSeek(null); } }}>
              {(clip || job.segments.length > 0) && <track key={subtitleFile} kind="subtitles" src={fileUrl(job.id, subtitleFile)} srcLang={showBilingual ? "zh" : job.language === "auto" ? "und" : job.language} label={showBilingual ? "中日双语" : "识别字幕"} default />}
            </video></SubtitlePreview>
            <div className="companion-ruler"><span>00:00</span><span>{time((job.duration ?? 0) / 2)}</span><span>{time(job.duration ?? 0)}</span></div>
            <div className="companion-timeline" aria-label="切片时间轴">{job.clips.map((item, index) => <button key={item.video} aria-label={`在时间轴预览切片 ${index + 1}`} aria-pressed={preview === item.video} onClick={() => setPreview(item.video)}><span className="companion-timeline-fill" style={{ left: `${item.start / (job.duration ?? 1) * 100}%`, width: `${(item.end - item.start) / (job.duration ?? 1) * 100}%` }} /><span>切片 {index + 1} · {time(item.start)} — {time(item.end)}</span></button>)}</div>
          </> : <div className="companion-empty-preview"><Film size={42} strokeWidth={1} /><strong>你的下一段精彩，从这里开始</strong><p>下载完成后可以预览视频<br />字幕和切片会随处理进度出现</p></div>}
          {job && visibleSegments.length > 0 && <details className="companion-transcript" open><summary>{showBilingual ? "完整双语字幕" : "完整字幕"} <span>{visibleSegments.length} 条 · 点击选择并跳转</span></summary><div>{visibleSegments.map((segment, index) => <button key={`${segment.id}/${index}`} onClick={() => { seekSource(segment.start_seconds); if (documentDraft) {setCueSelection([segment.id]);setTool('subtitle');} }}><time>{time(segment.start_seconds)}</time><span style={{ whiteSpace: "pre-line" }}>{segment.text}</span></button>)}</div></details>}
        </section>
      </div>
    </main>
  </div>;
}
