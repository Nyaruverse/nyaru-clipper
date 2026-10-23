import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";

import { AppRouter } from "../router";
import { EventStream } from "../workstation/api/__tests__/eventTransportHarness";
import type { WorkstationTaskOverview } from "../workstation/features/task-overview/api";

const overview: WorkstationTaskOverview = {
  archived_at: null, artifact_readiness: [], artifacts: [], created_at: "2026-10-21T00:00:00Z",
  current_stage: "asr", highlight_filtering_enabled: false, pipeline_run_id: "run-route",
  execution_progress: {
    current_phase: "transcribe", heartbeat_at: "2026-10-21T00:01:00Z", latest_message: "route ASR progress",
    phase_count: 5, phase_index: 3, phase_started_at: "2026-10-21T00:00:00Z", phases: [], stage_name: "asr",
  },
  progress_percent: 40, recovery_actions: [], safe_logs: [], source_kind: "bilibili",
  source_label: "路由测试录播", status: "running", storage_bytes: 0, tags: [], task_id: "task-route",
  title: "路由测试任务", updated_at: "2026-10-21T00:01:00Z",
  stages: [{ attempts: 1, failure_code: null, finished_at: null, name: "asr", planned: false, started_at: "2026-10-21T00:00:00Z", status: "running", summary: "阶段摘要" }],
};

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { headers: { "Content-Type": "application/json" }, status });
}

function libraryResponse(request: Request): Response {
  const pathname = new URL(request.url).pathname;
  if (pathname === "/api/v2/tasks/summary") return json({ active: 0, archived: 0, queued: 0, failed: 0, review_required: 0, storage_bytes: 0 });
  if (pathname === "/api/v2/tasks") return json({ items: [], page: 1, page_count: 1, page_size: 50, total: 0 });
  return json({ detail: "Unexpected fixture request" }, 500);
}

function renderRoute(path: string): void {
  window.history.replaceState({}, "", path);
  vi.stubGlobal("EventSource", EventStream);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  render(<QueryClientProvider client={client}><AppRouter /></QueryClientProvider>);
}

