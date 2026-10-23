import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";

import { Companion } from "./Companion";
import { documentFixture } from './subtitleDocument.fixture';

it("previews and downloads available bilingual live clips before recording ends", async () => {
  const job = {id:"aabbccddeeff",state:"recording",mode:"saozi",live:true,has_source:false,
    message:"录制中",duration:160,started_at:0,can_stop:true,
    clips:[{video:"clip-001.mp4",subtitles:"clip-001.srt",bilingual_subtitles:"clip-001.ja-zh.srt",start:0,end:80,reasons:[],score:null},
      {video:"clip-002.mp4",subtitles:"clip-002.srt",start:80,end:160,reasons:[],score:null}],
    segments:[{id:"1",start_seconds:0,end_seconds:1,text:"こんにちは"}],
    bilingual_segments:[{id:"1",start_seconds:0,end_seconds:1,text:"こんにちは\n你好"}],
    bilingual_files:["subtitles.ja-zh.srt","clip-001.ja-zh.srt"],
    translation:{state:"partial",done:1,total:2,error:null}};
  vi.stubGlobal("fetch", vi.fn(async (url: string) => new Response(JSON.stringify(
    url.endsWith("/config") ? {ready:true,missing:[],translation_configured:true} : url.endsWith("/jobs") ? [job] : job))));
  mount();
  openTool("导出");
  expect(await screen.findByRole("link", {name:"下载切片 1 双语字幕"})).toHaveAttribute("href", "/companion-api/jobs/aabbccddeeff/files/clip-001.ja-zh.srt?download=true");
  expect(screen.queryByRole("link", {name:"下载切片 2 双语字幕"})).toBeNull();
  await waitFor(() => expect(document.querySelector("track")).toHaveAttribute("src", "/companion-api/jobs/aabbccddeeff/files/clip-001.ja-zh.vtt"));
});
import { defaultStyle } from "./subtitleStyle";

afterEach(() => vi.unstubAllGlobals());

function selectionApi() {
  fakeApi();
  const original = globalThis.fetch;
  let translated = false;
  const loadedSources: string[] = [];
  const jobs = ['aabbccddeeff', '112233445566'].map(id => ({id, state: 'completed', started_at: 0, mode: 'ranges'}));
  vi.stubGlobal('fetch', vi.fn(async (url: string, options?: RequestInit) => {
    if (url.endsWith('/config')) return new Response(JSON.stringify({ready: true, missing: [], translation_configured: true}));
    if (url.endsWith('/translate')) { translated = true; return new Response('{}'); }
    if (url.endsWith('/jobs')) return new Response(JSON.stringify(jobs));
    if (url.endsWith('/subtitle-settings')) return new Response(JSON.stringify({style: defaultStyle, templates: [], arctime_templates: [], burn_available: true}));
    if (url.endsWith('/subtitle-document')) {
      const source = (translated ? 'b' : 'a').repeat(64);
      if (options?.method !== 'POST') loadedSources.push(source);
      return new Response(options?.method === 'POST' ? String(options.body) : JSON.stringify({...documentFixture(), source_fingerprint: source}));
    }
    if (url.endsWith('/subtitle-exports')) return new Response(JSON.stringify({active: null, outputs: []}));
    const response = await original(url, options);
    if (jobs.some(job => url.endsWith(`/jobs/${job.id}`))) return new Response(JSON.stringify({...await response.json(), bilingual_segments: [], translation: {state: translated ? 'completed' : 'not_started'}}));
    return response;
  }));
  return loadedSources;
}

it('initializes the first cue again when switching tasks with matching cue IDs', async () => {
  // Given two task documents share source and cue IDs.
  selectionApi();
  mount(false);
  openTool('字幕样式');
  expect(await screen.findByLabelText('选择字幕 1')).toBeChecked();
  fireEvent.click(screen.getByLabelText('选择字幕 1'));
  fireEvent.click(screen.getByLabelText('选择字幕 2'));

  // When another task is selected through history.
  openTool('任务记录');
  fireEvent.click(screen.getByRole('button', {name: /112233/}));

  // Then its initial selection is valid, independent of the previous task.
  await waitFor(() => expect(screen.getByLabelText('选择字幕 1')).toBeChecked());
  expect(screen.getByLabelText('选择字幕 2')).not.toBeChecked();
});

