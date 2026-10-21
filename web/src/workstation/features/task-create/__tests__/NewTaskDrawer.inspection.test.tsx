import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { useState } from "react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { ReactNode } from "react";

import { NewTaskDrawer } from "../NewTaskDrawer";

const originalUrl = "https://www.bilibili.com/video/BV1original";
const currentUrl = "https://www.bilibili.com/video/BV1current";

function response(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { headers: { "Content-Type": "application/json" }, status });
}

function inspection(url: string): Response {
  return response({ normalized_url: url, source_video_id: "BV1inspection", title: url, uploader: null, duration_seconds: null });
}

function ControlledDrawer(): ReactNode {
  const [open, setOpen] = useState(true);
  return <><NewTaskDrawer open={open} onOpenChange={setOpen} /><button onClick={() => setOpen(true)} type="button">重新打开新建任务</button></>;
}

function renderDelayedDrawer() {
  const pending: ((value: Response) => void)[] = [];
  const submitted: unknown[] = [];
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  vi.stubGlobal("fetch", async (input: RequestInfo | URL) => {
    if (!(input instanceof Request)) throw new TypeError("Expected the generated client's Request.");
    const url = new URL(input.url);
    if (url.pathname === "/api/v2/sources/bilibili/inspect") return new Promise<Response>((resolve) => pending.push(resolve));
    if (url.pathname === "/api/v2/sources/local") return response({ roots: [{ id: "media", name: "媒体导入" }], root_id: "media", relative_path: "", entries: [{ name: "local.mp4", relative_path: "local.mp4", kind: "file" }] });
    if (url.pathname === "/api/v2/processing-profiles") return response({ profiles: [{ id: "standard", name: "Standard", stages: ["ingest"] }] });
    if (url.pathname === "/api/v2/tasks") {
      submitted.push(await input.json());
      return response({ task_id: "created", profile_id: "standard", priority: 0, status: "pending" }, 201);
    }
    throw new TypeError(`Unexpected endpoint: ${url.pathname}`);
  });
  render(<QueryClientProvider client={queryClient}><MemoryRouter><ControlledDrawer /></MemoryRouter></QueryClientProvider>);
  return { pending, submitted, queryClient };
}

function enterUrl(url: string): void {
  fireEvent.change(screen.getByRole("textbox", { name: "Bilibili 链接" }), { target: { value: url } });
}

function startInspection(): void {
  fireEvent.click(screen.getByRole("button", { name: "检查来源" }));
}

async function discardAndReopen(): Promise<void> {
  fireEvent.click(screen.getByRole("button", { name: "关闭新建任务" }));
  fireEvent.click(await screen.findByRole("button", { name: "放弃更改" }));
  fireEvent.click(screen.getByRole("button", { name: "重新打开新建任务" }));
  fireEvent.click(await screen.findByRole("button", { name: "Bilibili 录播" }));
  enterUrl(originalUrl);
}

async function releaseInspection(harness: ReturnType<typeof renderDelayedDrawer>, result: Response): Promise<void> {
  const resolve = harness.pending.shift();
  if (resolve === undefined) throw new TypeError("No inspection request to release.");
  resolve(result);
  await waitFor(() => expect(harness.queryClient.isMutating()).toBe(0));
}

