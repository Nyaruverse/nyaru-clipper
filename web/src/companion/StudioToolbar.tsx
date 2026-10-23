import { ArrowDownToLine, History, Plus, Scissors, Settings, Sun, Pencil, ArrowLeft } from 'lucide-react';
export type StudioMode = 'daily' | 'design';
interface Props { readonly mode:StudioMode; readonly onMode:(mode:StudioMode)=>void; readonly settings:boolean; readonly onSettings:()=>void; readonly onBack:()=>void; readonly onCreate:()=>void; readonly onHistory:()=>void; readonly onPrimary:()=>void; readonly tool:string|null }
export function StudioToolbar({mode,onMode,settings,onSettings,onBack,onCreate,onHistory,onPrimary,tool}:Props) {
 return <header className="studio-toolbar">
  <div className="companion-brand"><Scissors size={22}/><span>NYARU<small>LOCAL CREATIVE STUDIO</small></span></div>
  <div className={`studio-modes ${mode}`} role="tablist" aria-label="工作模式" onKeyDown={event=>{if(['ArrowLeft','ArrowRight','Home','End'].includes(event.key)){event.preventDefault();const next=event.key==='Home'?'daily':event.key==='End'?'design':mode==='daily'?'design':'daily';onMode(next);event.currentTarget.querySelector<HTMLButtonElement>(`[data-mode="${next}"]`)?.focus();}}}>
   {([{id:'daily',label:'日常模式',Icon:Sun},{id:'design',label:'模板设计',Icon:Pencil}] as const).map(({id,label,Icon})=><button key={id} data-mode={id} role="tab" aria-selected={mode===id} tabIndex={mode===id?0:-1} onClick={()=>onMode(id)}><Icon size={16}/>{label}</button>)}
  </div>
  <nav className="studio-actions" aria-label="工作台工具">{settings?<button className="ny-button" onClick={onBack}><ArrowLeft size={16}/>返回工作区</button>:<>
   <button className="ny-button ny-button--quiet" aria-expanded={tool==='create'} onClick={onCreate}><Plus size={16}/>新建任务</button>
   <button className="ny-button ny-button--quiet" aria-label="任务记录" aria-expanded={tool==='history'} onClick={onHistory}><History size={16}/></button>
   <button className="ny-button ny-button--quiet" aria-label="设置" onClick={onSettings}><Settings size={16}/></button>
   <button className="ny-button ny-button--primary" aria-expanded={tool==='export'} onClick={onPrimary}><ArrowDownToLine size={16}/>{mode==='design'?'保存模板':'导出'}</button>
  </>}</nav>
 </header>;
}
