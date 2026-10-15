import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, type ChatGPTModel, type ChatGPTStatus, type CompanionConfig } from "./companionApi";

export function ChatGPTConnection({config, busy}: {readonly config?: CompanionConfig; readonly busy: boolean}) {
  const client = useQueryClient();
  const [loginUrl, setLoginUrl] = useState<string | null>(null);
  const authorizationPending = useRef(false);
  const [modelDraft, setModelDraft] = useState<string | null>(null);
  const status = useQuery({queryKey:["companion","chatgpt"],queryFn:()=>api<ChatGPTStatus>("/chatgpt"),
    initialData:config?.chatgpt,refetchInterval:query=>loginUrl || query.state.data?.authorization_pending ? 2000 : 15000});
  const account = status.data;
  const permitted = !!account?.connected && !!account.sharing && !status.isError;
  const models = useQuery({queryKey:["companion","chatgpt-models",account?.account_label],
    queryFn:()=>api<ChatGPTModel[]>("/chatgpt/models"),enabled:permitted});
  const model = modelDraft ?? (config?.llm_provider === "chatgpt" ? config.llm_model : "") ?? "";
  const available = permitted && !models.isError && models.data?.some(item=>item.slug === model);
  const login = useMutation({mutationFn:async()=>{
    const result = await api<{url:string}>("/chatgpt/login",{});
    await client.cancelQueries({queryKey:["companion","chatgpt"],exact:true});
    const pending = await api<ChatGPTStatus>("/chatgpt");
    client.setQueryData(["companion","chatgpt"],pending);
    return {...result,authorization_pending:pending.authorization_pending};
  },onMutate:()=>setLoginUrl(null),onSuccess:result=>{
    if (result.authorization_pending) setLoginUrl(result.url);
    else {
      setModelDraft(null);
      void client.invalidateQueries({queryKey:["companion","chatgpt-models"]});
      void client.invalidateQueries({queryKey:["companion","config"]});
    }
  }});
  const logout = useMutation({mutationFn:()=>api<ChatGPTStatus>("/chatgpt/logout",{}),onSuccess:async result=>{
    setLoginUrl(null);setModelDraft(null);
    client.setQueryData(["companion","chatgpt"],result);
    client.removeQueries({queryKey:["companion","chatgpt-models"]});
    await client.invalidateQueries({queryKey:["companion","config"]});
  }});
  const save = useMutation({mutationFn:()=>api("/llm-config",{provider:"chatgpt",model}),
    onSuccess:async()=>{await client.invalidateQueries({queryKey:["companion","config"]});setModelDraft(null);}});

  useEffect(()=>{
    if (authorizationPending.current && !account?.authorization_pending) {
      setLoginUrl(null);setModelDraft(null);
      void client.invalidateQueries({queryKey:["companion","chatgpt-models"]});
      void client.invalidateQueries({queryKey:["companion","config"]});
    }
    authorizationPending.current = !!account?.authorization_pending;
    if (account && (account.connected !== config?.chatgpt?.connected || account.sharing !== config?.chatgpt?.sharing || account.error !== config?.chatgpt?.error)) {
      void client.invalidateQueries({queryKey:["companion","config"]});
    }
  },[account?.connected,account?.sharing,account?.error,account?.authorization_pending,client,config?.chatgpt?.connected,config?.chatgpt?.sharing,config?.chatgpt?.error]);

  return <div className="companion-chatgpt">
    <p role="status">{account?.connected ? account.sharing ? "ChatGPT 已连接 · 已授权订阅额度" : "ChatGPT 已连接 · 尚未授权共享订阅额度，请重新登录授权" : "ChatGPT 未连接"}</p>
    {account?.account_label && <p className="companion-muted">{account.account_label}</p>}
    <div className="companion-downloads">
      <button className="ny-button" type="button" disabled={busy || login.isPending || logout.isPending} onClick={()=>login.mutate()}>{login.isPending ? "正在准备登录…" : "Continue with ChatGPT"}</button>
      {loginUrl && <a className="ny-button" href={loginUrl} target="_blank" rel="noopener noreferrer">在浏览器中继续登录</a>}
      {account?.manage_url && <a className="ny-button" href={account.manage_url} target="_blank" rel="noopener noreferrer">管理用量</a>}
      <button className="ny-button" type="button" disabled={busy || logout.isPending || login.isPending || !account?.connected} onClick={()=>logout.mutate()}>退出 ChatGPT</button>
    </div>
    {loginUrl && <p className="companion-footnote" role="status">请点击链接完成登录；此工作台会自动更新连接状态。</p>}
    {busy && <p className="companion-footnote">任务处理中，暂不能登录或退出 ChatGPT。</p>}
    {[status.error?.message,account?.error,login.error?.message,logout.error?.message,models.error?.message,save.error?.message].filter(Boolean).map((message,index)=><p className="companion-error" role="alert" key={index}>{message}</p>)}
    <form onSubmit={event=>{event.preventDefault();if (available) save.mutate();}}>
      <label className="ny-field">翻译模型<select className="ny-input" value={available ? model : ""} disabled={!permitted || models.isPending || models.isError || save.isPending} onChange={event=>setModelDraft(event.target.value)}>
        <option value="" disabled>{permitted ? models.isPending ? "正在读取账号模型…" : "请选择账号可用模型" : "连接并授权后获取模型"}</option>
        {permitted && models.data?.map(item=><option key={item.slug} value={item.slug}>{item.display_name}</option>)}
      </select></label>
      <button className="ny-button" type="submit" disabled={!available || save.isPending || (config?.llm_provider === "chatgpt" && model === config.llm_model)}>保存供应商与模型</button>
    </form>
    {permitted && !models.isPending && !models.isError && !models.data?.length && <p className="companion-muted">账号尚无可用模型，请检查订阅授权。</p>}
    <p className="companion-footnote">模型列表仅表示账号可见；实际调用仍受订阅权限与剩余额度限制。</p>
  </div>;
}
