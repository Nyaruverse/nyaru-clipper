import { useEffect, useRef, useState, type ReactNode } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { subtitleApi, type SubtitleSettings } from './subtitleStyle';
import { defaultWorkflow, parseStudioDefaults, type StudioDefaults } from './studioModel';
import { WorkflowFields } from './WorkflowFields';
import type { CompanionConfig } from './companionApi';
const categories=['通用','AI与翻译','识别与处理','字幕与模板','文件与导出','运行环境'] as const;
export type SettingsCategory=typeof categories[number];
interface Props {readonly open:boolean;readonly category:SettingsCategory;readonly onCategory:(category:SettingsCategory)=>void;readonly defaults?:StudioDefaults;readonly error:Error|null;readonly settings?:SubtitleSettings;readonly config?:CompanionConfig;readonly ai:ReactNode;readonly templates:ReactNode;readonly onDirty:(dirty:boolean)=>void}
export function StudioSettings({open,category,onCategory,defaults,error,settings,config,ai,templates,onDirty}:Props){
 const client=useQueryClient();const [draft,setDraft]=useState<StudioDefaults|null>(null);const heading=useRef<HTMLHeadingElement>(null);
 const value=draft??defaults??{...defaultWorkflow,default_template_id:null};const dirty=draft!==null&&JSON.stringify(draft)!==JSON.stringify(defaults);
 useEffect(()=>onDirty(dirty),[dirty,onDirty]);useEffect(()=>{if(open)heading.current?.focus();},[open,category]);
 const save=useMutation({mutationFn:async(submitted:StudioDefaults)=>parseStudioDefaults(await subtitleApi<unknown>('/studio-settings',submitted)),onSuccess:(result,submitted)=>{client.setQueryData(['companion','studio-settings'],result);setDraft(current=>current===submitted?null:current);}});
 return <main className="studio-settings" hidden={!open}>
 <nav aria-label="设置分类"><h2>设置中心</h2>{categories.map(item=><button className="ny-button" key={item} aria-current={category===item?'page':undefined} onClick={()=>onCategory(item)}>{item}</button>)}<p className="companion-footnote">全局默认 · 用于新任务<br/>更改不会覆盖已有任务。</p></nav>
 <div className="studio-settings-content"><p className="companion-muted">设置中心 › 软件默认设置</p><h1 ref={heading} tabIndex={-1}>{category}</h1>
 <section className="companion-panel" hidden={category!=='通用'}><h2>新任务默认模板</h2><label className="ny-field">默认工作模板<select className="ny-input" value={value.default_template_id??''} onChange={e=>setDraft({...value,default_template_id:e.target.value||null})}><option value="">不自动套用样式</option>{settings?.templates?.map(item=><option key={item.id} value={item.id}>{item.name}</option>)}</select></label><p className="companion-footnote">浅色创作工作台。任务保存创建时的模板快照。</p></section>
 <section className="companion-panel" hidden={category!=='AI与翻译'}>{ai}</section>
 <section className="companion-panel" hidden={category!=='识别与处理'}><WorkflowFields section="processing" value={value} onChange={next=>setDraft({...value,...next})}/></section>
 <section className="companion-panel" hidden={category!=='字幕与模板'}>{templates}</section>
 <section className="companion-panel" hidden={category!=='文件与导出'}><h2>导出能力</h2><p>字幕烧录：{settings?.burn_available?'可用':'不可用'}</p><p>原生 ArcTime 工程：{settings?.native_handoff_available?'可用':'不可用'}</p><p className="companion-footnote">文件通过任务导出面板下载，保存位置由浏览器或系统下载设置决定。</p><WorkflowFields section="export" prefix="导出任务" value={value} onChange={next=>setDraft({...value,...next})}/></section>
 <section className="companion-panel" hidden={category!=='运行环境'}><h2>{config?.ready?'本地引擎就绪':'本地环境尚未就绪'}</h2><p>{config?.missing?.length?`缺少：${config.missing.join('、')}`:'未报告缺少的运行组件'}</p><p>默认 AI：{config?.llm_provider??'DeepSeek'} · {config?.llm_model??config?.translation_model??'未配置'}</p></section>
 {(error||save.error)&&<p role="alert" className="companion-error">{(save.error??error)?.message}</p>}
 <footer className="studio-settings-footer"><span role="status">{save.isPending?'正在保存…':dirty?'有未保存的默认设置':'默认设置已保存'}</span><button className="ny-button" disabled={!dirty||save.isPending} onClick={()=>setDraft(null)}>取消更改</button><button className="ny-button ny-button--primary" disabled={!dirty||!defaults||save.isPending} onClick={()=>save.mutate(value)}>保存更改</button></footer>
 </div></main>;
}
