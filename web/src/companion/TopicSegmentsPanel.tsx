import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowDownToLine, Check, Film, ListTree } from "lucide-react";
import { api, fileUrl, time, parseTime, type Job, type TopicClipStore, type TopicSegmentStore } from "./companionApi";

type SubtitleMode = "bilingual" | "zh" | "original";

/** 内容切片与摘要：对已翻译字幕做语义话题切分，时间全部来自本地 SRT，点击时间可跳转预览 */
export function TopicSegmentsPanel({ job, onSeek }: { job?: Job; onSeek: (seconds: number) => void }) {
  const queryClient = useQueryClient();
  const canAnalyze = !!job && job.state === "completed" && job.translation?.state === "completed";
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
  // 切换任务或重新分析后，选择集合重置，避免编号错位
  useEffect(() => setSelected([]), [job?.id, store?.created_at]);
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
    onSuccess: data => queryClient.setQueryData(["companion", "topics", job!.id], data),
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
  const txtHref = job ? `/companion-api/jobs/${job.id}/topic-segments.txt` : "#";
  const variantOptions: { value: SubtitleMode; label: string }[] = [
    { value: "bilingual", label: "双语" }, { value: "zh", label: "仅译文" }, { value: "original", label: "仅原文" }];
  return <section className="companion-panel companion-topics" aria-label="内容切片与摘要">
    <div className="companion-section-heading">
      <div className="companion-panel-title"><h2><ListTree size={17} />内容切片与摘要</h2></div>
      {isCompleted && <span className="companion-muted">{store!.segments.length} 个切片 · {store!.total_cues} 条字幕
        {(store!.range_start != null || store!.range_end != null) && ` · 范围 ${time(store!.range_start ?? 0)}–${store!.range_end != null ? time(store!.range_end) : "结尾"}`}</span>}
    </div>
    <p className="companion-muted">基于翻译结果按话题语义自动切分，自动剔除片头片尾、唱歌音乐等环节，只保留杂谈聊天内容（单段约 30 秒–10 分钟，话题相关可合并更长）。时间来自本地字幕，点击时间跳转预览。勾选切片后可批量生成对应视频。</p>
    {!job && <p className="companion-muted">选择任务后可生成内容切片。</p>}
    {job && job.state !== "completed" && <p className="companion-muted">请等待视频任务完成后再生成内容切片。</p>}
    {job && job.state === "completed" && job.translation?.state !== "completed" && <p className="companion-muted">请先完成「日语 → 中文」双语字幕翻译，再生成内容切片。</p>}
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
      {generate.isPending && <p className="companion-footnote" role="status">DeepSeek 正在通读字幕并挑选杂谈段落，通常需要 10–60 秒，请勿重复点击。</p>}
      {(generate.isError || (store?.state === "failed")) && <p className="companion-error" role="alert">{generate.isError ? (generate.error as Error).message : store?.error ?? "语义分析失败，请重试"}</p>}
      {topics.isError && <p className="companion-error" role="alert">{(topics.error as Error)?.message ?? "切片结果读取失败"}</p>}
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
        <div className="topic-list">
          {store!.segments.map(segment => {
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
                  <h3>{segment.title}{!segment.analyzed && <span className="topic-badge">未分析</span>}</h3>
                  <button className="topic-time" type="button" title="跳转到该时间点预览"
                    onClick={event => { event.stopPropagation(); onSeek(segment.start_seconds); }}>
                    <time>{time(segment.start_seconds)}</time> — <time>{time(segment.end_seconds)}</time>
                  </button>
                </div>
                <span className="topic-meta">{segment.cue_count} 条 · {(segment.end_seconds - segment.start_seconds).toFixed(0)} 秒</span>
              </header>
              <p className="topic-summary">{segment.summary}</p>
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
