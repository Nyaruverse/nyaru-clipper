import { useEffect, useRef, useState, type CSSProperties, type FormEvent, type ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FileText, FolderCog, FolderOpen, Link2, Loader2, Play, Plus, RotateCcw, Square, Trash2, Upload } from "lucide-react";

import { api, time, type AutomationConfig, type AutomationStore, type AutomationTask, type LegacyStyleStore, type LegacyTextStyle, type RecorderRoom, type RecorderStore } from "./companionApi";

const LANGUAGES = [
  { id: "auto", label: "自动识别" },
  { id: "ja", label: "日语" },
  { id: "zh", label: "中文" },
  { id: "en", label: "英语" },
  { id: "ko", label: "韩语" },
];

const KIND_LABEL: Record<string, string> = { recording: "录播", upload: "本地视频", url: "视频链接" };
const TASK_STATE: Record<string, string> = {
  draft: "待开始", queued: "排队中", running: "执行中", completed: "已完成", failed: "失败",
};
const STAGE_STATE: Record<string, string> = {
  pending: "待执行", running: "执行中", done: "完成", skipped: "跳过", failed: "失败",
};

function stamp(value: number | null | undefined): string {
  if (!value) return "";
  const date = new Date(value * 1000);
  return Number.isNaN(date.getTime()) ? "" : date.toLocaleString("zh-CN", { hour12: false });
}

function cueStyle(t: LegacyTextStyle): CSSProperties {
  return {
    left: `${t.pos_x}%`, top: `${t.pos_y}%`,
    transform: t.align === "left" ? "translate(0, -50%)" : t.align === "right" ? "translate(-100%, -50%)" : "translate(-50%, -50%)",
    fontFamily: t.font_family, fontSize: `${(t.font_size / 1080) * 100}cqh`,
    lineHeight: 1.3, whiteSpace: "nowrap", maxWidth: "92%", overflow: "hidden", textOverflow: "ellipsis",
    background: t.background_opacity > 0 ? `${t.background_color}${Math.round(t.background_opacity * 255).toString(16).padStart(2, "0")}` : undefined,
  };
}

/** 预览字幕：与 StyledText 相同的真轮廓叠层描边（paint-order 外扩 + 2× 宽度），
 *  描边宽度用 em 随字号等比缩放，避免容器单位在旧版 text-stroke 解析器中失效。 */
function PreviewCue({ style, text }: { style: LegacyTextStyle; text: string }) {
  let cumulative = 0;
  const widths = style.outlines.map(outline => (cumulative += outline.width));
  const layers: ReactNode[] = [];
  for (let i = style.outlines.length - 1; i >= 0; i--) {
    layers.push(<span key={i} aria-hidden style={{
      position: "absolute", inset: 0, color: style.outlines[i].color,
      WebkitTextStroke: `${(2 * widths[i] / style.font_size).toFixed(3)}em ${style.outlines[i].color}`,
      paintOrder: "stroke fill",
    }}>{text}</span>);
  }
  layers.push(<span key="fill" style={{ position: "relative", color: style.text_color }}>{text}</span>);
  return (
    <span className="automation-preview-cue" style={cueStyle(style)}>
      <span style={{ position: "relative", display: "inline-block" }}>{layers}</span>
    </span>
  );
}

function Toggle({ on, onChange, disabled, children }: { on: boolean; onChange: (v: boolean) => void; disabled?: boolean; children: ReactNode }) {
  return <button type="button" className="automation-toggle" aria-pressed={on} disabled={disabled} onClick={() => onChange(!on)}>{children}</button>;
}

