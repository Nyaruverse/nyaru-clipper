import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ChatGPTConnection } from "./ChatGPTConnection";
import { api, type CompanionConfig, type LlmProvider } from "./companionApi";

export function LlmSettings({config, busy}: {readonly config?: CompanionConfig; readonly busy: boolean}) {
  const client = useQueryClient();
  const [providerDraft, setProviderDraft] = useState<LlmProvider | null>(null);
  const [apiKey, setApiKey] = useState("");
  const provider = providerDraft ?? config?.llm_provider ?? "deepseek";
  const refresh = () => client.invalidateQueries({queryKey:["companion","config"]});
  const key = useMutation({mutationFn:()=>api("/translation-config",{api_key:apiKey.trim()}),
    onSuccess:async()=>{setApiKey("");await refresh();}});
  const save = useMutation({mutationFn:()=>api("/llm-config",{provider:"deepseek",model:"deepseek-flash"}),onSuccess:refresh});
  const savedFlash = (config?.llm_provider ?? "deepseek") === "deepseek" && (config?.llm_model ?? config?.translation_model) === "deepseek-flash";

  return <div className="companion-llm-settings">
    <label className="ny-field">AI 供应商<select className="ny-input" value={provider} onChange={event=>{
      if (event.target.value === "deepseek" || event.target.value === "chatgpt") setProviderDraft(event.target.value);
    }}><option value="deepseek">DeepSeek Flash</option><option value="chatgpt">ChatGPT 订阅</option></select></label>
    {config && <p className="companion-footnote">已保存的供应商：{config.llm_provider === "chatgpt" ? "ChatGPT 订阅" : "DeepSeek Flash"}</p>}
    {provider !== (config?.llm_provider ?? "deepseek") && <p className="companion-footnote" role="status">供应商选择尚未保存</p>}
    <p className="companion-muted">只发送字幕文字与切点候选，会使用{provider === "chatgpt" ? "你的 ChatGPT 订阅额度" : "你的 DeepSeek API 额度"}。视频和识别在本机完成。</p>
    {provider === "chatgpt" ? <ChatGPTConnection config={config} busy={busy} /> : <>
      <form onSubmit={event=>{event.preventDefault();key.mutate();}}>
        <label className="ny-field">DeepSeek API Key<input className="ny-input" type="password" autoComplete="off" value={apiKey} onChange={event=>setApiKey(event.target.value)} placeholder="保存后重启自动加载" /></label>
        <button className="ny-button" type="submit" disabled={!apiKey.trim() || key.isPending || save.isPending}>保存 Key 到配置文件</button>
      </form>
      <p className="companion-footnote">{config?.translation_configured ? "Key 已保存 · 重启自动加载" : "Key 尚未设置 · 保存到 runs/config.json"}</p>
      <form onSubmit={event=>{event.preventDefault();save.mutate();}}>
        <label className="ny-field">翻译模型<select className="ny-input" value="deepseek-flash" disabled><option value="deepseek-flash">DeepSeek Flash</option></select></label>
        <button className="ny-button" type="submit" disabled={!config || savedFlash || save.isPending || key.isPending}>保存供应商与模型</button>
      </form>
      {(key.error || save.error || config?.translation_config_error) && <p className="companion-error" role="alert">{key.error?.message ?? save.error?.message ?? config?.translation_config_error}</p>}
    </>}
    <p className="companion-footnote">供应商与模型保存后用于新任务；当前任务继续使用创建时的设置。</p>
  </div>;
}
