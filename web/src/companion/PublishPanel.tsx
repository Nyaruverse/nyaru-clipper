import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, QrCode, RefreshCw, Trash2, Upload } from "lucide-react";
import { api, coverUrl, fileUrl, time, type BiliLoginPoll, type BiliLoginQrCode, type Job, type JobPublishStore, type PublishDefaults, type PublishItem, type PublishStore, type PublishZones, type TopicClipStore, type TopicSegmentStore } from "./companionApi";

const publishStateLabel: Record<string, string> = {
  scheduled: "已排期", uploading: "投稿中", success: "已投稿", failed: "失败",
};

const itemStateLabel = (item: PublishItem) =>
  item.state === "success" && item.delivery === "dtime" ? "已上传·B站定时发布"
    : item.state === "uploading" && item.delivery === "dtime" ? "上传中（B站定时）"
      : publishStateLabel[item.state] ?? item.state;

/** 扫码登录的临时状态：仅保存在当前标签页，刷新后 170 秒内可继续扫码 */
const LOGIN_STORAGE = "companion-publish-login";

/** 投稿：把已生成的切片视频交给 biliup 定时投到 B站；投稿信息跨切片复用 */
export function PublishPanel({ job }: { job?: Job }) {
  const queryClient = useQueryClient();
  const canPublish = !!job && job.state === "completed";
  const topicsKey = ["companion", "topics", job?.id] as const;
  const topics = useQuery({
    queryKey: topicsKey,
    queryFn: () => api<TopicSegmentStore>(`/jobs/${job!.id}/topic-segments`),
    enabled: canPublish,
  });
  const clipsKey = ["companion", "topic-clips", job?.id] as const;
  const clips = useQuery({
    queryKey: clipsKey,
    queryFn: () => api<TopicClipStore>(`/jobs/${job!.id}/topic-clips`),
    enabled: !!job,
    refetchInterval: query => query.state.data?.state === "running" ? 1000 : false,
  });
  const clipStore = clips.data;
  const [selected, setSelected] = useState<number[]>([]);

  const publishKey = ["companion", "publish"] as const;
  const publishStatus = useQuery({
    queryKey: publishKey,
    queryFn: () => api<PublishStore>("/publish"),
    refetchInterval: query => (query.state.data?.items ?? [])
      .some(item => item.state === "scheduled" || item.state === "uploading") ? 5000 : false,
  });
  const pub = publishStatus.data;
  const publishItems = [...(pub?.items ?? [])].reverse();

  const defaultsKey = ["companion", "publish-defaults"] as const;
  const publishDefaults = useQuery({
    queryKey: defaultsKey, queryFn: () => api<PublishDefaults>("/publish/defaults"), staleTime: Infinity,
  });
  const zones = useQuery({
    queryKey: ["companion", "publish-zones"], queryFn: () => api<PublishZones>("/publish/zones"),
    staleTime: 6 * 3600_000, retry: false,
  });
  const zoneItems = zones.data?.items ?? [];
  const [tid, setTid] = useState("21");
  const [tags, setTags] = useState("");
  const [desc, setDesc] = useState("");
  const [dynamicText, setDynamicText] = useState("");
  useEffect(() => {
    const data = publishDefaults.data;
    if (!data) return;
    setTid(String(data.tid));
    setTags(data.tags);
    setDesc(data.desc);
    setDynamicText(data.dynamic);
  }, [publishDefaults.data]);
  const saveDefaults = useMutation({
    mutationFn: () => {
      const tidValue = Number(tid);
      if (!Number.isInteger(tidValue) || tidValue < 1 || tidValue > 10000) throw new Error("分区 ID 请填 1–10000 的整数");
      return api<PublishDefaults>("/publish/defaults", {
        tid: tidValue, tid_v2: null, tags, desc, dynamic: dynamicText, submit: "web", line: "",
      }, "PUT");
    },
    onSuccess: data => queryClient.setQueryData(defaultsKey, data),
  });

  const [loginOpen, setLoginOpen] = useState(false);
  const [qr, setQr] = useState<BiliLoginQrCode | null>(null);
  const [qrState, setQrState] = useState<BiliLoginPoll | null>(null);
  const [qrFetchedAt, setQrFetchedAt] = useState(0);
  const startLogin = useMutation({
    mutationFn: () => api<BiliLoginQrCode>("/publish/credential/qrcode", {}),
    onSuccess: data => {
      setQr(data); setQrState({ state: "waiting", message: "等待扫码" }); setQrFetchedAt(Date.now());
    },
  });
  const qrFinished = qrState?.state === "success" || qrState?.state === "expired";
  // 二维码有效期只有几分钟：刷新页面后在同一有效期内继续显示并轮询，避免刚扫到一半就消失
  useEffect(() => {
    try {
      const saved = JSON.parse(sessionStorage.getItem(LOGIN_STORAGE) || "null") as
        { qr?: BiliLoginQrCode; state?: BiliLoginPoll; at?: number } | null;
      if (!saved?.qr?.key || !saved.at) return;
      if (Date.now() > saved.at + (saved.qr.expires_in || 0) * 1000) {
        sessionStorage.removeItem(LOGIN_STORAGE);
        return;
      }
      setQr(saved.qr);
      setQrState(saved.state ?? { state: "waiting", message: "等待扫码" });
      setQrFetchedAt(saved.at);
      setLoginOpen(true);
    } catch {
      sessionStorage.removeItem(LOGIN_STORAGE);
    }
  }, []);
  useEffect(() => {
    try {
      if (loginOpen && qr && !qrFinished && qrFetchedAt) {
        sessionStorage.setItem(LOGIN_STORAGE, JSON.stringify({ qr, state: qrState, at: qrFetchedAt }));
      } else {
        sessionStorage.removeItem(LOGIN_STORAGE);
      }
    } catch {
      // 无痕模式等场景下 sessionStorage 不可用，忽略即可
    }
  }, [loginOpen, qr, qrState, qrFinished, qrFetchedAt]);
  // 投稿凭据走 TV 登录扫码：成功后同时拿到 access_token 与新的网页 Cookie
  useEffect(() => {
    if (!loginOpen || !qr || qrFinished) return;
    const timer = setInterval(async () => {
      try {
        const result = await api<BiliLoginPoll>(`/publish/credential/qrcode/${qr.key}`);
        setQrState(result);
        if (result.state === "success") {
          void queryClient.invalidateQueries({ queryKey: publishKey });
          void queryClient.invalidateQueries({ queryKey: ["companion", "bilibili-auth"] });
        }
      } catch (error) {
        setQrState({ state: "waiting", message: (error as Error).message });
      }
    }, 2000);
    return () => clearInterval(timer);
  }, [loginOpen, qr, qrFinished, queryClient]);

  const segments = topics.data?.segments ?? [];
  const segmentByIndex = new Map(segments.map(segment => [segment.index, segment]));
  const clipItems = clipStore?.state === "completed" || clipStore?.state === "failed" ? clipStore.items ?? [] : [];
  const completed = clipItems.filter(item => item.state === "completed" && item.file)
    .sort((a, b) => a.index - b.index);
  const availableKey = completed.map(item => item.index).join(",");
  // 切换任务或重新生成切片后，勾选失效，避免把旧编号投出去
  useEffect(() => setSelected([]), [job?.id]);
  useEffect(() => {
    const available = new Set(availableKey ? availableKey.split(",").map(Number) : []);
    setSelected(current => {
      const next = current.filter(index => available.has(index));
      return next.length === current.length ? current : next;
    });
  }, [availableKey]);

  const [publishCount, setPublishCount] = useState("");
  const [windowStart, setWindowStart] = useState("");
  const [windowEnd, setWindowEnd] = useState("");
  const publishNow = useMutation({
    mutationFn: () => {
      if (!selected.length) throw new Error("请先勾选要投稿的切片");
      const countText = publishCount.trim();
      const count = countText ? Number(countText) : selected.length;
      if (!Number.isInteger(count) || count < 1 || count > selected.length)
        throw new Error(`投稿数量请填 1–${selected.length} 的整数`);
      const payload: { indices: number[]; count: number; start_ts?: number; end_ts?: number } = { indices: selected, count };
      if (windowStart.trim() || windowEnd.trim()) {
        const startTs = Math.floor(new Date(windowStart).getTime() / 1000);
        const endTs = Math.floor(new Date(windowEnd).getTime() / 1000);
        if (!windowStart.trim() || !windowEnd.trim() || !Number.isFinite(startTs) || !Number.isFinite(endTs))
          throw new Error("请同时填写时间段的开始与结束");
        payload.start_ts = startTs;
        payload.end_ts = endTs;
      }
      return api<JobPublishStore>(`/jobs/${job!.id}/publish`, payload);
    },
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: publishKey }),
  });

  const removePublish = useMutation({
    mutationFn: (id: string) => api<PublishStore>(`/publish/${encodeURIComponent(id)}`, undefined, "DELETE"),
    onSuccess: data => queryClient.setQueryData(publishKey, data),
  });

  const toggle = (index: number) => {
    setSelected(prev => prev.includes(index) ? prev.filter(i => i !== index) : [...prev, index]);
  };
  const allSelected = completed.length > 0 && selected.length === completed.length;
  const countHint = publishCount.trim() ? Math.min(Number(publishCount) || 1, selected.length) : selected.length;

  return <section className="companion-panel companion-publish" aria-label="B站自动投稿">
    <div className="topic-bar-row">
      <span className="topic-bar-label">B站自动投稿</span>
      <span className="topic-bar-hint">{pub?.biliup_ready ? "投稿工具已就绪" : "未找到 biliup 可执行文件"}</span>
      <span className="topic-bar-spacer" />
      <span className="topic-bar-hint">{pub?.credential_ready ? "投稿凭据已生成" : "尚未生成投稿凭据"}</span>
    </div>
    <p className="companion-muted">分区、标签、简介、粉丝动态只填一次，之后所有切片沿用（等价于 B站投稿页的一键填写）；标题与封面随切片自动带入。</p>
    {!pub?.biliup_ready && <p className="companion-error" role="alert">缺少投稿工具：请把 biliup 解压到 ~/.nyaru-clipper/tools/biliup 或仓库 tools/biliup 目录，也可用环境变量 APP_BILIUP_PATH 指定路径。</p>}
    <div className="topic-publish">
      <div className="topic-publish-form">
        <label>分区<select className="ny-input" value={tid} onChange={event => setTid(event.target.value)}
          disabled={zones.isLoading}>
          {zones.isLoading && <option value={tid}>正在获取分区…</option>}
          {zoneItems.map(zone => <optgroup key={zone.id} label={zone.name}>
            {zone.children.map(child => <option key={`${zone.id}-${child.id}`} value={String(child.id)}>
              {zone.name} / {child.name}（{child.id}）
            </option>)}
          </optgroup>)}
          {!zones.isLoading && !zoneItems.some(zone => zone.children.some(child => String(child.id) === tid))
            && <option value={tid}>当前分区（{tid}）</option>}
        </select></label>
        <label>标签（逗号分隔）<input type="text" value={tags}
          onChange={event => setTags(event.target.value)} /></label>
        <label className="is-wide">简介（可用 {"{title}"} 带入标题）<textarea rows={2} value={desc}
          onChange={event => setDesc(event.target.value)} /></label>
        <label className="is-wide">粉丝动态<textarea rows={2} value={dynamicText}
          onChange={event => setDynamicText(event.target.value)} /></label>
      </div>
      <div className="topic-bar-row">
        <button className="ny-button" type="button" disabled={saveDefaults.isPending}
          onClick={() => saveDefaults.mutate()}>
          <Check size={15} />{saveDefaults.isPending ? "正在保存…" : "保存投稿信息"}
        </button>
        <button className="ny-button" type="button" disabled={startLogin.isPending}
          onClick={() => {
            setLoginOpen(open => !open);
            if (!qr || qrState?.state === "expired") startLogin.mutate();
          }}>
          <QrCode size={15} />{startLogin.isPending ? "正在获取二维码…" : "扫码获取投稿凭据"}
        </button>
        <span className="topic-bar-hint">只投自制（不转载）</span>
      </div>
      {saveDefaults.isError && <p className="companion-error" role="alert">{(saveDefaults.error as Error).message}</p>}
      {startLogin.isError && <p className="companion-error" role="alert">{(startLogin.error as Error).message}</p>}
      {zones.isError && <p className="companion-error" role="alert">分区列表获取失败，当前使用内置常用分区：{(zones.error as Error).message}</p>}
      {zones.data?.stale && !zones.isError && <p className="companion-footnote">分区列表来自本地缓存，联网后会自动更新。</p>}
      {loginOpen && <div className="topic-login">
        {qr
          ? <>
            <img className="topic-login-qr" src={qr.image} alt="B站投稿凭据二维码" />
            <div className="topic-login-body">
              <strong>用 B站手机客户端扫码，确认后生成投稿凭据</strong>
              <p className="companion-muted">投稿需要带 access_token 的凭据（data/bilibili-cookies.json），扫码后会一并刷新网页 Cookie，弹幕与投稿共用一次登录。</p>
              <p className={`topic-login-state is-${qrState?.state ?? "waiting"}`} role="status">
                {qrState?.state === "success" ? `投稿凭据已生成${qrState.name ? `：${qrState.name}` : ""}`
                  : qrState?.state === "expired" ? "二维码已过期，请刷新"
                    : qrState?.state === "scanned" ? "已扫码，请在手机上确认"
                      : qrState?.message || "等待扫码"}
              </p>
              <div className="topic-login-actions">
                <button className="ny-button" type="button" disabled={startLogin.isPending}
                  onClick={() => startLogin.mutate()}><RefreshCw size={14} />刷新二维码</button>
                <button className="topic-auth-link" type="button" onClick={() => setLoginOpen(false)}>收起</button>
              </div>
            </div>
          </>
          : <p className="companion-muted">正在获取二维码…</p>}
      </div>}
    </div>
    {!job && <p className="companion-muted">先在左侧任务记录里选择一个任务，再勾选要投稿的切片。</p>}
    {job && job.state !== "completed" && <p className="companion-muted">请等待任务完成后再投稿。</p>}
    {canPublish && <>
      <div className="topic-bar-row">
        <span className="topic-bar-label">选择切片</span>
        <span className="companion-muted">已选 {selected.length}/{completed.length} 条</span>
        <span className="topic-bar-spacer" />
        {completed.length > 1 && <button className="ny-button" type="button"
          onClick={() => setSelected(allSelected ? [] : completed.map(item => item.index))}>
          {allSelected ? "取消全选" : "全选"}
        </button>}
      </div>
      {completed.length
        ? <ul className="publish-picks">
          {completed.map(item => {
            const segment = segmentByIndex.get(item.index);
            const checked = selected.includes(item.index);
            const order = selected.indexOf(item.index) + 1;
            return <li key={item.index}>
              <button type="button" className={`publish-pick${checked ? " is-checked" : ""}`}
                aria-pressed={checked} onClick={() => toggle(item.index)}>
                <span className={`topic-check${checked ? " is-checked" : ""}`}>{checked && <Check size={12} />}</span>
                {segment?.cover && job && <img src={coverUrl(job.id, segment)} alt="" loading="lazy" />}
                <span className="publish-pick-title">{segment?.post_title || segment?.title || `切片 ${item.index + 1}`}</span>
                {segment && <span className="publish-pick-meta">{time(segment.start_seconds)}–{time(segment.end_seconds)}</span>}
                {checked && <span className="publish-pick-order">第 {order} 条</span>}
              </button>
            </li>;
          })}
        </ul>
        : <p className="companion-muted">还没有已完成的切片视频，请先到「内容切片」勾选并生成视频。</p>}
      <div className="topic-publish">
        <div className="topic-options">
          <label>投稿数量<input type="text" inputMode="numeric" className="topic-count" value={publishCount}
            placeholder={String(selected.length || 1)} onChange={event => setPublishCount(event.target.value)} /></label>
          <label>时间段开始<input type="datetime-local" value={windowStart}
            onChange={event => setWindowStart(event.target.value)} /></label>
          <label>时间段结束<input type="datetime-local" value={windowEnd}
            onChange={event => setWindowEnd(event.target.value)} /></label>
          <button className="ny-button ny-button--primary" type="button"
            disabled={publishNow.isPending || !selected.length || !pub?.biliup_ready}
            onClick={() => publishNow.mutate()}>
            <Upload size={15} />{publishNow.isPending ? "正在加入队列…" : `加入投稿队列（${countHint} 条）`}
          </button>
        </div>
        <p className="companion-footnote">提交后立即开始上传：第 1 条直接在 B站立即发布；其余顺延到 4 小时后交给 B站自带定时发布——未填时间段时每条间隔 2 小时，填了时间段则按（小时数 ÷ 投稿数量）±10 分钟排间隔。上传完成后即可关闭本程序。标题与封面随切片，其余信息复用上面的设置。</p>
        {publishNow.isError && <p className="companion-error" role="alert">{(publishNow.error as Error).message}</p>}
      </div>
    </>}
    <div className="topic-bar-row"><span className="topic-bar-label">投稿队列</span><span className="topic-bar-spacer" />
      <span className="topic-bar-hint">共 {publishItems.length} 条</span></div>
    {!publishItems.length && <p className="companion-muted">还没有排期中的投稿。</p>}
    {!!publishItems.length && <ul className="publish-queue">
      {publishItems.map(item => <li key={item.id} className={`publish-item is-${item.state}`}>
        <span className="publish-item-title" title={item.title}>{item.title}</span>
        <span className="publish-item-state" title={item.delivery === "dtime" ? "已交给 B站定时发布，无需保持本程序运行" : "上传后立即发布"}>
          {itemStateLabel(item)}</span>
        <span className="publish-item-time">{new Date(item.scheduled_at * 1000).toLocaleString("zh-CN", { hour12: false })}</span>
        {item.bvid && <a className="publish-item-link" href={`https://www.bilibili.com/video/${item.bvid}`}
          target="_blank" rel="noreferrer">{item.bvid}</a>}
        {item.error && <span className="publish-item-error" title={item.error}>{item.error}</span>}
        <button type="button" className="publish-item-del" title="从队列删除这条记录" aria-label="删除"
          disabled={item.state === "uploading" || (removePublish.isPending && removePublish.variables === item.id)}
          onClick={() => removePublish.mutate(item.id)}>
          <Trash2 size={13} />
        </button>
      </li>)}
    </ul>}
    {removePublish.isError && <p className="companion-error" role="alert">{(removePublish.error as Error).message}</p>}
    <p className="companion-footnote">到点后会调用 biliup 上传，成功后队列里会显示 BV 号；失败会保留原因，可重新生成切片后再投。凭据失效时重新扫码即可。</p>
  </section>;
}