it('keeps explicit empty selection through edits, undo and workspace navigation', async () => {
  // Given a loaded document with an undoable edit.
  selectionApi();
  mount(false);
  openTool('字幕样式');
  fireEvent.change(await screen.findByLabelText('本条原文'), {target: {value: '编辑稿'}});

  // When selection is cleared and the document and visible workspace change.
  fireEvent.click(screen.getByRole('button', {name: '取消选择'}));
  fireEvent.click(screen.getByRole('button', {name: '撤销'}));
  fireEvent.click(screen.getByRole('button', {name: '设置'}));
  fireEvent.click(screen.getByRole('button', {name: '返回工作区'}));
  fireEvent.click(screen.getByRole('tab', {name: '模板设计'}));
  fireEvent.click(screen.getByRole('tab', {name: '日常模式'}));
  openTool('字幕样式');
  fireEvent.change(screen.getByLabelText('查找字幕'), {target: {value: '你好'}});

  // Then no cue is silently selected again.
  expect(screen.getByText('2 条 · 已选 0')).toBeVisible();
  expect(screen.getByLabelText('选择字幕 1')).not.toBeChecked();
  expect(screen.queryByLabelText('本条原文')).not.toBeInTheDocument();
});

it('initializes selection when a refreshed source document replaces an empty selection', async () => {
  const loadedSources = selectionApi();
  mount(false);
  openTool('字幕样式');
  await screen.findByLabelText('选择字幕 1');
  fireEvent.click(screen.getByRole('button', {name: '取消选择'}));
  fireEvent.click(screen.getByRole('button', {name: '生成中日双语字幕'}));
  await waitFor(() => expect(loadedSources).toEqual(['a'.repeat(64), 'b'.repeat(64)]));
  await waitFor(() => expect(screen.getByLabelText('选择字幕 1')).toBeChecked());
  expect(screen.getByLabelText('选择字幕 2')).not.toBeChecked();
});

it('leaves the first cue unchanged when attempting bulk style, timing and move actions after clearing', async () => {
  // Given the timing tools and a visible first cue at the playhead.
  selectionApi();
  mount(false);
  openTool('字幕样式');
  await screen.findByLabelText('本条原文');
  fireEvent.click(screen.getByRole('button', {name: '高级逐条编辑'}));
  fireEvent.click(screen.getByRole('button', {name: /^时间$/}));
  const video = document.querySelector('video');
  if (!video) throw new Error('Expected task video');
  fireEvent.timeUpdate(video, {target: {currentTime: 2}});

  // When cleared, attempt every formerly available bulk action and canvas nudge.
  fireEvent.click(screen.getByRole('button', {name: '取消选择'}));
  for (const name of ['平移所选时间', '应用当前全局模板到所选']) {
    const button = screen.queryByRole('button', {name});
    if (button) fireEvent.click(button);
  }
  const anchor = screen.queryByRole('button', {name: '原文位置锚点'});
  if (anchor) fireEvent.keyDown(anchor, {key: 'ArrowRight'});
  fireEvent.click(screen.getByLabelText('选择字幕 1'));

  // Then the original timing and inherited style are intact.
  expect(screen.getByLabelText('开始秒数')).toHaveValue(1);
  expect(screen.getByLabelText('结束秒数')).toHaveValue(5);
  expect(screen.getByText(/当前语言继承全局样式/)).toBeVisible();
  expect(screen.getByRole('button', {name: '撤销'})).toBeDisabled();
});

it.each([false, true])('prunes removed split-cue IDs after undo with a retained cue: %s', async retainFirst => {
  // Given a split creates a new cue, selected alone or alongside the original.
  selectionApi();
  mount(false);
  openTool('字幕样式');
  await screen.findByLabelText('本条原文');
  fireEvent.click(screen.getByRole('button', {name: '高级逐条编辑'}));
  fireEvent.click(screen.getByRole('button', {name: /^时间$/}));
  const video = document.querySelector('video');
  if (!video) throw new Error('Expected task video');
  fireEvent.timeUpdate(video, {target: {currentTime: 3}});
  fireEvent.click(screen.getByRole('button', {name: '在播放头拆分'}));
  fireEvent.click(screen.getByLabelText('选择字幕 2'));
  if (!retainFirst) fireEvent.click(screen.getByLabelText('选择字幕 1'));
  expect(screen.getByText(`3 条 · 已选 ${retainFirst ? 2 : 1}`)).toBeVisible();

  // When undo removes the newly selected cue.
  fireEvent.click(screen.getByRole('button', {name: '撤销'}));

  // Then every stale ID is removed without replacing an empty selection.
  expect(screen.getByText(`2 条 · 已选 ${retainFirst ? 1 : 0}`)).toBeVisible();
  expect(screen.getByLabelText('选择字幕 1').matches(':checked')).toBe(retainFirst);
  expect(screen.getByLabelText('选择字幕 2')).not.toBeChecked();
});

