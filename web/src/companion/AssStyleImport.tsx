import { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { subtitleApi, type StyleTemplate, type TextStyle } from './subtitleStyle';

interface Inspection {readonly styles: readonly {readonly name: string; readonly style: TextStyle}[]; readonly warnings: readonly string[]}
interface Props {readonly disabled: boolean; readonly onImported: (template: StyleTemplate) => void}

export function AssStyleImport({disabled,onImported}: Props) {
  const [inspection,setInspection] = useState<Inspection | null>(null);
  const [original,setOriginal] = useState('');
  const [translation,setTranslation] = useState('');
  const [name,setName] = useState('');
  const inspect = useMutation({mutationFn:(file:File)=>subtitleApi<Inspection>('/style-templates/inspect-ass',file),onSuccess:(result,file)=>{
    setInspection(result);setOriginal(result.styles[0]?.name ?? '');setTranslation(result.styles[1]?.name ?? result.styles[0]?.name ?? '');setName(file.name.replace(/\.ass$/i,''));
  }});
  const save = useMutation({mutationFn:()=>subtitleApi<StyleTemplate>('/style-templates',{name,style:{version:1,
    original:inspection?.styles.find(item=>item.name===original)?.style,
    translation:inspection?.styles.find(item=>item.name===translation)?.style}}),onSuccess:(template)=>{onImported(template);setInspection(null);}});
  return <fieldset disabled={disabled || inspect.isPending || save.isPending}>
    <legend>从 ArcTime ASS 导入样式</legend>
    <label className="ny-field">导入 ArcTime ASS 样式<input type="file" accept=".ass" onChange={event=>{
      const file=event.target.files?.[0];event.target.value='';setInspection(null);save.reset();if(file) inspect.mutate(file);
    }}/></label>
    {inspect.isPending && <p role="status">正在读取 ASS 样式…</p>}
    {(inspect.error || save.error) && <p role="alert" className="companion-error">{inspect.error?.message ?? save.error?.message}</p>}
    {inspection && <>
      {inspection.warnings.map(warning=><p className="companion-footnote" key={warning}>{warning}</p>)}
      <label className="ny-field">ASS 模板名称<input className="ny-input" maxLength={100} value={name} onChange={event=>setName(event.target.value)}/></label>
      <label className="ny-field">ASS 原文样式<select className="ny-input" value={original} onChange={event=>setOriginal(event.target.value)}>{inspection.styles.map(item=><option key={item.name}>{item.name}</option>)}</select></label>
      <label className="ny-field">ASS 译文样式<select className="ny-input" value={translation} onChange={event=>setTranslation(event.target.value)}>{inspection.styles.map(item=><option key={item.name}>{item.name}</option>)}</select></label>
      <p className="companion-muted">按字幕用途选择样式。只有一个样式时可供两种语言共用；保存后可在新建实时录播任务中选择。</p>
      <button className="ny-button" type="button" disabled={!name.trim() || !original || !translation} onClick={()=>save.mutate()}>保存 ASS 为样式模板</button>
    </>}
  </fieldset>;
}