describe("real application router smoke", () => {
  afterEach(() => {
    cleanup();
    EventStream.instances = [];
    vi.unstubAllGlobals();
    window.history.replaceState({}, "", "/");
  });

  it.each(["/", "/workstation"])("opens the current library at %s", async (path) => {
    // Given: an empty current task library.
    vi.stubGlobal("fetch", async (input: RequestInfo | URL) => libraryResponse(new Request(input)));
    // When: the actual application entry mounts.
    renderRoute(path);
    // Then: the current shell, library and creation action are usable.
    expect(await screen.findByRole("heading", { name: "任务库" })).toBeVisible();
    expect(screen.getByRole("link", { name: "处理队列" })).toHaveAttribute("href", "/workstation/queue");
    expect(screen.getByRole("button", { name: "新建任务" })).toBeEnabled();
  });

  it("replaces a legacy task deep link with the current overview route", async () => {
    // Given: the current overview API, with no old detail-page endpoint.
    const paths: string[] = [];
    vi.stubGlobal("fetch", async (input: RequestInfo | URL) => {
      paths.push(new URL(new Request(input).url).pathname);
      return json(overview);
    });
    const historyLength = window.history.length;
    // When: an old task URL is opened.
    renderRoute("/tasks/task-route");
    // Then: redirect replacement loads the real overview and preserves history depth.
    expect(await screen.findByRole("heading", { name: overview.title })).toBeVisible();
    expect(window.location.pathname).toBe("/workstation/tasks/task-route");
    expect(window.history.length).toBe(historyLength);
    expect(paths).toEqual(["/api/v2/tasks/task-route"]);
    expect(screen.getByRole("list", { name: "任务阶段" })).toHaveTextContent(/采集.*媒体准备.*语音转写.*翻译.*高光.*导出.*报告/);
    expect(screen.getByText("route ASR progress")).toBeVisible();
    expect(screen.getByText("转写音频 · 3 / 5")).toBeVisible();
  });

  it("creates an inspected source from the real shell and opens its current overview", async () => {
    // Given: successful inspection, profile and task creation endpoints.
    const createdBodies: unknown[] = [];
    vi.stubGlobal("fetch", async (input: RequestInfo | URL, init?: RequestInit) => {
      const request = new Request(input, init);
      const pathname = new URL(request.url).pathname;
      if (pathname === "/api/v2/sources/bilibili/inspect") return json({ normalized_url: "https://www.bilibili.com/video/BV1route", source_video_id: "BV1route", title: "已检查录播", uploader: null, duration_seconds: 60 });
      if (pathname === "/api/v2/processing-profiles") return json({ profiles: [{ id: "standard", name: "Standard", stages: ["ingest"] }] });
      if (pathname === "/api/v2/tasks" && request.method === "POST") {
        createdBodies.push(await request.json());
        return json({ task_id: "task-route", profile_id: "standard", priority: 3, status: "pending" }, 201);
      }
      if (pathname === "/api/v2/tasks/task-route") return json({ ...overview, status: "pending", execution_progress: null });
      return libraryResponse(request);
    });
    renderRoute("/");
    // When: the operator completes the real shell's creation drawer.
    fireEvent.click(screen.getByRole("button", { name: "新建任务" }));
    fireEvent.click(screen.getByRole("button", { name: "Bilibili 录播" }));
    fireEvent.change(screen.getByRole("textbox", { name: "Bilibili 链接" }), { target: { value: "https://www.bilibili.com/video/BV1route" } });
    fireEvent.click(screen.getByRole("button", { name: "检查来源" }));
    fireEvent.click(await screen.findByRole("button", { name: "继续设置" }));
    fireEvent.change(await screen.findByRole("spinbutton", { name: "优先级" }), { target: { value: "3" } });
    fireEvent.click(screen.getByRole("button", { name: "创建任务" }));
    // Then: the real request carries the draft and the real route renders its task.
    expect(await screen.findByRole("heading", { name: overview.title })).toBeVisible();
    expect(window.location.pathname).toBe("/workstation/tasks/task-route");
    expect(createdBodies).toEqual([{ source: { kind: "bilibili", url: "https://www.bilibili.com/video/BV1route" }, profile_id: "standard", priority: 3, highlight_filtering_enabled: false }]);
    expect(screen.getByText("等待开始")).toBeVisible();
  });

  it("keeps creation available through overview loading and failure, then retries the query", async () => {
    // Given: the first overview request remains pending and then returns 404.
    let settle: ((response: Response) => void) | undefined;
    let requests = 0;
    vi.stubGlobal("fetch", () => {
      requests += 1;
      return requests === 1 ? new Promise<Response>((resolve) => { settle = resolve; }) : Promise.resolve(json(overview));
    });
    renderRoute("/workstation/tasks/task-route");
    expect(screen.getByRole("heading", { name: "正在读取任务概览" })).toBeVisible();
    // When: the request fails and the operator retries through the current error view.
    await act(async () => { settle?.(json({ detail: "Task not found" }, 404)); });
    expect(await screen.findByRole("heading", { name: "任务概览无法读取" })).toBeVisible();
    expect(screen.getByRole("button", { name: "新建任务" })).toBeEnabled();
    fireEvent.click(screen.getByRole("button", { name: "重新读取任务概览" }));
    // Then: a fresh request recovers the overview.
    expect(await screen.findByRole("heading", { name: overview.title })).toBeVisible();
    expect(requests).toBe(2);
  });

  it("retries a failed translation stage and refreshes the current task projection", async () => {
    // Given: the backend offers a translation retry action.
    const retries: unknown[] = [];
    vi.stubGlobal("fetch", async (input: RequestInfo | URL, init?: RequestInit) => {
      const request = new Request(input, init);
      if (new URL(request.url).pathname === "/api/tasks/task-route/retry" && request.method === "POST") {
        retries.push(await request.json());
        return json({ task_id: "task-route", retry_stage: "translation", status: "pending" });
      }
      return json(retries.length > 0 ? { ...overview, status: "pending", execution_progress: null } : {
        ...overview, status: "failed", execution_progress: null, current_stage: "translation",
        recovery_actions: [{ confirmation_required: false, description_key: "retry_stage", disabled_reason: null, enabled: true, endpoint: "/api/tasks/task-route/retry", id: "retry_stage", label_key: "retry_stage", method: "POST", payload: { stage_name: "translation" }, success_behavior: "poll_task" }],
      });
    });
    renderRoute("/workstation/tasks/task-route");
    // When: the operator retries the offered stage.
    fireEvent.click(await screen.findByRole("button", { name: "从翻译重新尝试" }));
    // Then: the exact stage is submitted and invalidation refreshes the rendered status.
    expect(await screen.findByText("等待开始")).toBeVisible();
    expect(retries).toEqual([{ stage_name: "translation" }]);
  });

  it.each([
    ["success", "任务已完成"],
    ["failed", "任务需要恢复"],
    ["cancelled", "任务已取消"],
  ] as const)("hides stale execution progress for a %s task on the current route", async (status, label) => {
    // Given: a terminal task retains an old running ASR progress record and stage.
    vi.stubGlobal("fetch", async () => json({ ...overview, status }));
    // When: the actual task route reads the terminal projection.
    renderRoute("/workstation/tasks/task-route");
    // Then: task status owns liveness even when a stale stage still says running.
    expect(await screen.findByText(label)).toBeVisible();
    expect(screen.queryByText("route ASR progress")).not.toBeInTheDocument();
    expect(screen.queryByText("转写音频 · 3 / 5")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /重新尝试/ })).not.toBeInTheDocument();
    expect(screen.getByText("阶段摘要")).toBeVisible();
  });
});
