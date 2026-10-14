import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";

import { Companion } from "./Companion";

afterEach(() => vi.unstubAllGlobals());

it("saves a persistent key and translates an existing task without creating or resuming one", async () => {
  const posts: string[] = [];
  let translated = false;
  let configured = false;
  vi.stubGlobal("fetch", vi.fn(async (url: string, options?: RequestInit) => {
    if (options?.method === "POST") {
      posts.push(url);
      if (url.endsWith("translation-config")) {
        expect(JSON.parse(String(options.body))).toEqual({ api_key: "test-session-key" });
        configured = true;
      } else if (url.endsWith("/translate")) translated = true;
      return new Response(JSON.stringify({ id: "aabbccddeeff" }));
    }
    const job = { id: "aabbccddeeff", state: "completed", message: "处理完成", error: null, started_at: 0,
      duration: 10, mode: "ranges", can_resume: false, has_source: true, language: "ja",
      clips: [{ video: "clip-001.mp4", subtitles: "clip-001.srt", start: 1, end: 4, score: null, reasons: [] }],
      segments: [{ id: "1", start_seconds: 1, end_seconds: 3, text: "こんにちは" }],
      bilingual_segments: translated ? [{ id: "1", start_seconds: 1, end_seconds: 3, text: "こんにちは\n你好" }] : [],
      translation: { state: translated ? "completed" : "not_started", done: translated ? 1 : 0, total: 1, error: null } };
    return new Response(JSON.stringify(url.endsWith("/config") ? { ready: true, missing: [], translation_configured: configured } : url.endsWith("/jobs") ? [job] : job));
  }));
  mount();
  await screen.findByText("こんにちは");
  const input = screen.getByLabelText("DeepSeek API Key");
  expect(input).toHaveAttribute("type", "password");
  fireEvent.change(input, { target: { value: "test-session-key" } });
  fireEvent.click(screen.getByRole("button", { name: "保存 Key 到配置文件" }));
  await waitFor(() => expect(input).toHaveValue(""));
  expect(await screen.findByText(/Key 已保存 · 重启自动加载/)).toBeVisible();
  const button = screen.getByRole("button", { name: "生成中日双语字幕" });
  await waitFor(() => expect(button).toBeEnabled());
  fireEvent.click(button);
  const download = await screen.findByRole("link", { name: "完整双语字幕 SRT" });
  expect(download).toHaveAttribute("href", "/companion-api/jobs/aabbccddeeff/files/subtitles.ja-zh.srt?download=true");
  expect(document.querySelector("track")).toHaveAttribute("src", "/companion-api/jobs/aabbccddeeff/files/subtitles.ja-zh.vtt");
  fireEvent.click(screen.getByRole("button", { name: "预览切片 1" }));
  expect(document.querySelector("track")).toHaveAttribute("src", "/companion-api/jobs/aabbccddeeff/files/clip-001.ja-zh.vtt");
  expect(posts).toEqual(["/companion-api/translation-config", "/companion-api/jobs/aabbccddeeff/translate"]);
});

function mount() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(<QueryClientProvider client={client}><Companion /></QueryClientProvider>);
}

it("loads and saves the translation model without submitting a key", async () => {
  let model = "deepseek-v4-pro";
  const posts: unknown[] = [];
  vi.stubGlobal("fetch", vi.fn(async (url: string, options?: RequestInit) => {
    if (options?.method === "POST") {
      const payload = JSON.parse(String(options.body));
      posts.push(payload);
      model = payload.model;
      return new Response(JSON.stringify({ translation_model: model }));
    }
    return new Response(JSON.stringify(url.endsWith("/config") ? { ready: true, missing: [],
      translation_configured: true, translation_model: model, translation_models: ["deepseek-flash", "deepseek-v4-pro"] } : []));
  }));
  mount();
  const select = await screen.findByLabelText("翻译模型");
  await waitFor(() => expect(select).toHaveValue("deepseek-v4-pro"));
  fireEvent.change(select, { target: { value: "deepseek-flash" } });
  fireEvent.click(screen.getByRole("button", { name: "保存模型" }));
  await waitFor(() => expect(posts).toEqual([{ model: "deepseek-flash" }]));
  expect(screen.getByLabelText("DeepSeek API Key")).toHaveValue("");
});

function fakeApi() {
  let submitted: unknown;
  const job = { id: "aabbccddeeff", state: "completed", message: "处理完成，已导出 1 个切片", error: null, started_at: 0,
    duration: 10, mode: "ranges", can_resume: false, has_source: true,
    clips: [{ video: "clip-001.mp4", subtitles: "clip-001.srt", start: 1, end: 4, score: null, reasons: ["manual"] }],
    segments: [{ segment_id: "1", start_seconds: 1, end_seconds: 3, text: "测试字幕" }] };
  vi.stubGlobal("fetch", vi.fn(async (url: string, options?: RequestInit) => {
    if (options?.method === "POST") {
      submitted = JSON.parse(String(options.body));
      return new Response(JSON.stringify({ id: job.id }), { status: 202 });
    }
    const result = url.endsWith("/config") ? { ready: true, missing: [] } : url.endsWith("/jobs") ? [] : job;
    return new Response(JSON.stringify(result));
  }));
  return () => submitted;
}