describe("NewTaskDrawer inspection ownership", () => {
  afterEach(() => vi.unstubAllGlobals());

  it.each(["success", "failure"])("ignores a late %s after editing the URL", async (outcome) => {
    // Given: an inspection in flight for the original URL.
    const harness = renderDelayedDrawer();
    fireEvent.click(screen.getByRole("button", { name: "Bilibili 录播" }));
    enterUrl(originalUrl);
    startInspection();
    await waitFor(() => expect(harness.pending).toHaveLength(1));
    enterUrl(currentUrl);

    // When: the response arrives after the input has changed.
    await releaseInspection(harness, outcome === "success" ? inspection(originalUrl) : response({}, 500));

    // Then: only the current URL remains editable, with no stale preview or error.
    expect(screen.getByRole("textbox", { name: "Bilibili 链接" })).toHaveValue(currentUrl);
    expect(screen.getByRole("textbox", { name: "Bilibili 链接" })).not.toHaveAttribute("aria-invalid");
    expect(screen.queryByRole("region", { name: "Bilibili 来源预览" })).not.toBeInTheDocument();
  });

  it.each(["success", "failure"])("preserves local selection when a late %s arrives", async (outcome) => {
    // Given: the operator selects a local file while Bilibili inspection is pending.
    const harness = renderDelayedDrawer();
    fireEvent.click(screen.getByRole("button", { name: "Bilibili 录播" }));
    enterUrl(originalUrl);
    startInspection();
    await waitFor(() => expect(harness.pending).toHaveLength(1));
    fireEvent.click(screen.getByRole("button", { name: "本地文件" }));
    fireEvent.click(await screen.findByRole("button", { name: "媒体导入" }));
    fireEvent.click(await screen.findByRole("button", { name: "local.mp4" }));

    // When: the obsolete Bilibili response completes.
    await releaseInspection(harness, outcome === "success" ? inspection(originalUrl) : response({}, 500));

    // Then: local preview and its submitted source remain local.
    expect(screen.getByRole("region", { name: "已选本地来源" })).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "继续设置" }));
    fireEvent.click(screen.getByRole("button", { name: "创建任务" }));
    await waitFor(() => expect(harness.submitted).toEqual([{ highlight_filtering_enabled: false, priority: 0, profile_id: "standard", source: { kind: "local", root_id: "media", relative_path: "local.mp4", import_mode: "reference" } }]));
  });

  it.each(["success", "failure"])("ignores a late %s after discarding and reopening the same URL", async (outcome) => {
    // Given: a discarded request and a new draft with the identical URL.
    const harness = renderDelayedDrawer();
    fireEvent.click(screen.getByRole("button", { name: "Bilibili 录播" }));
    enterUrl(originalUrl);
    startInspection();
    await waitFor(() => expect(harness.pending).toHaveLength(1));
    await discardAndReopen();

    // When: the old draft's response resolves.
    await releaseInspection(harness, outcome === "success" ? inspection(originalUrl) : response({}, 500));

    // Then: matching URLs do not allow the old draft to supply metadata or errors.
    expect(screen.getByRole("textbox", { name: "Bilibili 链接" })).toHaveValue(originalUrl);
    expect(screen.getByRole("textbox", { name: "Bilibili 链接" })).not.toHaveAttribute("aria-invalid");
    expect(screen.queryByRole("region", { name: "Bilibili 来源预览" })).not.toBeInTheDocument();
  });

  it("inspects and submits the current draft while the discarded same-URL request remains pending", async () => {
    // Given: an old inspection still pending after discard/reopen.
    const harness = renderDelayedDrawer();
    fireEvent.click(screen.getByRole("button", { name: "Bilibili 录播" }));
    enterUrl(originalUrl);
    startInspection();
    await waitFor(() => expect(harness.pending).toHaveLength(1));
    await discardAndReopen();

    // When: a fresh inspection is requested and resolves before the obsolete request.
    expect(screen.getByRole("button", { name: "检查来源" })).toBeEnabled();
    startInspection();
    await waitFor(() => expect(harness.pending).toHaveLength(2));
    const resolveCurrent = harness.pending.pop();
    if (resolveCurrent === undefined) throw new TypeError("Missing current inspection.");
    resolveCurrent(inspection(currentUrl));

    // Then: the current normalized URL alone reaches the create payload.
    fireEvent.click(await screen.findByRole("button", { name: "继续设置" }));
    fireEvent.click(screen.getByRole("button", { name: "创建任务" }));
    await waitFor(() => expect(harness.submitted).toEqual([{ highlight_filtering_enabled: false, priority: 0, profile_id: "standard", source: { kind: "bilibili", url: currentUrl } }]));
    await releaseInspection(harness, inspection(originalUrl));
    fireEvent.click(screen.getByRole("button", { name: "重新打开新建任务" }));
    expect(screen.getByRole("button", { name: "Bilibili 录播" })).toBeVisible();
    expect(screen.queryByRole("region", { name: "Bilibili 来源预览" })).not.toBeInTheDocument();
  });

  it("shows an inspection failure for the current source", async () => {
    // Given: a current pending inspection with surrounding input whitespace.
    const harness = renderDelayedDrawer();
    fireEvent.click(screen.getByRole("button", { name: "Bilibili 录播" }));
    enterUrl(` ${originalUrl} `);
    startInspection();
    await waitFor(() => expect(harness.pending).toHaveLength(1));

    // When: this current request fails.
    await releaseInspection(harness, response({}, 500));

    // Then: the current field retains input and displays its actionable error.
    expect(screen.getByRole("textbox", { name: "Bilibili 链接" })).toHaveValue(` ${originalUrl} `);
    expect(screen.getByRole("textbox", { name: "Bilibili 链接" })).toHaveAttribute("aria-invalid", "true");
    expect(screen.getByText("来源检查失败，请确认链接后重试。")).toBeVisible();
  });
});
