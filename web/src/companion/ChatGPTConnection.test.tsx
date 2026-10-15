import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { Companion } from "./Companion";
import type { ChatGPTStatus } from "./companionApi";

const disconnected = {connected:false,sharing:false,account_label:null,error:null,manage_url:"https://chatgpt.com/#settings",authorization_pending:false};
const connected = {...disconnected,connected:true,sharing:true,account_label:"Test account"};
function setup(options: {status?: typeof disconnected | typeof connected; loginError?: string; busy?: boolean; expired?: boolean; provider?: string; key?: boolean; keyError?: string; taskModel?: string; saoziModel?: string} = {}) {
  let status: ChatGPTStatus = options.status ?? disconnected;
  let provider = options.provider ?? "chatgpt";
  let model = "account-model";
  let catalog = [{slug:"account-model",display_name:"Account Model"},{slug:"another-model",display_name:"Another Model"}];
  let statusReads = 0;
  const posts: {url:string;body:unknown}[] = [];
  const job = {id:"saved-task",state:options.busy ? "recording" : "completed",mode:"saozi",message:"保存的任务",started_at:0,
    has_source:false,clips:[],segments:[],saozi_model:options.saoziModel,translation:{state:options.taskModel || options.saoziModel ? "interrupted" : "completed",model:options.saoziModel ? undefined : options.taskModel ?? "chatgpt:saved-model",done:0,total:0,error:null}};
  vi.stubGlobal("fetch", vi.fn(async (url:string, request?:RequestInit) => {
    if (request?.method === "POST") {
      const body = JSON.parse(String(request.body));
      posts.push({url,body});
      if (url.endsWith("/login")) {
        if (!options.loginError) status = {...status,authorization_pending:true};
        return new Response(JSON.stringify(options.loginError ? {detail:options.loginError} : {url:"https://auth.openai.com/oauth/authorize?state=test-state"}),{status:options.loginError ? 400 : 200});
      }
      if (url.endsWith("/llm-config")) {provider = body.provider;model = body.model;}
      if (url.endsWith("/logout")) status = disconnected;
      return new Response(JSON.stringify(status));
    }
    if (url.endsWith("/config")) return new Response(JSON.stringify({ready:true,missing:[],translation_configured:!!options.key,translation_config_error:options.keyError,translation_model:"deepseek-flash",
      llm_provider:provider,llm_model:model,llm_configured:provider === "chatgpt" ? status.connected && status.sharing : !!options.key && !options.keyError,chatgpt:status}));
    if (url.endsWith("/chatgpt")) {statusReads++;return new Response(JSON.stringify(options.expired ? {...disconnected,error:"登录已过期，请重新授权"} : status));}
    if (url.endsWith("/models")) return new Response(JSON.stringify(catalog));
    if (url.endsWith("/jobs")) return new Response(JSON.stringify([job]));
    return new Response(JSON.stringify(job));
  }));
  const client = new QueryClient({defaultOptions:{queries:{retry:false},mutations:{retry:false}}});
  render(<QueryClientProvider client={client}><Companion /></QueryClientProvider>);
  fireEvent.click(screen.getByRole("button", {name:"AI 设置"}));
  return {posts,statusReads:()=>statusReads,unrelatedError:()=>{status={...status,error:"回调未匹配，当前授权仍待完成"};},connect:(replaceModels=false)=>{
    status=connected;
    if (replaceModels) catalog=[{slug:"new-model",display_name:"New Model"}];
  }};
}
afterEach(()=>vi.unstubAllGlobals());

it("offers an official user-activated login link and polls connection to refresh account models", async () => {
  const {connect} = setup();
  fireEvent.click(await screen.findByRole("button",{name:"Continue with ChatGPT"}));
  const link = await screen.findByRole("link",{name:"在浏览器中继续登录"});
  expect(link).toHaveAttribute("href","https://auth.openai.com/oauth/authorize?state=test-state");
  expect(link).toHaveAttribute("target","_blank");
  expect(screen.queryByLabelText("DeepSeek API Key")).toBeNull();
  connect();
  await waitFor(()=>expect(screen.getByText("Test account")).toBeVisible(),{timeout:5000});
  expect(await screen.findByRole("option",{name:"Account Model"})).toBeVisible();
  expect(screen.queryByRole("link",{name:"在浏览器中继续登录"})).toBeNull();
  expect(screen.getByRole("link",{name:"管理用量"})).toHaveAttribute("href",connected.manage_url);
});