it("submits explicit ranges and shows real preview and export links", async () => {
  const submitted = fakeApi();
  mount();
  await waitFor(() => expect(screen.getByRole("button", { name: "开始处理" })).toBeEnabled());
  fireEvent.change(screen.getByLabelText("视频链接"), { target: { value: "https://example.org/video.mp4" } });
  fireEvent.change(screen.getByLabelText("开始时间 1"), { target: { value: "00:01" } });
  fireEvent.change(screen.getByLabelText("结束时间 1"), { target: { value: "00:04" } });
  fireEvent.click(screen.getByRole("button", { name: "开始处理" }));
  await screen.findByText("测试字幕");
  expect(submitted()).toEqual({ url: "https://example.org/video.mp4", ranges: [["00:01", "00:04"]], highlights: null, language: "auto" });
  expect(screen.getByRole("link", { name: "下载切片 1 视频" })).toHaveAttribute("href", "/companion-api/jobs/aabbccddeeff/files/clip-001.mp4?download=true");
  fireEvent.click(screen.getByRole("button", { name: "预览切片 1" }));
  expect(document.querySelector("video")).toHaveAttribute("src", "/companion-api/jobs/aabbccddeeff/files/clip-001.mp4");
  expect(document.querySelector("track")).toHaveAttribute("src", "/companion-api/jobs/aabbccddeeff/files/clip-001.vtt");
});

it("preserves range drafts when switching mode and submits only highlights", async () => {
  const submitted = fakeApi();
  mount();
  await waitFor(() => expect(screen.getByRole("button", { name: "开始处理" })).toBeEnabled());
  fireEvent.change(screen.getByLabelText("视频链接"), { target: { value: "https://example.org/v.mp4" } });
  fireEvent.change(screen.getByLabelText("开始时间 1"), { target: { value: "12" } });
  fireEvent.click(screen.getByLabelText("高光自动切片"));
  fireEvent.change(screen.getByLabelText("最多导出片段数"), { target: { value: "2" } });
  fireEvent.click(screen.getByLabelText("指定时间段"));
  expect(screen.getByLabelText("开始时间 1")).toHaveValue("12");
  fireEvent.click(screen.getByLabelText("高光自动切片"));
  fireEvent.click(screen.getByRole("button", { name: "开始处理" }));
  await screen.findByText("测试字幕");
  expect(submitted()).toEqual({ url: "https://example.org/v.mp4", ranges: [], highlights: 2, language: "auto" });
});

it("rejects reversed ranges and never starts a job", async () => {
  const submitted = fakeApi();
  mount();
  await waitFor(() => expect(screen.getByRole("button", { name: "开始处理" })).toBeEnabled());
  fireEvent.change(screen.getByLabelText("视频链接"), { target: { value: "https://example.org/v.mp4" } });
  fireEvent.change(screen.getByLabelText("开始时间 1"), { target: { value: "30" } });
  fireEvent.change(screen.getByLabelText("结束时间 1"), { target: { value: "10" } });
  fireEvent.click(screen.getByRole("button", { name: "开始处理" }));
  expect(within(await screen.findByRole("alert")).getByText(/结束时间必须大于开始时间/)).toBeInTheDocument();
  expect(submitted()).toBeUndefined();
});

it("retries a failed initial task detail request and recovers the preview", async () => {
  fakeApi();
  const original = globalThis.fetch;
  let failures = 0;
  vi.stubGlobal("fetch", vi.fn(async (url: string, options?: RequestInit) => {
    if (url.includes("/jobs/aabbccddeeff") && failures++ === 0) return new Response(JSON.stringify({ detail: "temporary outage" }), { status: 503 });
    return original(url, options);
  }));
  mount();
  await waitFor(() => expect(screen.getByRole("button", { name: "开始处理" })).toBeEnabled());
  fireEvent.change(screen.getByLabelText("视频链接"), { target: { value: "https://example.org/video.mp4" } });
  fireEvent.click(screen.getByRole("button", { name: "开始处理" }));
  await screen.findByText(/本地服务连接中断/);
  await waitFor(() => expect(screen.getByText("测试字幕")).toBeInTheDocument(), { timeout: 5000 });
});

it("uses completed detail immediately when the history poll still says running", async () => {
  fakeApi();
  const original = globalThis.fetch;
  vi.stubGlobal("fetch", vi.fn(async (url: string, options?: RequestInit) => {
    if (url.endsWith("/jobs") && !options) return new Response(JSON.stringify([{ id: "aabbccddeeff", state: "preparing", started_at: 0, mode: "ranges" }]));
    return original(url, options);
  }));
  mount();
  await screen.findByText("测试字幕");
  expect(screen.getByRole("button", { name: "开始处理" })).toBeEnabled();
  expect(within(screen.getByRole("region", { name: "任务记录" })).getByText("已完成")).toBeInTheDocument();
});
