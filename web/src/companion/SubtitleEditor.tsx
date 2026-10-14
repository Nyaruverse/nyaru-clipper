import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { defaultStyle, subtitleApi, type SubtitleSettings, type SubtitleStyle, type TextStyle, type StyleTemplate } from './subtitleStyle';
interface Props { settings?: SubtitleSettings; error: Error | null; style: SubtitleStyle; onStyle: (style: SubtitleStyle) => void; project: string | null; onProject: (id: string | null) => void; busy: boolean }
export function SubtitleEditor({settings,error,style,onStyle,project,onProject,busy}: Props) {
  const client = useQueryClient();
  const [selected,setSelected] = useState('');
  const [name,setName] = useState('我的字幕样式');
  const [confirmation,setConfirmation] = useState<'rename' | 'delete' | 'project' | null>(null);
  const [notice,setNotice] = useState('');
  const [projectName,setProjectName] = useState('');
  const [savedTemplate,setSavedTemplate] = useState<StyleTemplate | null>(null);
  const templates = settings?.templates ?? [];
  const choices = savedTemplate && !templates.some(item => item.id === savedTemplate.id) ? [...templates,savedTemplate] : templates;
  const template = choices.find(item => item.id === selected);
  const mutation = useMutation({mutationFn: ({path,body}: {path:string;body:object | File}) => subtitleApi<Partial<StyleTemplate>>(path,body),onSuccess: async (result,request) => {
    if ((request.path === '/style-templates' || request.path === '/style-templates/import') && result.id && result.name && result.style) {
      const saved = {id:result.id,name:result.name,style:result.style,arctime_template_id:result.arctime_template_id ?? null,builtin:!!result.builtin};
      setSavedTemplate(saved);setSelected(saved.id);setName(saved.name);onProject(saved.arctime_template_id);onStyle(saved.style);
    }
    if (request.path === `/style-templates/${selected}/delete`) {setSelected('');setSavedTemplate(null);}
    setConfirmation(null);setNotice('已保存');await client.invalidateQueries({queryKey:['companion','subtitle-settings']});}});
  const save = (id?: string) => mutation.mutate({path:'/style-templates',body:{...(id ? {id}:{}),name,style,arctime_template_id:project}});
  const disabled = busy || mutation.isPending || !settings?.style;
  const update = (key:'original'|'translation',patch:Partial<TextStyle>) => onStyle({...style,[key]:{...style[key],...patch}});
  return <details className="companion-panel subtitle-editor"><summary>字幕样式与模板</summary>
    {(error || mutation.error) && <p role="alert" className="companion-error">{(mutation.error ?? error)?.message}</p>}
    {notice && <p role="status">{notice}</p>}
    <fieldset disabled={disabled}>
      <label className="ny-field">样式模板<select className="ny-input" value={selected} onChange={event => { const id = event.target.value;setSelected(id);const item = choices.find(value => value.id === id);if (item) {onStyle(item.style);onProject(item.arctime_template_id);setName(item.name);}}}><option value="">当前自定义样式</option>{choices.map(item => <option key={item.id} value={item.id}>{item.name}{item.builtin ? ' · 内置' : ''}</option>)}</select></label>
      <div className="subtitle-style-columns">{(['original','translation'] as const).map(key => <fieldset key={key}><legend>{key === 'original' ? '原文' : '译文'}</legend>
        <label className="ny-field">{key === 'original' ? '原文' : '译文'}字体<input className="ny-input" maxLength={100} value={style[key].font} onChange={event => { if (!/[,{}\\\x00-\x1f\x7f-\x9f]/.test(event.target.value)) update(key,{font:event.target.value}); }} /></label>
        {([{key:'size',label:'字号',min:8,max:200,step:1},{key:'outline',label:'描边',min:0,max:20,step:1},{key:'background_opacity',label:'背景不透明度',min:0,max:1,step:0.05},{key:'margin',label:'垂直边距',min:0,max:1080,step:1}] as const).map(field => <label className="ny-field" key={field.key}>{key === 'original' ? '原文' : '译文'}{field.label}<input className="ny-input" type="number" min={field.min} max={field.max} step={field.step} value={style[key][field.key]} onChange={event => { const value = event.target.valueAsNumber;if (Number.isFinite(value)) update(key,{[field.key]:Math.max(field.min,Math.min(field.max,value))}); }} /></label>)}
        {([{key:'color',label:'文字颜色'},{key:'outline_color',label:'描边颜色'},{key:'background_color',label:'背景颜色'}] as const).map(field => <label className="ny-field" key={field.key}>{key === 'original' ? '原文' : '译文'}{field.label}<input className="ny-input" type="color" value={style[key][field.key]} onChange={event => update(key,{[field.key]:event.target.value})} /></label>)}
        <label className="ny-field">{key === 'original' ? '原文' : '译文'}位置<select className="ny-input" value={style[key].position} onChange={event => update(key,{position:event.target.value === 'top' ? 'top' : 'bottom'})}><option value="bottom">底部</option><option value="top">顶部</option></select></label>
      </fieldset>)}</div>
      <p className="companion-footnote">字号和边距按 1080 高画布缩放。字体取决于本机安装情况；浏览器与烧录的字形可能略有差异。</p>
      <label className="ny-field">模板名称<input className="ny-input" maxLength={100} value={name} onChange={event => setName(event.target.value)} /></label>
      {template && <p className="companion-muted">已选模板：{template.name}。名称和样式修改后需更新或另存；JSON 下载为已保存版本。</p>}
      <div className="companion-downloads"><button className="ny-button" onClick={() => onStyle(defaultStyle)}>恢复基础样式</button><button className="ny-button" disabled={!name.trim()} onClick={() => save()}>另存为新模板</button><button className="ny-button" disabled={!template} onClick={() => {mutation.mutate({path:'/style-templates',body:{name:`${name} 副本`,style,arctime_template_id:project}});}}>复制模板</button><button className="ny-button" disabled={!template || template.builtin || !name.trim()} onClick={() => setConfirmation('rename')}>更新 / 重命名模板</button><button className="ny-button" disabled={!template || template.builtin} onClick={() => setConfirmation('delete')}>删除样式模板</button>{template && <a className="ny-button" href={`/companion-api/style-templates/${template.id}/download`}>导出样式 JSON</a>}<button className="ny-button" onClick={() => mutation.mutate({path:'/subtitle-settings',body:{style}})}>设为默认样式</button></div>
      <label className="ny-field">导入样式 JSON<input type="file" accept=".json,application/json" onChange={event => {const file=event.target.files?.[0];if(file) mutation.mutate({path:'/style-templates/import',body:file});event.target.value='';}} /></label>
      <label className="ny-field">绑定 ArcTime 工程模板<select className="ny-input" value={project ?? ''} onChange={event => onProject(event.target.value || null)}><option value="">不附带工程模板</option>{settings?.arctime_templates?.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
      <label className="ny-field">工程模板名称（留空使用文件名）<input className="ny-input" maxLength={100} value={projectName} onChange={event => setProjectName(event.target.value)} /></label>
      <label className="ny-field">导入 ArcTime ATPJ<input type="file" accept=".atpj" onChange={event => {const file=event.target.files?.[0];if(file) mutation.mutate({path:`/arctime-templates?name=${encodeURIComponent(projectName.trim() || file.name.replace(/\.atpj$/i,''))}&filename=${encodeURIComponent(file.name)}`,body:file});event.target.value='';}} /></label>
      {project && <div className="companion-downloads"><a className="ny-button" href={`/companion-api/arctime-templates/${project}/download`}>下载工程模板</a><button className="ny-button" onClick={() => setConfirmation('project')}>删除工程模板</button></div>}
      {confirmation && <div role="group" aria-label="确认模板操作" className="companion-error"><p>{confirmation === 'rename' ? `更新模板为“${name}”并保存当前样式与绑定？` : '确认删除此模板？已导出的文件不受影响。'}</p><button className="ny-button" onClick={() => {if(confirmation === 'rename') save(selected);else if(confirmation === 'delete') mutation.mutate({path:`/style-templates/${selected}/delete`,body:{}});else mutation.mutate({path:`/arctime-templates/${project}/delete`,body:{}},{onSuccess:()=>onProject(null)});}}>确认</button><button className="ny-button" onClick={() => setConfirmation(null)}>取消</button></div>}
    </fieldset>
  </details>;
}