function saoziApi(translationConfigured = true) {
  const posts: {url: string; body: BodyInit | null | undefined}[] = [];
  vi.stubGlobal("fetch", vi.fn(async (url: string, options?: RequestInit) => {
    if (options?.method === "POST") {
      posts.push({url, body: options.body});
      return new Response(JSON.stringify({id:"aabbccddeeff"}), {status:202});
    }
    return new Response(JSON.stringify(url.endsWith("/config") ? {ready:true,missing:[],translation_configured:translationConfigured} : url.endsWith("/jobs") ? [] : {
      id:"aabbccddeeff",state:"recording",mode:"saozi",live:true,can_stop:true,message:"正在录制",clips:[],segments:[],translation:{state:"not_started"}
    }));
  }));
  return posts;
}

it("starts Bilibili live saozi and stops capture while preserving results", async () => {
  const posts = saoziApi();
  mount();
  await waitFor(() => expect(screen.getByRole("button", {name:"开始处理"})).toBeEnabled());
  openTool("新建任务");
  fireEvent.click(screen.getByRole("button", {name:"实时录播"}));
  fireEvent.change(screen.getByLabelText("直播间号"), {target:{value:"12345"}});
  fireEvent.click(screen.getByRole("button", {name:"开始处理"}));
  expect(await screen.findByRole("button", {name:"停止直播并导出剩余内容"})).toBeEnabled();
  expect(JSON.parse(String(posts[0]?.body))).toEqual({url:"12345",ranges:[],highlights:null,language:"auto",saozi:true,live:true});
  fireEvent.click(screen.getByRole("button", {name:"停止直播并导出剩余内容"}));
  await waitFor(() => expect(posts[1]?.url).toBe("/companion-api/jobs/aabbccddeeff/stop"));
});

it('submits the chosen saved subtitle template for live tasks only',async()=>{
 const posts:{url:string;body:string}[]=[];
 vi.stubGlobal('fetch',vi.fn(async(url:string,options?:RequestInit)=>{
   if(options?.method==='POST'){posts.push({url,body:String(options.body)});return new Response(JSON.stringify({id:'aabbccddeeff'}),{status:202});}
   return new Response(JSON.stringify(url.endsWith('/config')?{ready:true,missing:[],translation_configured:true}:
     url.endsWith('/subtitle-settings')?{style:defaultStyle,templates:[{id:'imported',name:'ArcTime 双语',style:defaultStyle}],arctime_templates:[],burn_available:true}:
     url.endsWith('/jobs')?[]:{id:'aabbccddeeff',state:'recording',mode:'saozi',live:true,message:'录制中',clips:[],segments:[],translation:{state:'not_started'}}));
 }));
 mount();openTool('新建任务');fireEvent.click(screen.getByRole('button',{name:'实时录播'}));
 await screen.findByRole('option',{name:'ArcTime 双语'});
 fireEvent.change(screen.getByLabelText('实时切片字幕模板'),{target:{value:'imported'}});
 fireEvent.change(screen.getByLabelText('直播间号'),{target:{value:'12345'}});
 fireEvent.click(screen.getByRole('button',{name:'开始处理'}));
 await waitFor(()=>expect(posts).toHaveLength(1));
 expect(JSON.parse(posts[0].body)).toMatchObject({live:true,subtitle_template_id:'imported'});
});