it("shows missing plan sharing and disables account model saving", async () => {
  const {posts} = setup({status:{...connected,sharing:false}});
  expect(await screen.findByText(/尚未授权共享订阅额度/)).toBeVisible();
  expect(screen.getByRole("button",{name:"保存供应商与模型"})).toBeDisabled();
  expect(screen.queryByRole("option",{name:"Account Model"})).toBeNull();
  fireEvent.click(screen.getByRole("button", {name:"切片方式"}));
  fireEvent.click(screen.getByRole("radio",{name:"臊子"}));
  fireEvent.click(screen.getByRole("button", {name:"新建任务"}));
  fireEvent.change(screen.getByLabelText("视频链接"),{target:{value:"https://example.org/video.mp4"}});
  fireEvent.click(screen.getByRole("button",{name:"开始处理"}));
  expect(await screen.findByText("臊子需要先连接 ChatGPT、授权订阅额度并保存可用模型")).toBeVisible();
  expect(posts).toEqual([]);
});

it("persists raw account model and provider while retaining the current task model", async () => {
  const {posts} = setup({status:connected});
  await screen.findByRole("option",{name:"Another Model"});
  fireEvent.change(screen.getByLabelText("翻译模型"),{target:{value:"another-model"}});
  fireEvent.click(screen.getByRole("button",{name:"保存供应商与模型"}));
  await waitFor(()=>expect(posts).toContainEqual({url:"/companion-api/llm-config",body:{provider:"chatgpt",model:"another-model"}}));
  expect(screen.getByText("当前任务模型：chatgpt:saved-model")).toBeVisible();
  fireEvent.change(screen.getByLabelText("AI 供应商"),{target:{value:"deepseek"}});
  fireEvent.click(screen.getByRole("button",{name:"保存供应商与模型"}));
  await waitFor(()=>expect(posts).toContainEqual({url:"/companion-api/llm-config",body:{provider:"deepseek",model:"deepseek-flash"}}));
  expect(screen.getByText("当前任务模型：chatgpt:saved-model")).toBeVisible();
});

it("shows failed login without opening a link", async () => {
  setup({loginError:"授权服务暂不可用"});
  fireEvent.click(await screen.findByRole("button",{name:"Continue with ChatGPT"}));
  expect(await screen.findByText("授权服务暂不可用")).toBeVisible();
  expect(screen.queryByRole("link",{name:"在浏览器中继续登录"})).toBeNull();
});

it("shows expired session recovery and keeps logout disabled during a busy task", async () => {
  setup({status:connected,busy:true,expired:true});
  expect(await screen.findByText("登录已过期，请重新授权")).toBeVisible();
  expect(screen.getByRole("button",{name:"退出 ChatGPT"})).toBeDisabled();
  expect(screen.getByRole("button",{name:"Continue with ChatGPT"})).toBeDisabled();
});

it("uses ChatGPT readiness for Saozi even when no DeepSeek key exists", async () => {
  setup({status:connected});
  await screen.findByRole("option",{name:"Account Model"});
  fireEvent.click(screen.getByRole("button", {name:"切片方式"}));
  fireEvent.click(screen.getByRole("radio",{name:"臊子"}));
  expect(screen.getByText(/ChatGPT 根据字幕段落选择切点/)).toBeVisible();
  fireEvent.click(screen.getByRole("button", {name:"新建任务"}));
  fireEvent.change(screen.getByLabelText("视频链接"),{target:{value:"https://example.org/video.mp4"}});
  fireEvent.click(screen.getByRole("button",{name:"开始处理"}));
  await waitFor(()=>expect(globalThis.fetch).toHaveBeenCalledWith("/companion-api/jobs",expect.objectContaining({method:"POST"})));
  expect(screen.queryByText(/需要先保存 DeepSeek/)).toBeNull();
});