export function LiveAutomationPanel({ onOpenJob }: { onOpenJob: (jobId: string) => void }) {
  const queryClient = useQueryClient();
  const recorder = useQuery({ queryKey: ["companion", "recorder"], queryFn: () => api<RecorderStore>("/recorder"), refetchInterval: 10000 });
  const automation = useQuery({ queryKey: ["companion", "automation"], queryFn: () => api<AutomationStore>("/automation"), refetchInterval: 4000 });
  const styleStore = useQuery({ queryKey: ["companion", "subtitle-style"], queryFn: () => api<LegacyStyleStore>("/subtitle-style"), refetchInterval: 30000 });
  const [roomInput, setRoomInput] = useState("");
  const [roomName, setRoomName] = useState("");
  const [templateId, setTemplateId] = useState("");
  const [templateName, setTemplateName] = useState("");
  const [config, setConfig] = useState<AutomationConfig | null>(null);
  const [url, setUrl] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [editingPath, setEditingPath] = useState(false);
  const [pathInput, setPathInput] = useState("");
  const upload = useRef<HTMLInputElement>(null);
  const danmakuInput = useRef<HTMLInputElement>(null);
  // 已选但还没挂到任务上的弹幕文件：下一次上传视频时自动一并附加
  const [danmakuPick, setDanmakuPick] = useState<File | null>(null);
  const [danmakuNote, setDanmakuNote] = useState<string | null>(null);

  useEffect(() => {
    if (!config && automation.data) setConfig(automation.data.default_config);
  }, [automation.data, config]);

  const refreshRecorder = () => queryClient.invalidateQueries({ queryKey: ["companion", "recorder"] });
  const refreshAutomation = () => queryClient.invalidateQueries({ queryKey: ["companion", "automation"] });

  const addRoom = useMutation({
    mutationFn: (payload: { room: string; name: string }) => api<RecorderRoom>("/recorder/rooms", payload),
    onSuccess: () => { setRoomInput(""); setRoomName(""); setError(null); void refreshRecorder(); },
    onError: (err: Error) => setError(err.message),
  });
  const changeRoom = useMutation({
    mutationFn: (payload: { room_id: string; patch: { enabled?: boolean; auto_run?: boolean } }) =>
      api<RecorderRoom>(`/recorder/rooms/${payload.room_id}`, payload.patch, "PUT"),
    onSuccess: () => void refreshRecorder(),
    onError: (err: Error) => setError(err.message),
  });
  const dropRoom = useMutation({
    mutationFn: (roomId: string) => api(`/recorder/rooms/${roomId}`, {}, "DELETE"),
    onSuccess: () => void refreshRecorder(),
    onError: (err: Error) => setError(err.message),
  });
  const startRecording = useMutation({
    mutationFn: (roomId: string) => api<{ ok: boolean }>(`/recorder/rooms/${roomId}/start`, {}, "POST"),
    onSuccess: () => { setError(null); void refreshRecorder(); },
    onError: (err: Error) => { setError(err.message); void refreshRecorder(); },
  });
  const stopRecording = useMutation({
    mutationFn: (roomId: string) => api<{ ok: boolean }>(`/recorder/rooms/${roomId}/stop`, {}, "POST"),
    onSuccess: () => { setError(null); void refreshRecorder(); },
    onError: (err: Error) => { setError(err.message); void refreshRecorder(); },
  });
  const openFolder = useMutation({
    mutationFn: () => api<{ opened: boolean }>("/recorder/open-folder", {}, "POST"),
    onError: (err: Error) => setError(err.message),
  });
  const savePath = useMutation({
    mutationFn: (recordPath: string | null) =>
      api<{ record_path: string; default_record_path: string; custom: boolean }>("/recorder/settings", { record_path: recordPath }, "PUT"),
    onSuccess: () => { setError(null); setEditingPath(false); void refreshRecorder(); },
    onError: (err: Error) => setError(err.message),
  });
  const retryTask = useMutation({
    mutationFn: (taskId: string) => api(`/automation/tasks/${taskId}/retry`, {}, "POST"),
    onSuccess: () => void refreshAutomation(),
    onError: (err: Error) => setError(err.message),
  });
  const startTask = useMutation({
    mutationFn: (taskId: string) => api(`/automation/tasks/${taskId}/start`, {}, "POST"),
    onSuccess: () => { setError(null); void refreshAutomation(); },
    onError: (err: Error) => setError(err.message),
  });
  const dropTask = useMutation({
    mutationFn: (taskId: string) => api(`/automation/tasks/${taskId}`, undefined, "DELETE"),
    onSuccess: () => void refreshAutomation(),
    onError: (err: Error) => setError(err.message),
  });
  const saveTemplate = useMutation({
    mutationFn: (payload: { name: string; config: AutomationConfig }) =>
      api<{ templates: AutomationStore["templates"] }>("/automation/templates", payload),
    onSuccess: (result) => {
      setTemplateName("");
      const created = result.templates.find(item => item.name === templateName.trim());
      if (created) setTemplateId(created.id);
      void refreshAutomation();
    },
    onError: (err: Error) => setError(err.message),
  });
  const startUrl = useMutation({
    mutationFn: () => api<AutomationTask>("/automation/tasks", {
      url: url.trim(), title: url.trim(), template_id: templateId || null, config,
    }),
    onSuccess: () => { setUrl(""); setError(null); void refreshAutomation(); },
    onError: (err: Error) => setError(err.message),
  });
  const attachDanmaku = useMutation({
    mutationFn: async (payload: { taskId: string; file: File }) => {
      const response = await fetch(`/companion-api/automation/tasks/${payload.taskId}/danmaku`, {
        method: "POST", headers: { "x-filename": encodeURIComponent(payload.file.name) }, body: payload.file,
      });
      const result: { detail?: string; count?: number } = await response.json();
      if (!response.ok) throw new Error(result.detail ?? "弹幕文件上传失败，请检查文件格式");
      return result;
    },
    onSuccess: (result) => {
      setDanmakuPick(null);
      setDanmakuNote(`已附加 ${result.count ?? 0} 条弹幕，开始任务时会一起导入`);
      setError(null);
      void refreshAutomation();
    },
    onError: (err: Error) => { setDanmakuNote(null); setError(err.message); },
  });
  const startUpload = useMutation({
    mutationFn: async (file: File) => {
      const params = new URLSearchParams();
      if (config) params.set("config", JSON.stringify(config));
      params.set("title", file.name.replace(/\.[^.]+$/, ""));
      const response = await fetch(`/companion-api/automation/tasks/upload?${params}`, {
        method: "POST", headers: { "x-filename": encodeURIComponent(file.name) }, body: file,
      });
      const result: AutomationTask & { detail?: string } = await response.json();
      if (!response.ok) throw new Error(result.detail ?? "视频上传失败，请检查文件与磁盘空间");
      return result;
    },
    onSuccess: (created) => {
      setError(null);
      if (danmakuPick) attachDanmaku.mutate({ taskId: created.id, file: danmakuPick });
      void refreshAutomation();
    },
    onError: (err: Error) => setError(err.message),
  });

  const rooms = recorder.data?.rooms ?? [];
  const recordings = recorder.data?.recordings ?? [];
  const tasks = automation.data?.tasks ?? [];
  const templates = automation.data?.templates ?? [];
  const busy = startUrl.isPending || startUpload.isPending || attachDanmaku.isPending;
  const previewStyle = config?.style_template ? styleStore.data?.templates?.[config.style_template] ?? styleStore.data?.current : styleStore.data?.current;
  const previewShapes = config?.shapes_template ? styleStore.data?.shapes_templates?.[config.shapes_template] ?? [] : styleStore.data?.shapes ?? [];

  const pickTemplate = (next: string) => {
    setTemplateId(next);
    if (!next) {
      if (automation.data) setConfig(automation.data.default_config);
      return;
    }
    const template = templates.find(item => item.id === next);
    if (template) setConfig(template.config);
  };
  const patch = (changes: Partial<AutomationConfig>) => {
    setConfig(current => (current ? { ...current, ...changes } : current));
  };
  const submitRoom = (event: FormEvent) => {
    event.preventDefault();
    if (!roomInput.trim()) return;
    addRoom.mutate({ room: roomInput.trim(), name: roomName.trim() });
  };
  const pickFile = (file: File | null) => {
    if (!file) return;
    if (config && config.generate_clips && automation.data && !automation.data.api_key_ready) {
      setError("自动切片需要先保存 DeepSeek API Key");
      return;
    }
    startUpload.mutate(file);
    if (upload.current) upload.current.value = "";
  };
  const pickDanmaku = (file: File | null) => {
    if (!file) return;
    setError(null);
    setDanmakuPick(file);
    // 已有待开始的本地视频任务时直接挂上去，否则留给下一次上传视频一起附加
    const draft = tasks.find(item => item.kind === "upload" && item.state === "draft");
    if (draft) {
      setDanmakuNote(`正在附加 ${file.name}…`);
      attachDanmaku.mutate({ taskId: draft.id, file });
    } else {
      setDanmakuNote(`已选择 ${file.name}，下次上传本地视频时会一并附加`);
    }
    if (danmakuInput.current) danmakuInput.current.value = "";
  };

  return (
    <div className="automation-panel automation-panel--page">
      {error && <div className="companion-error" role="alert">{error}</div>}
      {(recorder.isError || automation.isError) && !error && <div className="companion-error" role="alert">本地服务连接中断，正在重试。</div>}

      <section className="automation-block" aria-label="直播间列表">
        <div className="automation-head">
          <h3>直播间列表</h3>
          <span className="automation-note">开播自动录制，同时保留 XML 弹幕与 SC</span>
        </div>
        {recorder.data && (
          editingPath ? (
            <div className="automation-path-edit">
              <input className="ny-input" value={pathInput} onChange={event => setPathInput(event.target.value)} placeholder={recorder.data.default_record_path} aria-label="录播目录" />
              <button className="ny-button ny-button--primary" type="button" disabled={savePath.isPending} onClick={() => savePath.mutate(pathInput.trim() || null)}>保存</button>
              <button className="ny-button" type="button" disabled={savePath.isPending} onClick={() => savePath.mutate(null)}>恢复默认</button>
              <button className="ny-button ny-button--quiet" type="button" disabled={savePath.isPending} onClick={() => setEditingPath(false)}>取消</button>
            </div>
          ) : (
            <div className="automation-path">
              <span className="automation-note" title={recorder.data.record_path}>录播目录：{recorder.data.record_path}</span>
              <button className="ny-button" type="button" disabled={openFolder.isPending} onClick={() => openFolder.mutate()}><FolderOpen size={13} />打开文件夹</button>
              <button className="ny-button" type="button" onClick={() => { setPathInput(recorder.data?.record_path ?? ""); setEditingPath(true); }}><FolderCog size={13} />更改路径</button>
            </div>
          )
        )}
        <form className="automation-inline" onSubmit={submitRoom}>
          <input className="ny-input" value={roomInput} onChange={event => setRoomInput(event.target.value)} placeholder="直播间号或 live.bilibili.com 链接" aria-label="直播间号或链接" />
          <input className="ny-input" value={roomName} onChange={event => setRoomName(event.target.value)} placeholder="备注名（可选）" aria-label="备注名" />
          <button className="ny-button" type="submit" disabled={!roomInput.trim() || addRoom.isPending}><Plus size={14} />添加</button>
        </form>
        {rooms.length === 0 ? <p className="automation-empty">还没有直播间。添加后每 20 秒检查一次开播状态。</p> : (
          <ul className="automation-rooms">
            {rooms.map(room => (
              <li className="automation-room" key={room.room_id}>
                <div className="automation-room-head">
                  <span className="automation-room-name">{room.name || room.uname || `直播间 ${room.room_id}`}</span>
                  <span className="automation-badges">
                    <span className={`automation-badge ${room.live_status === 1 ? "is-live" : ""}`}>
                      {room.live_status === 1 ? "直播中" : room.live_status === null ? "未知" : "未开播"}
                    </span>
                    <span className={`automation-badge ${room.recording ? "is-recording" : ""}`}>
                      {room.recording ? (room.stopping ? "收尾中" : "录制中") : "未录制"}
                    </span>
                  </span>
                </div>
                <div className="automation-room-meta">{room.room_id}{room.title ? ` · ${room.title}` : ""}</div>
                <div className="automation-room-actions">
                  <Toggle on={room.enabled} onChange={value => changeRoom.mutate({ room_id: room.room_id, patch: { enabled: value } })}>自动录制</Toggle>
                  <Toggle on={room.auto_run} onChange={value => changeRoom.mutate({ room_id: room.room_id, patch: { auto_run: value } })}>下播自动切片</Toggle>
                  {room.recording ? (
                    <button type="button" className="ny-button ny-button--danger" disabled={stopRecording.isPending || room.stopping} onClick={() => stopRecording.mutate(room.room_id)}><Square size={13} />{room.stopping ? "正在停止…" : "停止录制"}</button>
                  ) : (
                    <button type="button" className="ny-button" disabled={room.live_status !== 1 || !!recorder.data?.active || startRecording.isPending} onClick={() => startRecording.mutate(room.room_id)}><Play size={13} />开始录制</button>
                  )}
                  <button type="button" className="automation-icon" aria-label="删除直播间" disabled={dropRoom.isPending} onClick={() => dropRoom.mutate(room.room_id)}><Trash2 size={14} /></button>
                </div>
              </li>
            ))}
          </ul>
        )}
        <p className="automation-note">WebSocket 断线期间的弹幕无法补录；合并 XML 与录像存在 1–2 秒基准误差。</p>
        {recordings.length > 0 && (
          <details className="automation-recordings">
            <summary>录制历史（{recordings.length}）</summary>
            <ul>
              {recordings.slice(0, 8).map(item => (
                <li key={item.directory}>
                  <span className="automation-recording-name">{item.name || item.room_id}</span>
                  <span className="automation-recording-meta">{stamp(item.started_at)} · {time(item.duration)} · 弹幕 {item.danmaku_xml?.count ?? item.danmaku_count}</span>
                  <span className={`automation-badge ${item.merged ? "is-live" : "is-failed"}`}>{item.merged ? "已合并" : item.state}</span>
                </li>
              ))}
            </ul>
          </details>
        )}
      </section>

      <section className="automation-block" aria-label="自动任务设置">
        <div className="automation-head"><h3>自动任务设置</h3></div>
        <div className="automation-template">
          <select className="ny-input" value={templateId} onChange={event => pickTemplate(event.target.value)} aria-label="自动化模板">
            <option value="">默认模板</option>
            {templates.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}
          </select>
          <input className="ny-input" value={templateName} onChange={event => setTemplateName(event.target.value)} placeholder="模板名称" aria-label="模板名称" />
          <button className="ny-button" type="button" disabled={!templateName.trim() || !config || saveTemplate.isPending}
            onClick={() => config && saveTemplate.mutate({ name: templateName.trim(), config })}>保存模板</button>
        </div>
        {config ? (
          <div className="automation-config">
            <label>语种<select value={config.language} onChange={event => patch({ language: event.target.value })}>
              {LANGUAGES.map(item => <option key={item.id} value={item.id}>{item.label}</option>)}
            </select></label>
            <label>字幕版本<select value={config.variant} onChange={event => patch({ variant: event.target.value as AutomationConfig["variant"] })}>
              <option value="bilingual">双语</option>
              <option value="zh">中文</option>
              <option value="original">原文</option>
            </select></label>
            <div className="automation-select">
              <Toggle on={config.use_top_n} onChange={value => patch({ use_top_n: value })}>按评分 Top N</Toggle>
              {config.use_top_n && <input className="ny-input" type="number" min={1} max={50} value={config.top_n} aria-label="Top N" onChange={event => patch({ top_n: Number(event.target.value) || 1 })} />}
              <Toggle on={config.use_min_score} onChange={value => patch({ use_min_score: value })}>最低分不低于</Toggle>
              {config.use_min_score && <input className="ny-input" type="number" min={0} max={100} value={config.min_score} aria-label="最低分" onChange={event => patch({ min_score: Number(event.target.value) || 0 })} />}
            </div>
            <div className="automation-density">
              每
              <input className="ny-input" type="number" min={1} max={1440} value={config.per_minutes} aria-label="切片密度分钟数" onChange={event => patch({ per_minutes: Number(event.target.value) || 1 })} />
              分钟视频最多
              <input className="ny-input" type="number" min={1} max={20} value={config.per_count} aria-label="切片密度数量" onChange={event => patch({ per_count: Number(event.target.value) || 1 })} />
              个切片
            </div>
            <div className="automation-toggles">
              <label className="automation-publish">投稿数量<input className="ny-input" type="number" min={1} max={100} placeholder="全部" value={config.publish_count ?? ""} onChange={event => patch({ publish_count: event.target.value ? Number(event.target.value) : null })} /></label>
              <Toggle on={config.translate} onChange={value => patch({ translate: value })}>翻译</Toggle>
              <Toggle on={config.generate_clips} onChange={value => patch({ generate_clips: value })}>生成切片视频</Toggle>
              <Toggle on={config.auto_publish} onChange={value => patch({ auto_publish: value })}>自动投稿</Toggle>
            </div>
            <div className="automation-density automation-danmaku">
              <Toggle on={config.danmaku_enabled} onChange={value => patch({ danmaku_enabled: value })}>切片弹幕</Toggle>
              <span>字号</span>
              <input className="ny-input" type="number" min={12} max={96} value={config.danmaku_font_size}
                aria-label="弹幕字号" disabled={!config.danmaku_enabled}
                onChange={event => patch({ danmaku_font_size: Math.max(12, Math.min(96, Number(event.target.value) || 40)) })} />
              <span>区域高度</span>
              <input className="ny-input" type="number" min={10} max={100} value={config.danmaku_area_height}
                aria-label="弹幕区域高度百分比" disabled={!config.danmaku_enabled}
                onChange={event => patch({ danmaku_area_height: Math.max(10, Math.min(100, Number(event.target.value) || 60)) })} />%
            </div>
          </div>
        ) : <p className="automation-empty">正在读取自动化配置…</p>}
        <div className="automation-quick">
          <div className="automation-uploads">
            <button className="ny-button" type="button" disabled={busy} onClick={() => upload.current?.click()}>
              {startUpload.isPending ? <Loader2 size={14} className="automation-spin" /> : <Upload size={14} />}上传本地视频
            </button>
            <input ref={upload} type="file" accept="video/*,.mkv,.flv,.ts" hidden onChange={event => pickFile(event.target.files?.[0] ?? null)} />
            <button className="ny-button" type="button" disabled={attachDanmaku.isPending} onClick={() => danmakuInput.current?.click()}>
              {attachDanmaku.isPending ? <Loader2 size={14} className="automation-spin" /> : <FileText size={14} />}上传弹幕
            </button>
            <input ref={danmakuInput} type="file" accept=".xml,.json,application/xml,application/json" hidden onChange={event => pickDanmaku(event.target.files?.[0] ?? null)} />
          </div>
          <div className="automation-url">
            <input className="ny-input" value={url} onChange={event => setUrl(event.target.value)} placeholder="粘贴 B站视频链接" aria-label="视频链接" />
            <button className="ny-button" type="button" disabled={!url.trim() || busy} onClick={() => startUrl.mutate()}>
              {startUrl.isPending ? <Loader2 size={14} className="automation-spin" /> : <Link2 size={14} />}开始自动化
            </button>
          </div>
        </div>
        {danmakuNote && <p className="automation-note">{danmakuNote}</p>}
        <p className="automation-note">导入 → 转写 → 翻译（可选）→ LLM 切片分析 → 生成切片 → 加入投稿队列。</p>
        {config ? (
          <>
            <div className="automation-templates">
              <label>字幕模板<select value={config.style_template} onChange={event => patch({ style_template: event.target.value })}>
                <option value="">当前样式</option>
                {Object.keys(styleStore.data?.templates ?? {}).map(name => <option key={name} value={name}>{name}</option>)}
              </select></label>
              <label>图形模板<select value={config.shapes_template} onChange={event => patch({ shapes_template: event.target.value })}>
                <option value="">当前图形</option>
                {Object.keys(styleStore.data?.shapes_templates ?? {}).map(name => <option key={name} value={name}>{name}</option>)}
              </select></label>
            </div>
            {previewStyle ? (
              <div className="automation-preview" aria-label="字幕与图形样式预览">
                <video className="automation-preview-video" src="/companion-api/automation/preview-sample" autoPlay muted loop playsInline />
                {previewShapes.map((s, i) => (
                  <div key={i} className="automation-preview-shape" style={{
                    left: `${s.x - s.width / 2}%`, top: `${s.y - s.height / 2}%`, width: `${s.width}%`, height: `${s.height}%`,
                    background: `${s.fill_color}${Math.round(Math.max(0, Math.min(1, s.fill_opacity)) * 255).toString(16).padStart(2, "0")}`,
                    border: s.outline_width > 0 ? `${(s.outline_width / 1080) * 100}cqh solid ${s.outline_color}` : undefined,
                    borderRadius: s.radius > 0 ? `${(s.radius / 1080) * 100}cqh` : undefined,
                  }} />
                ))}
                {previewStyle.show_original !== false && <PreviewCue style={previewStyle.original} text="Sample subtitle 示例原文" />}
                {previewStyle.show_translated !== false && <PreviewCue style={previewStyle.translated} text="示例字幕：样式效果预览" />}
              </div>
            ) : <p className="automation-empty automation-preview-empty">样式加载中…</p>}
          </>
        ) : null}
      </section>

      <section className="automation-block" aria-label="自动任务列表">
        <div className="automation-head"><h3>自动任务列表</h3><span className="automation-note">{tasks.length} 个任务</span></div>
        {tasks.length === 0 ? <p className="automation-empty">还没有自动任务。上传视频、粘贴链接或等待录播结束。</p> : (
          <ul className="automation-tasks">
            {tasks.map(task => {
              const active = task.stages.find(stage => stage.state === "running");
              return (
                <li className={`automation-task is-${task.state}`} key={task.id}>
                  <div className="automation-task-head">
                    <span className="automation-task-title">{task.title}</span>
                    <span className={`automation-task-state is-${task.state}`}>{TASK_STATE[task.state] ?? task.state}</span>
                  </div>
                  <div className="automation-task-meta">{KIND_LABEL[task.kind] ?? task.kind} · {task.template_name || "默认模板"} · {stamp(task.created_at)}{task.selected.length ? ` · ${task.selected.length} 条切片` : ""}{task.danmaku_count ? ` · 弹幕 ${task.danmaku_count} 条` : ""}</div>
                  <ol className="automation-stages">
                    {task.stages.map(stage => (
                      <li key={stage.key} className={`automation-stage is-${stage.state}`} title={stage.error || stage.message || STAGE_STATE[stage.state]}>{stage.label}</li>
                    ))}
                  </ol>
                  {active?.message && <div className="automation-task-message">{active.message}</div>}
                  {task.error && <div className="companion-error" role="alert">{task.error}</div>}
                  <div className="automation-task-actions">
                    {task.state === "draft" && (
                      <button className="ny-button ny-button--primary" type="button" disabled={startTask.isPending} onClick={() => startTask.mutate(task.id)}>
                        <Play size={13} />开始
                      </button>
                    )}
                    <button className="ny-button" type="button" disabled={!task.started_at} onClick={() => onOpenJob(task.job_id)}>查看任务</button>
                    {task.state === "failed" && <button className="automation-icon" type="button" aria-label="重试任务" disabled={retryTask.isPending} onClick={() => retryTask.mutate(task.id)}><RotateCcw size={14} /></button>}
                    <button className="automation-icon" type="button" aria-label="删除任务" disabled={dropTask.isPending || task.state === "running"} onClick={() => dropTask.mutate(task.id)}><Trash2 size={14} /></button>
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </section>
    </div>
  );
}