it.each([false,true])('defaults live to builtin Nyaru and permits opt-out: %s',async(optOut)=>{
 const posts:Record<string,unknown>[]=[];
 vi.stubGlobal('fetch',vi.fn(async(url:string,options?:RequestInit)=>{
   if(options?.method==='POST'){posts.push(JSON.parse(String(options.body)));return new Response(JSON.stringify({id:'aabbccddeeff'}),{status:202});}
   return new Response(JSON.stringify(url.endsWith('/config')?{ready:true,missing:[],translation_configured:true}:
     url.endsWith('/subtitle-settings')?{style:defaultStyle,templates:[{id:'nyaru',name:'猫雷 Nyaru',style:defaultStyle,builtin:true}],arctime_templates:[],burn_available:true}:
     url.endsWith('/jobs')?[]:{id:'aabbccddeeff',state:'recording',mode:'saozi',live:true,message:'录制中',clips:[],segments:[],translation:{state:'not_started'}}));
 }));
 mount();openTool('新建任务');fireEvent.click(screen.getByRole('button',{name:'实时录播'}));
 await screen.findByRole('option',{name:'猫雷 Nyaru'});
 expect(screen.getByLabelText('实时切片字幕模板')).toHaveValue('nyaru');
 if(optOut)fireEvent.change(screen.getByLabelText('实时切片字幕模板'),{target:{value:''}});
 fireEvent.change(screen.getByLabelText('直播间号'),{target:{value:'12345'}});
 fireEvent.click(screen.getByRole('button',{name:'开始处理'}));
 await waitFor(()=>expect(posts).toHaveLength(1));
 expect(posts[0].subtitle_template_id).toBe(optOut?undefined:'nyaru');
});

it("uploads a local recording as raw file bytes for saozi", async () => {
  const posts = saoziApi();
  mount();
  await waitFor(() => expect(screen.getByRole("button", {name:"开始处理"})).toBeEnabled());
  openTool("切片方式");
  fireEvent.click(screen.getByRole("radio", {name:"臊子"}));
  openTool("新建任务");
  fireEvent.click(screen.getByRole("button", {name:"本地视频"}));
  const file = new File(["recording"], "my-video.mp4", {type:"video/mp4"});
  fireEvent.change(screen.getByLabelText("本地视频文件"), {target:{files:[file]}});
  fireEvent.click(screen.getByRole("button", {name:"开始处理"}));
  await waitFor(() => expect(posts[0]?.body).toBe(file));
  const url = new URL(posts[0]?.url ?? "", "http://localhost");
  expect(url.pathname).toBe("/companion-api/jobs/upload");
  expect(url.searchParams.get("saozi")).toBe("true");
});

it("submits a BV number with the selected video slicing mode", async () => {
  const posts = saoziApi();
  mount();
  await waitFor(() => expect(screen.getByRole("button", {name:"开始处理"})).toBeEnabled());
  openTool("新建任务");
  expect(screen.getByRole("button", {name:"下载视频"})).toHaveAttribute("aria-pressed", "true");
  fireEvent.change(screen.getByLabelText("BV 号"), {target:{value:"BV1xx411c7mD"}});
  fireEvent.click(screen.getByRole("button", {name:"开始处理"}));
  await waitFor(() => expect(posts).toHaveLength(1));
  expect(JSON.parse(String(posts[0]?.body))).toEqual({url:"BV1xx411c7mD",ranges:[["00:00","00:30"]],highlights:null,language:"auto"});
});

it.each([
  ["下载视频", "BV 号", "BV1xx411c7mD", "https://www.bilibili.com/video/BV1xx411c7mD"],
  ["实时录播", "直播间号", "12345", "https://live.bilibili.com/12345"],
])("accepts only an identifier in the %s source field", (sourceName, label, identifier, link) => {
  saoziApi();
  mount();
  openTool("新建任务");
  fireEvent.click(screen.getByRole("button", {name:sourceName}));
  const input = screen.getByLabelText<HTMLInputElement>(label);
  fireEvent.change(input, {target:{value:identifier}});
  expect(input.validity.valid).toBe(true);
  fireEvent.change(input, {target:{value:link}});
  expect(input.validity.patternMismatch).toBe(true);
});