it("logs out without credentials in the request and removes account models", async () => {
  const {posts} = setup({status:connected});
  await screen.findByRole("option",{name:"Account Model"});
  fireEvent.click(screen.getByRole("button",{name:"退出 ChatGPT"}));
  await waitFor(()=>expect(posts).toEqual([{url:"/companion-api/chatgpt/logout",body:{}}]));
  expect(await screen.findByText("ChatGPT 未连接")).toBeVisible();
  expect(screen.queryByRole("option",{name:"Account Model"})).toBeNull();
  expect(screen.getByRole("button",{name:"保存供应商与模型"})).toBeDisabled();
});

it("settles same-account reconnect only after pending authorization ends and replaces cached models", async () => {
  const {connect,statusReads} = setup({status:connected});
  await screen.findByRole("option",{name:"Another Model"});
  fireEvent.change(screen.getByLabelText("翻译模型"),{target:{value:"another-model"}});
  const before = statusReads();
  fireEvent.click(screen.getByRole("button",{name:"Continue with ChatGPT"}));
  expect(await screen.findByRole("link",{name:"在浏览器中继续登录"})).toBeVisible();
  expect(statusReads()).toBeGreaterThan(before);
  expect(screen.getByText("Test account")).toBeVisible();
  connect(true);
  await waitFor(()=>expect(screen.queryByRole("link",{name:"在浏览器中继续登录"})).toBeNull(),{timeout:5000});
  expect(await screen.findByRole("option",{name:"New Model"})).toBeVisible();
  expect(screen.queryByRole("option",{name:"Another Model"})).toBeNull();
  expect(screen.getByLabelText("翻译模型")).toHaveValue("");
  expect(screen.getByRole("button",{name:"保存供应商与模型"})).toBeDisabled();
});

it.each([
  {name:"saved ChatGPT ready despite unset default Flash key",provider:"deepseek",status:connected,key:false,taskModel:"chatgpt:saved-model",ready:true},
  {name:"saved Flash ready despite disconnected default ChatGPT",provider:"chatgpt",status:disconnected,key:true,taskModel:"deepseek-flash",ready:true},
  {name:"saved ChatGPT blocked despite ready default Flash",provider:"deepseek",status:disconnected,key:true,taskModel:"chatgpt:saved-model",ready:false},
  {name:"saved Flash blocked despite ready default ChatGPT",provider:"chatgpt",status:connected,key:false,taskModel:"deepseek-flash",ready:false},
  {name:"saved Flash blocked by unhealthy key configuration",provider:"chatgpt",status:connected,key:true,keyError:"配置不可用",taskModel:"deepseek-flash",ready:false},
  {name:"saved Saozi ChatGPT model ready despite unset default Flash key",provider:"deepseek",status:connected,key:false,saoziModel:"chatgpt:saved-model",ready:true},
])("$name", async ({ready,name: _name,...options}) => {
  const {posts} = setup(options);
  const button = await screen.findByRole("button",{name:"继续生成中日双语字幕"});
  if (ready) {
    expect(button).toBeEnabled();
    fireEvent.click(button);
    await waitFor(()=>expect(posts).toContainEqual({url:"/companion-api/jobs/saved-task/translate",body:{}}));
  } else {
    expect(button).toBeDisabled();
    fireEvent.click(button);
    expect(posts).toEqual([]);
  }
});

it("identifies the saved provider while settings have an unsaved provider choice", async () => {
  setup({status:connected});
  await screen.findByRole("option",{name:"Account Model"});
  fireEvent.change(screen.getByLabelText("AI 供应商"),{target:{value:"deepseek"}});
  expect(screen.getByText("已保存的供应商：ChatGPT 订阅")).toBeVisible();
  expect(screen.getByText("供应商选择尚未保存")).toBeVisible();
});

it("keeps the login link when an unrelated callback fails while authorization is pending", async () => {
  const {unrelatedError} = setup({status:connected});
  await screen.findByRole("option",{name:"Account Model"});
  fireEvent.click(screen.getByRole("button",{name:"Continue with ChatGPT"}));
  await screen.findByRole("link",{name:"在浏览器中继续登录"});
  unrelatedError();
  await waitFor(()=>expect(screen.getByText("回调未匹配，当前授权仍待完成")).toBeVisible(),{timeout:5000});
  expect(screen.getByRole("link",{name:"在浏览器中继续登录"})).toBeVisible();
});
