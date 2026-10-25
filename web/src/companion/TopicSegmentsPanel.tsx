import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowDownToLine, Check, Film, ListTree, LogOut, QrCode, RefreshCw, Upload } from "lucide-react";
import { api, fileUrl, time, parseTime, type BiliAuthStatus, type BiliLoginPoll, type BiliLoginQrCode, type DanmakuSummary, type Job, type TopicClipStore, type TopicSegmentStore } from "./companionApi";

type SubtitleMode = "bilingual" | "zh" | "original";

/** 内容切片与摘要：对已翻译字幕做语义话题切分，时间全部来自本地 SRT，点击时间可跳转预览 */
export function TopicSegmentsPanel({ job, onSeek }: { job?: Job; onSeek: (seconds: number) => void }) {
  const queryClient = useQueryClient();
  const canAnalyze = !!job && job.state === "completed";
  const hasTranslation = job?.translation?.state === "completed";
  const topics = useQuery({
    queryKey: ["companion", "topics", job?.id],
    queryFn: () => api<TopicSegmentStore>(`/jobs/${job!.id}/topic-segments`),
    enabled: canAnalyze,
  });
  const store = topics.data;
  const isCompleted = store?.state === "completed" && !!store.segments?.length;
  const clipsKey = ["companion", "topic-clips", job?.id] as const;
  const clips = useQuery({
    queryKey: clipsKey,
    queryFn: () => api<TopicClipStore>(`/jobs/${job!.id}/topic-clips`),
    enabled: !!job,
    refetchInterval: query => query.state.data?.state === "running" ? 1000 : false,
  });
  const clipStore = clips.data;
  const [selected, setSelected] = useState<number[]>([]);
  const [mode, setMode] = useState<"separate" | "combined">("separate");
  const [variant, setVariant] = useState<SubtitleMode>("bilingual");
  const [rangeStart, setRangeStart] = useState("");
  const [rangeEnd, setRangeEnd] = useState("");
  const [maxCount, setMaxCount] = useState("");
  const [sortBy, setSortBy] = useState<"time" | "score">("time");
  const [sourceUrl, setSourceUrl] = useState("");
  const fileInput = useRef<HTMLInputElement>(null);
  const danmakuKey = ["companion", "danmaku", job?.id] as const;
  const danmaku = useQuery({
    queryKey: danmakuKey,
    queryFn: () => api<DanmakuSummary>(`/jobs/${job!.id}/danmaku`),
    enabled: !!job,
  });
  // 自动拉取过的链接优先，其次用新建任务时保留的来源链接
  useEffect(() => { setSourceUrl(danmaku.data?.url ?? job?.url ?? ""); }, [job?.id, job?.url, danmaku.data?.url]);
  const authKey = ["companion", "bilibili-auth"] as const;
  const auth = useQuery({
    queryKey: authKey,
    queryFn: () => api<BiliAuthStatus>("/bilibili/auth"),
    staleTime: 30_000,
  });
  const [loginOpen, setLoginOpen] = useState(false);
  const [qr, setQr] = useState<BiliLoginQrCode | null>(null);
  const [qrState, setQrState] = useState<BiliLoginPoll | null>(null);
  const startLogin = useMutation({
    mutationFn: () => api<BiliLoginQrCode>("/bilibili/login/qrcode", {}),
    onSuccess: data => { setQr(data); setQrState({ state: "waiting", message: "等待扫码" }); },
  });
  const logout = useMutation({
    mutationFn: () => api<BiliAuthStatus>("/bilibili/auth", undefined, "DELETE"),
    onSuccess: data => {
      queryClient.setQueryData(authKey, data);
      setQr(null);
      setQrState(null);
      setLoginOpen(false);
    },
  });
  const fetchDanmaku = useMutation({
    mutationFn: () => api<{ count: number; source: string; title?: string; topics: TopicSegmentStore | null }>(
      `/jobs/${job!.id}/danmaku/fetch`, { url: sourceUrl.trim() }),
    onSuccess: data => {
      void queryClient.invalidateQueries({ queryKey: danmakuKey });
      if (data.topics) queryClient.setQueryData(["companion", "topics", job!.id], data.topics);
    },
  });
  const importDanmaku = useMutation({
    mutationFn: async (file: File) => {
      const response = await fetch(`/companion-api/jobs/${job!.id}/danmaku`,
        { method: "POST", body: file, headers: { "X-Filename": file.name } });
      const result: { count?: number; detail?: string; topics?: TopicSegmentStore | null } = await response.json();
      if (!response.ok) throw new Error(result.detail ?? "弹幕导入失败，请确认文件格式");
      return result as { count: number; topics: TopicSegmentStore | null };
    },
    onSuccess: data => {
      void queryClient.invalidateQueries({ queryKey: danmakuKey });
      if (data.topics) queryClient.setQueryData(["companion", "topics", job!.id], data.topics);
    },
  });
  // 扫码登录：每 2 秒轮询一次，成功后刷新登录态；仍填着链接时自动重新拉取弹幕
  const qrFinished = qrState?.state === "success" || qrState?.state === "expired";
  useEffect(() => {
    if (!loginOpen || !qr || qrFinished) return;
    const timer = setInterval(async () => {
      try {
        const result = await api<BiliLoginPoll>(`/bilibili/login/qrcode/${qr.key}`);
        setQrState(result);
        if (result.state === "success") {
          void queryClient.invalidateQueries({ queryKey: authKey });
          if (sourceUrl.trim()) fetchDanmaku.mutate();
        }
      } catch (error) {
        setQrState({ state: "waiting", message: (error as Error).message });
      }
    }, 2000);
    return () => clearInterval(timer);
  }, [loginOpen, qr, qrFinished, sourceUrl, queryClient, fetchDanmaku.mutate]);
  // 切换任务或重新分析后，选择集合重置，避免编号错位
  useEffect(() => setSelected([]), [job?.id, store?.created_at]);
  // 翻译不可用时字幕内容只能是原文
  useEffect(() => { if (!hasTranslation && variant !== "original") setVariant("original"); }, [hasTranslation, variant]);
  const generate = useMutation({
    mutationFn: () => {
      const payload: { start_seconds?: number; end_seconds?: number; max_segments?: number } = {};
      const startText = rangeStart.trim(), endText = rangeEnd.trim();
      if (startText) payload.start_seconds = parseTime(startText);
      if (endText) payload.end_seconds = parseTime(endText);
      if (payload.start_seconds !== undefined && payload.end_seconds !== undefined
          && payload.end_seconds <= payload.start_seconds) throw new Error("时间段结束必须大于开始");
      const countText = maxCount.trim();
      if (countText) {
        const count = Number(countText);
        if (!Number.isInteger(count) || count < 1 || count > 100) throw new Error("最大切片数量请填 1–100 的整数");
        payload.max_segments = count;
      }
      return api<TopicSegmentStore>(`/jobs/${job!.id}/topic-segments`, payload);
    },
    onSuccess: data => {
      queryClient.setQueryData(["companion", "topics", job!.id], data);
      // 生成切片时后端会按任务来源链接自动拉弹幕，这里同步刷新弹幕统计
      void queryClient.invalidateQueries({ queryKey: danmakuKey });
    },
  });
  const makeClips = useMutation({
    mutationFn: () => api<TopicClipStore>(`/jobs/${job!.id}/topic-clips`, { indices: selected, mode, variant }),
    onSuccess: data => queryClient.setQueryData(clipsKey, data),
  });
  const segmentCount = store?.segments?.length ?? 0;
  const allSelected = selected.length > 0 && selected.length === segmentCount;
  const running = makeClips.isPending || clipStore?.state === "running";
  const clipsStale = clipStore?.state === "stale";
  const clipItems = clipStore?.state === "completed" || clipStore?.state === "failed" ? clipStore.items ?? [] : [];
  const itemByIndex = new Map(clipItems.map(item => [item.index, item]));
  const combinedDone = clipStore?.state === "completed" && clipStore.combined?.state === "completed" && clipStore.combined.file;
  const progressPct = clipStore?.total ? Math.round(((clipStore.done ?? 0) / clipStore.total) * 100) : 0;
  const toggle = (index: number) => {
    if (running) return;
    // 保留点击选择顺序：组合视频按此顺序合并并编号
    setSelected(prev => prev.includes(index) ? prev.filter(i => i !== index) : [...prev, index]);
  };
  const segments = store?.segments ?? [];
  // 按评分排序时保持 index 稳定，切片编号与勾选顺序不受影响
  const sortedSegments = sortBy === "score"
    ? [...segments].sort((a, b) => (b.score ?? -1) - (a.score ?? -1) || a.index - b.index)
    : segments;
  const txtHref = job ? `/companion-api/jobs/${job.id}/topic-segments.txt` : "#";
  // 没有翻译字幕时只能烧录原文，双语/仅译文不可用
  const variantOptions: { value: SubtitleMode; label: string }[] = hasTranslation ? [
    { value: "bilingual", label: "双语" }, { value: "zh", label: "仅译文" }, { value: "original", label: "仅原文" }]
    : [{ value: "original", label: "仅原文" }];
  return <section className="companion-panel companion-topics" aria-label="内容切片与摘要">
    <div className="companion-section-heading">
      <div className="companion-panel-title"><h2><ListTree size={17} />内容切片与摘要</h2></div>
      {isCompleted && <span className="companion-muted">{store!.segments.length} 个切片 · {store!.total_cues} 条字幕
        {danmaku.data?.count ? ` · 弹幕 ${danmaku.data.count} 条` : ""}
        {(store!.range_start != null || store!.range_end != null) && ` · 范围 ${time(store!.range_start ?? 0)}–${store!.range_end != null ? time(store!.range_end) : "结尾"}`}</span>}
    </div>
    <p className="companion-muted">按话题语义自动切分：有翻译时用双语字幕，没有翻译时直接用原文。自动剔除片头片尾、唱歌音乐等环节，只保留杂谈聊天内容（单段约 30 秒–10 分钟，话题相关可合并更长）。时间来自本地字幕，点击时间跳转预览。勾选切片后可批量生成对应视频。</p>
    <p className="companion-footnote">评分综合弹幕密度、参与人数、刷屏共鸣、说话密度，并叠加响度峰值、笑声/尖叫、热词命中与弹幕峰值形态。热词和可当标题的金句由每次分析时从高分切片的弹幕与字幕中自动提取，并按主播累积画像；静态梗词表已移除，只保留需要人工维护的合规风险词（命中会扣分并标「风险」）。</p>
    {!job && <p className="companion-muted">选择任务后可生成内容切片。</p>}
    {job && job.state !== "completed" && <p className="companion-muted">请等待视频任务完成后再生成内容切片。</p>}
    {job && job.state === "completed" && !hasTranslation && <p className="companion-muted">当前任务没有翻译字幕，将直接基于原文切分；若主播需要翻译，完成翻译后重新生成即可自动切换为双语切片。</p>}
    {canAnalyze && <>
      <div className="topic-options">
        <label>分析开始<input type="text" value={rangeStart} disabled={generate.isPending}
          placeholder="留空为开头" onChange={event => setRangeStart(event.target.value)} /></label>
        <label>分析结束<input type="text" value={rangeEnd} disabled={generate.isPending}
          placeholder="留空为结尾" onChange={event => setRangeEnd(event.target.value)} /></label>
        <label>最大切片数<input type="text" inputMode="numeric" className="topic-count" value={maxCount}
          disabled={generate.isPending} placeholder="100" onChange={event => setMaxCount(event.target.value)} /></label>
        <span className="topic-options-hint">时间填秒数、MM:SS 或 HH:MM:SS；留空则分析全部、最多 100 段</span>
      </div>
      <div className="topic-actions">
        <button className="ny-button ny-button--primary" type="button" disabled={generate.isPending}
          onClick={() => generate.mutate()}>
          <ListTree size={15} />{generate.isPending ? "正在分析内容…" : store?.state === "completed" || store?.state === "stale" ? "重新生成内容切片" : "生成内容切片"}
        </button>
        {isCompleted && <a className="ny-button" href={txtHref}><ArrowDownToLine size={15} />导出切片清单 TXT</a>}
      </div>
      <div className="topic-danmaku">
        <label>B站弹幕源<input type="text" value={sourceUrl} disabled={fetchDanmaku.isPending}
          placeholder="BV号或视频链接" onChange={event => setSourceUrl(event.target.value)} /></label>
        <button className="ny-button" type="button" disabled={fetchDanmaku.isPending || !sourceUrl.trim()}
          onClick={() => fetchDanmaku.mutate()}>
          <RefreshCw size={15} />{fetchDanmaku.isPending ? "正在拉取弹幕…" : "自动拉取弹幕"}
        </button>
        <button className="ny-button" type="button" disabled={importDanmaku.isPending}
          onClick={() => fileInput.current?.click()}>
          <Upload size={15} />{importDanmaku.isPending ? "正在导入弹幕…"
            : danmaku.data?.count ? `重新导入弹幕（${danmaku.data.count} 条）` : "导入弹幕（ASS/XML）"}
        </button>
        <input ref={fileInput} type="file" accept=".ass,.xml,.txt" hidden
          onChange={event => {
            const file = event.target.files?.[0];
            event.target.value = "";
            if (file) importDanmaku.mutate(file);
          }} />
        {auth.data?.logged_in
          ? <span className="topic-auth-state">已登录：{auth.data.name ?? "B站账号"}
            <button type="button" className="topic-auth-link" disabled={logout.isPending}
              onClick={() => logout.mutate()}><LogOut size={12} />退出</button></span>
          : <button className="ny-button" type="button" disabled={startLogin.isPending}
            onClick={() => {
              setLoginOpen(open => !open);
              if (!qr || qrState?.state === "expired") startLogin.mutate();
            }}>
            <QrCode size={15} />{startLogin.isPending ? "正在获取二维码…" : "扫码登录 B站"}
          </button>}
      </div>
      {loginOpen && !auth.data?.logged_in && <div className="topic-login">
        {qr
          ? <>
            <img className="topic-login-qr" src={qr.image} alt="B站登录二维码" />
            <div className="topic-login-body">
              <strong>用 B站手机客户端扫码并确认登录</strong>
              <p className="companion-muted">登录后自动拉取弹幕可拿到完整历史弹幕（长回放不再只返回最新约 1 万条）。Cookie 只保存在本地 data/bilibili-cookies.txt。</p>
              <p className={`topic-login-state is-${qrState?.state ?? "waiting"}`} role="status">
                {qrState?.state === "success" ? `登录成功${qrState.name ? `：${qrState.name}` : ""}，正在重新拉取弹幕`
                  : qrState?.state === "expired" ? "二维码已过期，请刷新"
                    : qrState?.state === "scanned" ? "已扫码，请在手机上确认登录"
                      : qrState?.message || "等待扫码"}
              </p>
              <div className="topic-login-actions">
                <button className="ny-button" type="button" disabled={startLogin.isPending}
                  onClick={() => startLogin.mutate()}><RefreshCw size={14} />刷新二维码</button>
                <button className="topic-auth-link" type="button" onClick={() => setLoginOpen(false)}>收起</button>
              </div>
            </div>
          </>
          : <p className="companion-muted">{startLogin.isError ? (startLogin.error as Error).message : "正在获取二维码…"}</p>}
      </div>}
      <p className="companion-footnote">自动拉取走 B站稿件弹幕接口；匿名访问时弹幕池有上限（长回放可能只返回最新约 1 万条），点「扫码登录 B站」后再拉取即可拿到完整历史弹幕。也可以用环境变量 APP_BILIBILI_COOKIE_PATH 指向自备的 cookies.txt。首次生成切片会解码音轨，长视频约需数十秒，失败会自动跳过。风险词可用数据目录的 clip_words.json 覆盖。</p>
      {generate.isPending && <p className="companion-footnote" role="status">DeepSeek 正在通读字幕并挑选杂谈段落，通常需要 10–60 秒，请勿重复点击。</p>}
      {(generate.isError || (store?.state === "failed")) && <p className="companion-error" role="alert">{generate.isError ? (generate.error as Error).message : store?.error ?? "语义分析失败，请重试"}</p>}
      {fetchDanmaku.isError && <p className="companion-error" role="alert">{(fetchDanmaku.error as Error).message}</p>}
      {topics.isError && <p className="companion-error" role="alert">{(topics.error as Error)?.message ?? "切片结果读取失败"}</p>}
      {importDanmaku.isError && <p className="companion-error" role="alert">{(importDanmaku.error as Error).message}</p>}
      {store?.state === "stale" && <p className="companion-error" role="alert">字幕内容已更新，当前切片结果已过期，请重新生成。</p>}
      {store?.state === "completed" && !store.segments?.length && <p className="companion-muted">分析完成，但未在该范围内发现值得切片的杂谈聊天内容；可调整时间段后重试。</p>}
      {isCompleted && <>
        {store!.truncated && <p className="companion-error" role="alert">分析范围内字幕共 {store!.total_cues} 条，仅分析了前 {store!.covered_cues} 条；最后一段为未分析的后续内容，可用「分析开始/结束」缩小范围后再生成。</p>}
        <div className="topic-video-bar">
          <div className="topic-bar-row">
            <button type="button" className="topic-select-all" disabled={running}
              onClick={() => setSelected(allSelected ? [] : store!.segments.map(s => s.index))}>
              <span className={`topic-check${allSelected ? " is-checked" : ""}`}>{allSelected && <Check size={12} />}</span>
              {allSelected ? "取消全选" : "全选"}
            </button>
            <span className="companion-muted">已选 {selected.length}/{segmentCount} 段</span>
            <span className="topic-bar-spacer" />
            <span className="topic-bar-label">字幕内容</span>
            <span className="topic-seg">
              {variantOptions.map(option => <button key={option.value} type="button"
                className={variant === option.value ? "is-active" : ""} disabled={running}
                onClick={() => setVariant(option.value)}>{option.label}</button>)}
            </span>
          </div>
          <div className="topic-bar-row">
            <span className="topic-bar-label">生成模式</span>
            <span className="topic-seg">
              <button type="button" className={mode === "separate" ? "is-active" : ""} disabled={running}
                onClick={() => setMode("separate")}>分别生成</button>
              <button type="button" className={mode === "combined" ? "is-active" : ""} disabled={running}
                onClick={() => setMode("combined")}>组合生成</button>
            </span>
            <span className="topic-bar-hint">{mode === "separate"
              ? "每个切片输出独立视频，并烧录对应时间段字幕"
              : "按勾选先后顺序合并为一个视频，每段开头标注勾选顺序编号"}</span>
          </div>
          <div className="topic-bar-row">
            <button type="button" className="ny-button ny-button--primary"
              disabled={running || selected.length === 0}
              onClick={() => makeClips.mutate()}>
              <Film size={15} />{running ? "正在生成视频…" : `生成${mode === "combined" ? "组合" : "切片"}视频（${selected.length} 段）`}
            </button>
          </div>
          {running && <>
            <div className="topic-progress" role="progressbar" aria-valuenow={progressPct} aria-valuemin={0} aria-valuemax={100}>
              <span style={{ width: `${progressPct}%` }} />
            </div>
            <p className="companion-footnote" role="status">{makeClips.isPending ? "正在提交生成任务…" : (clipStore?.message ?? "正在生成…")}</p>
          </>}
          {makeClips.isError && <p className="companion-error" role="alert">{(makeClips.error as Error).message}</p>}
          {clipStore?.state === "failed" && <p className="companion-error" role="alert">{clipStore.error ?? "部分切片生成失败，请重试或单独重新生成"}</p>}
          {clipsStale && <p className="companion-error" role="alert">内容切片已重新分析，旧视频结果已过期，请重新选择并生成。</p>}
          {combinedDone && job && <div className="topic-combined-product">
            <video controls preload="none" src={fileUrl(job.id, clipStore.combined!.file!)} />
            <a className="ny-button ny-button--primary" href={fileUrl(job.id, clipStore.combined!.file!, true)}>
              <ArrowDownToLine size={15} />下载组合视频（{clipStore.total} 段）</a>
          </div>}
        </div>
        <div className="topic-sort-row">
          <span className="topic-bar-label">列表排序</span>
          <span className="topic-seg">
            <button type="button" className={sortBy === "time" ? "is-active" : ""}
              onClick={() => setSortBy("time")}>按时间</button>
            <button type="button" className={sortBy === "score" ? "is-active" : ""} disabled={!danmaku.data?.count}
              title={danmaku.data?.count ? "按弹幕热度从高到低" : "导入弹幕后可用"} onClick={() => setSortBy("score")}>按评分</button>
          </span>
          {!danmaku.data?.count && <span className="topic-bar-hint">导入弹幕后可为每个切片打互动评分</span>}
        </div>
        {(!!store!.vocabulary?.length || !!store!.quotes?.length || !!store!.streamer) && <div className="topic-vocab">
          <div className="topic-vocab-row">
            <span className="topic-bar-label">本场热词</span>
            {store!.streamer && <span className="topic-bar-hint">主播画像：{store!.streamer}</span>}
            <span className="topic-bar-spacer" />
            <span className="topic-bar-hint">从高分切片的弹幕里提取，按主播累积复用</span>
          </div>
          {store!.vocabulary?.length
            ? <div className="topic-vocab-tags">
              {store!.vocabulary.map(term => <span className="topic-vocab-tag" key={term}>{term}</span>)}
            </div>
            : <p className="topic-bar-hint">本场暂未提取到有区分度的热词（弹幕需在高分切片里更集中地出现）。</p>}
          {!!store!.quotes?.length && <>
            <div className="topic-vocab-row">
              <span className="topic-bar-label">高点时刻金句</span>
              <span className="topic-bar-hint">弹幕峰值对齐字幕，可当标题或开头钩子</span>
            </div>
            <div className="topic-quotes">
              {store!.quotes.map(quote => <button type="button" className="topic-quote" key={`${quote.start}-${quote.text}`}
                title={quote.start != null ? "跳转到该时间点预览" : undefined}
                onClick={() => quote.start != null && onSeek(quote.start)}>
                <span className="topic-quote-text">{quote.text}</span>
                {quote.start != null && <time>{time(quote.start)}</time>}
              </button>)}
            </div>
          </>}
        </div>}
        <div className="topic-list">
          {sortedSegments.map(segment => {
            const item = itemByIndex.get(segment.index);
            const checked = selected.includes(segment.index);
            return <article className={`topic-card${segment.analyzed ? "" : " topic-card--muted"}${checked ? " topic-card--selected" : ""}`}
              key={segment.index} onClick={() => toggle(segment.index)} role="checkbox" aria-checked={checked} tabIndex={0}
              onKeyDown={event => { if (event.key === " " || event.key === "Enter") { event.preventDefault(); toggle(segment.index); } }}>
              <header>
                <span className={`topic-check topic-check--card${checked ? " is-checked" : ""}`}>{checked
                  ? String(selected.indexOf(segment.index) + 1).padStart(2, "0")
                  : String(segment.index + 1).padStart(2, "0")}</span>
                <div className="topic-heading">
                  <h3>{segment.title}{!segment.analyzed && <span className="topic-badge">未分析</span>}
                    {segment.score != null && <span className={`topic-score topic-score--${segment.score >= 70 ? "high" : segment.score >= 40 ? "mid" : "low"}`}
                      title={`弹幕 ${segment.dm_count ?? 0} 条 · ${segment.dm_rate ?? 0} 条/秒 · ${segment.dm_users ?? 0} 人参与`
                        + (segment.dm_peak_time != null ? ` · 10 秒峰值 ${segment.dm_peak ?? 0} 条（${time(segment.dm_peak_time)}）` : "")
                        + (segment.dm_shape ? ` · 形态 ${segment.dm_shape}` : "")
                        + (segment.loudness_db != null ? ` · 响度 ${segment.loudness_db} dB` : "")
                        + (segment.laugh_rate != null ? ` · 笑声 ${segment.laugh_rate}/分` : "")
                        + (segment.meme_hits != null ? ` · 热词命中 ${segment.meme_hits} 次${segment.hot_words?.length ? `（${segment.hot_words.join("、")}）` : ""}` : "")}>
                      {segment.score} 分 · {segment.grade}</span>}
                    {segment.risk && <span className="topic-risk"
                      title={`命中风险词：${(segment.risk_terms ?? []).join("、") || "敏感内容"}`}>风险</span>}
                  </h3>
                  <button className="topic-time" type="button" title="跳转到该时间点预览"
                    onClick={event => { event.stopPropagation(); onSeek(segment.start_seconds); }}>
                    <time>{time(segment.start_seconds)}</time> — <time>{time(segment.end_seconds)}</time>
                  </button>
                </div>
                <span className="topic-meta">{segment.cue_count} 条 · {(segment.end_seconds - segment.start_seconds).toFixed(0)} 秒
                  {segment.dm_count != null && <> · 弹幕 {segment.dm_count}</>}</span>
              </header>
              <p className="topic-summary">{segment.summary}</p>
              {!!segment.hot_words?.length && <div className="topic-hotwords" onClick={event => event.stopPropagation()}>
                {segment.hot_words.map(term => <span className="topic-hotword" key={term}>{term}</span>)}
              </div>}
              <details className="topic-preview" onClick={event => event.stopPropagation()}>
                <summary>内容片段</summary>
                <p>{segment.preview}</p>
              </details>
              {item?.state === "completed" && item.file && job && <div className="topic-product" onClick={event => event.stopPropagation()}>
                <video controls preload="none" src={fileUrl(job.id, item.file)} />
                <a className="ny-button" href={fileUrl(job.id, item.file, true)}><ArrowDownToLine size={14} />下载 {item.file}</a>
              </div>}
              {item?.state === "failed" && <p className="companion-error" role="alert">该切片生成失败：{item.error}</p>}
            </article>;
          })}
        </div>
        <p className="companion-footnote">生成时间：{new Date(store!.created_at * 1000).toLocaleString("zh-CN")} · 视频时间与字幕均来自本地文件，切片帧级对齐；重新翻译或重新分析后视频结果需重新生成。</p>
      </>}
    </>}
  </section>;
}