it("keeps source drafts and restores non-live slicing after switching away from live", async () => {
  saoziApi();
  mount();
  openTool("新建任务");
  fireEvent.change(screen.getByLabelText("BV 号"), {target:{value:"BV1xx411c7mD"}});
  fireEvent.click(screen.getByRole("button", {name:"实时录播"}));
  fireEvent.change(screen.getByLabelText("直播间号"), {target:{value:"12345"}});
  openTool("切片方式");
  expect(screen.getByRole("radio", {name:"臊子"})).toBeChecked();
  expect(screen.getByRole("radio", {name:"指定时间段"})).toBeDisabled();
  openTool("新建任务");
  fireEvent.click(screen.getByRole("button", {name:"下载视频"}));
  expect(screen.getByLabelText("BV 号")).toHaveValue("BV1xx411c7mD");
  openTool("切片方式");
  expect(screen.getByRole("radio", {name:"指定时间段"})).toBeChecked();
  openTool("新建任务");
  fireEvent.click(screen.getByRole("button", {name:"实时录播"}));
  expect(screen.getByLabelText("直播间号")).toHaveValue("12345");
});

it("excludes an invalid inactive source draft from form validation", () => {
  saoziApi();
  mount();
  openTool("新建任务");
  fireEvent.change(screen.getByLabelText("BV 号"), {target:{value:"invalid BV"}});
  fireEvent.click(screen.getByRole("button", {name:"实时录播"}));
  expect(screen.getByLabelText("BV 号")).toBeDisabled();
});

it.each(["指定时间段", "高光自动切片"])("imports a local file with %s without AI configuration", async mode => {
  const posts = saoziApi(false);
  mount();
  await waitFor(() => expect(screen.getByRole("button", {name:"开始处理"})).toBeEnabled());
  openTool("切片方式");
  fireEvent.click(screen.getByRole("radio", {name:mode}));
  openTool("新建任务");
  fireEvent.click(screen.getByRole("button", {name:"本地视频"}));
  const file = new File(["recording"], "my-video.mp4", {type:"video/mp4"});
  fireEvent.change(screen.getByLabelText("本地视频文件"), {target:{files:[file]}});
  fireEvent.click(screen.getByRole("button", {name:"下载视频"}));
  fireEvent.click(screen.getByRole("button", {name:"本地视频"}));
  fireEvent.click(screen.getByRole("button", {name:"开始处理"}));
  await waitFor(() => expect(posts[0]?.body).toBe(file));
  const params = new URL(posts[0]?.url ?? "", "http://localhost").searchParams;
  expect(params.get("saozi")).toBe("false");
  expect(JSON.parse(params.get("ranges") ?? "null")).toEqual(mode === "指定时间段" ? [["00:00","00:30"]] : []);
  expect(params.get("highlights")).toBe(mode === "高光自动切片" ? "3" : null);
});

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
  openTool("AI 设置");
  const input = screen.getByLabelText("DeepSeek API Key");
  expect(input).toHaveAttribute("type", "password");
  fireEvent.change(input, { target: { value: "test-session-key" } });
  fireEvent.click(screen.getByRole("button", { name: "保存 Key 到配置文件" }));
  await waitFor(() => expect(input).toHaveValue(""));
  expect(await screen.findByText(/Key 已保存 · 重启自动加载/)).toBeVisible();
  fireEvent.click(screen.getByRole("button",{name:"返回工作区"}));
  const button = screen.getByRole("button", { name: "生成中日双语字幕" });
  await waitFor(() => expect(button).toBeEnabled());
  fireEvent.click(button);
  openTool("导出");
  const download = await screen.findByRole("link", { name: "完整双语字幕 SRT" });
  expect(download).toHaveAttribute("href", "/companion-api/jobs/aabbccddeeff/files/subtitles.ja-zh.srt?download=true");
  expect(document.querySelector("track")).toHaveAttribute("src", "/companion-api/jobs/aabbccddeeff/files/subtitles.ja-zh.vtt");
  fireEvent.click(screen.getByRole("button", { name: "预览切片 1" }));
  expect(document.querySelector("track")).toHaveAttribute("src", "/companion-api/jobs/aabbccddeeff/files/clip-001.ja-zh.vtt");
  expect(posts).toEqual(["/companion-api/translation-config", "/companion-api/jobs/aabbccddeeff/translate"]);
});

function openTool(name: string) {
  const back = screen.queryByRole('button',{name:'返回工作区'});
  if(back) fireEvent.click(back);
  if(name==='AI 设置') {fireEvent.click(screen.getByRole('button',{name:'设置'}));fireEvent.click(screen.getByRole('button',{name:'AI与翻译'}));return;}
  const button = screen.getByRole('button',{name});
  if (button.getAttribute('aria-expanded') !== 'true') fireEvent.click(button);
}

function mount(openCreate = true) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  const result = render(<QueryClientProvider client={client}><Companion /></QueryClientProvider>);
  if (openCreate) openTool("新建任务");
  return result;
}

it("toggles the right drawer closed when its active toolbar option is clicked again", () => {
  fakeApi();
  mount(false);
  const toolbar = screen.getByRole("navigation", {name:"工作台工具"});
  const button = within(toolbar).getByRole("button", {name:"新建任务"});
  expect(button).toHaveAttribute("aria-expanded", "false");
  fireEvent.click(button);
  expect(screen.getByRole("complementary", {name:"工具选项"})).toBeVisible();
  expect(screen.getByLabelText("BV 号")).toBeVisible();
  fireEvent.click(button);
  expect(button).toHaveAttribute("aria-expanded", "false");
  expect(screen.getByRole("complementary", {name:"工具选项"})).toBeVisible();
  expect(screen.getByLabelText("BV 号")).not.toBeVisible();
});

it("preserves source and provider drafts while switching the single open drawer section", () => {
  fakeApi();
  mount(false);
  openTool("新建任务");
  fireEvent.change(screen.getByLabelText("BV 号"), {target:{value:"BV1xx411c7mD"}});
  openTool("AI 设置");
  fireEvent.change(screen.getByLabelText("DeepSeek API Key"), {target:{value:"unsaved-test-key"}});
  expect(screen.getByLabelText("BV 号")).not.toBeVisible();
  openTool("新建任务");
  expect(screen.getByLabelText("BV 号")).toHaveValue("BV1xx411c7mD");
  openTool("AI 设置");
  expect(screen.getByLabelText("DeepSeek API Key")).toHaveValue("unsaved-test-key");
  expect(screen.getByRole("button",{name:"返回工作区"})).toBeVisible();
});

it("returns focus to the active toolbar option when Escape closes the drawer", () => {
  fakeApi();
  mount(false);
  const button = screen.getByRole("button", {name:"新建任务"});
  fireEvent.click(button);
  screen.getByLabelText("BV 号").focus();
  fireEvent.keyDown(screen.getByLabelText("BV 号"), {key:"Escape"});
  expect(button).toHaveFocus();
  expect(screen.getByRole("complementary", {name:"工具选项"})).toBeVisible();
  expect(screen.getByLabelText("BV 号")).not.toBeVisible();
});

it("retains a selected local recording after closing and reopening the drawer", async () => {
  saoziApi();
  mount();
  await waitFor(() => expect(screen.getByRole("button", {name:"开始处理"})).toBeEnabled());
  openTool("切片方式");
  fireEvent.click(screen.getByRole("radio", {name:"臊子"}));
  openTool("新建任务");
  fireEvent.click(screen.getByRole("button", {name:"本地视频"}));
  const file = new File(["sample"], "draft.mp4", {type:"video/mp4"});
  const input = screen.getByLabelText<HTMLInputElement>("本地视频文件");
  fireEvent.change(input, {target:{files:[file]}});
  fireEvent.click(screen.getByRole("button", {name:"新建任务"}));
  openTool("AI 设置");
  openTool("新建任务");
  expect(screen.getByLabelText("本地视频文件")).toBe(input);
  expect(input.files?.[0]).toBe(file);
});

it("returns Escape focus to slicing after opening it from the creation form", () => {
  fakeApi();
  mount();
  fireEvent.click(screen.getByRole("button", {name:"指定时间段 · 1 段"}));
  fireEvent.keyDown(screen.getByLabelText("开始时间 1"), {key:"Escape"});
  expect(screen.getByRole("button", {name:"切片方式"})).toHaveFocus();
});

it("reveals source validation when starting from the slicing section", () => {
  fakeApi();
  mount();
  openTool("切片方式");
  const input = screen.getByLabelText("BV 号");
  const invalid = vi.fn();
  input.addEventListener("invalid", invalid);
  fireEvent.invalid(input);
  expect(invalid).toHaveBeenCalledTimes(1);
  expect(screen.getByLabelText("BV 号")).toBeVisible();
  expect(screen.getByRole("button", {name:"新建任务"})).toHaveAttribute("aria-expanded", "true");
  expect(screen.getByRole("alert")).not.toBeEmptyDOMElement();
});

it("offers only Flash and replaces a prohibited legacy default", async () => {
  const posts: unknown[] = [];
  vi.stubGlobal("fetch", vi.fn(async (url: string, options?: RequestInit) => {
    if (options?.method === "POST") {
      posts.push({url, body: JSON.parse(String(options.body))});
      return new Response(JSON.stringify({}));
    }
    return new Response(JSON.stringify(url.endsWith("/config") ? { ready: true, missing: [],
      translation_configured: true, translation_model: "deepseek-v4-pro", translation_models: ["deepseek-flash", "deepseek-v4-pro"] } : []));
  }));
  mount();
  openTool("AI 设置");
  const select = await screen.findByLabelText("翻译模型");
  expect(within(select).getAllByRole("option")).toHaveLength(1);
  expect(select).toHaveValue("deepseek-flash");
  expect(screen.queryByText(/DeepSeek V4 Pro/)).toBeNull();
  await waitFor(() => expect(screen.getByRole("button", { name: "保存供应商与模型" })).toBeEnabled());
  fireEvent.click(screen.getByRole("button", { name: "保存供应商与模型" }));
  await waitFor(() => expect(posts).toEqual([{url:"/companion-api/llm-config",body:{provider:"deepseek",model:"deepseek-flash"}}]));
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
  fireEvent.change(screen.getByLabelText("BV 号"), { target: { value: "BV1xx411c7mD" } });
  openTool("切片方式");
  fireEvent.change(screen.getByLabelText("开始时间 1"), { target: { value: "00:01" } });
  fireEvent.change(screen.getByLabelText("结束时间 1"), { target: { value: "00:04" } });
  fireEvent.click(screen.getByRole("button", { name: "开始处理" }));
  await screen.findByText("测试字幕");
  expect(submitted()).toEqual({ url: "BV1xx411c7mD", ranges: [["00:01", "00:04"]], highlights: null, language: "auto" });
  openTool("导出");
  expect(screen.getByRole("link", { name: "下载切片 1 视频" })).toHaveAttribute("href", "/companion-api/jobs/aabbccddeeff/files/clip-001.mp4?download=true");
  fireEvent.click(screen.getByRole("button", { name: "预览切片 1" }));
  expect(document.querySelector("video")).toHaveAttribute("src", "/companion-api/jobs/aabbccddeeff/files/clip-001.mp4");
  expect(document.querySelector("track")).toHaveAttribute("src", "/companion-api/jobs/aabbccddeeff/files/clip-001.vtt");
});

it("preserves range drafts when switching mode and submits only highlights", async () => {
  const submitted = fakeApi();
  mount();
  await waitFor(() => expect(screen.getByRole("button", { name: "开始处理" })).toBeEnabled());
  fireEvent.change(screen.getByLabelText("BV 号"), { target: { value: "BV1xx411c7mD" } });
  openTool("切片方式");
  fireEvent.change(screen.getByLabelText("开始时间 1"), { target: { value: "12" } });
  fireEvent.click(screen.getByLabelText("高光自动切片"));
  fireEvent.change(screen.getByLabelText("最多导出片段数"), { target: { value: "2" } });
  fireEvent.click(screen.getByLabelText("指定时间段"));
  expect(screen.getByLabelText("开始时间 1")).toHaveValue("12");
  fireEvent.click(screen.getByLabelText("高光自动切片"));
  fireEvent.click(screen.getByRole("button", { name: "开始处理" }));
  await screen.findByText("测试字幕");
  expect(submitted()).toEqual({ url: "BV1xx411c7mD", ranges: [], highlights: 2, language: "auto" });
});

it("rejects reversed ranges and never starts a job", async () => {
  const submitted = fakeApi();
  mount();
  await waitFor(() => expect(screen.getByRole("button", { name: "开始处理" })).toBeEnabled());
  fireEvent.change(screen.getByLabelText("BV 号"), { target: { value: "BV1xx411c7mD" } });
  openTool("切片方式");
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
  fireEvent.change(screen.getByLabelText("BV 号"), { target: { value: "BV1xx411c7mD" } });
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
  openTool("任务记录");
  expect(within(screen.getByRole("region", { name: "任务记录" })).getByText("已完成")).toBeInTheDocument();
});

it('blocks new jobs while another history job exports subtitles', async () => {
  fakeApi();
  const original = globalThis.fetch;
  vi.stubGlobal('fetch', vi.fn(async (url: string, options?: RequestInit) => {
    if (url.endsWith('/jobs') && !options) return new Response(JSON.stringify([
      {id:'aabbccddeeff',state:'completed',started_at:0,mode:'ranges'},
      {id:'otherjob',state:'completed',started_at:0,mode:'ranges',subtitle_export_busy:true},
    ]));
    return original(url,options);
  }));
  mount();
  await screen.findByText('测试字幕');
  expect(screen.getByRole('button',{name:'已有任务处理中'})).toBeDisabled();
  expect(screen.getByLabelText('BV 号')).toBeDisabled();
});

it('allows retry and editing after a subtitle export was interrupted', async () => {
  fakeApi();
  const original = globalThis.fetch;
  const posts: string[] = [];
  vi.stubGlobal('fetch', vi.fn(async (url: string, options?: RequestInit) => {
    if (options?.method === 'POST') posts.push(url);
    if (url.endsWith('/jobs') && !options) return new Response(JSON.stringify([{id:'aabbccddeeff',state:'completed',started_at:0,mode:'ranges'}]));
    if (url.endsWith('/subtitle-settings')) return new Response(JSON.stringify({style:defaultStyle,templates:[],arctime_templates:[],burn_available:true,native_handoff_available:false}));
    if (url.endsWith('/subtitle-document')) return new Response(JSON.stringify(documentFixture()));
    if (url.endsWith('/subtitle-exports')) return new Response(JSON.stringify({active:{state:'interrupted',message:'字幕导出已中断，请重新导出',error:null},outputs:[]}));
    return original(url, options);
  }));
  mount();
  await within(screen.getByRole('region',{name:'处理进度'})).findByText('字幕导出已中断，请重新导出');
  expect(screen.getByRole('button',{name:'开始处理'})).toBeEnabled();
  openTool("字幕样式");
  expect(screen.getByLabelText('本条原文')).toBeEnabled();
  openTool("导出");
  const retry = screen.getByRole('button',{name:'导出 ASS'});
  expect(retry).toBeEnabled();
  fireEvent.click(retry);
  await waitFor(()=>expect(posts).toContain('/companion-api/jobs/aabbccddeeff/subtitle-export'));
});
it('exports the selected task snapshot ArcTime binding without using a design template draft',async()=>{
 fakeApi();const original=globalThis.fetch;const posts:Record<string,unknown>[]=[];
 vi.stubGlobal('fetch',vi.fn(async(url:string,options?:RequestInit)=>{
  if(options?.method==='POST'){posts.push(JSON.parse(String(options.body)));return new Response('{}');}
  if(url.endsWith('/jobs'))return new Response(JSON.stringify([{id:'aabbccddeeff',state:'completed',started_at:0,mode:'ranges'}]));
  if(url.endsWith('/subtitle-settings'))return new Response(JSON.stringify({style:defaultStyle,templates:[],arctime_templates:[{id:'bound-project',name:'绑定工程'}],burn_available:true}));
  if(url.endsWith('/subtitle-document'))return new Response(JSON.stringify(documentFixture()));
  if(url.endsWith('/subtitle-exports'))return new Response(JSON.stringify({active:null,outputs:[]}));
  const response=await original(url,options);
  if(url.endsWith('/jobs/aabbccddeeff'))return new Response(JSON.stringify({...await response.json(),state:'completed',subtitle_template:{name:'固定模板',style:defaultStyle,arctime_template_id:'bound-project'}}));
  return response;
 }));
 mount();openTool('导出');
 await waitFor(()=>expect(screen.getByRole('button',{name:'导出 ArcTime ZIP'})).toBeEnabled());
 fireEvent.click(screen.getByRole('button',{name:'导出 ArcTime ZIP'}));
 await waitFor(()=>expect(posts[0]).toMatchObject({kind:'arctime',arctime_template_id:'bound-project'}));
});
