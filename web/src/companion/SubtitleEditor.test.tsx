import { useState } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { SubtitleEditor } from './SubtitleEditor';
import { SubtitleExports } from './SubtitleExports';
import { defaultWorkflow } from './studioModel';
import { defaultStyle, type SubtitleSettings } from './subtitleStyle';
const settings: SubtitleSettings = {style:defaultStyle,templates:[{id:'user1',name:'测试模板',style:defaultStyle,builtin:false,arctime_template_id:'project1'}],arctime_templates:[{id:'project1',name:'工程',sha256:'a',size:1}],burn_available:true,native_handoff_available:false};
afterEach(()=>vi.unstubAllGlobals());
function Harness(){const [style,onStyle]=useState(defaultStyle);const [project,onProject]=useState<string|null>(null);return <SubtitleEditor settings={settings} error={null} style={style} onStyle={onStyle} project={project} onProject={onProject} busy={false}/>;}
function mount(content=<Harness/>){return render(<QueryClientProvider client={new QueryClient({defaultOptions:{queries:{retry:false},mutations:{retry:false}}})}>{content}</QueryClientProvider>);}
it('saves current default, copies binding, confirms rename/delete and uploads raw ATPJ', async()=>{
 const requests:{url:string;body:unknown}[]=[];
 vi.stubGlobal('fetch',vi.fn(async(url:string,init:RequestInit)=>{requests.push({url,body:typeof init.body==='string'?JSON.parse(init.body):init.body});return new Response('{}');}));
 mount();fireEvent.click(screen.getByText('字幕样式与模板'));
 fireEvent.change(screen.getByLabelText('原文字号'),{target:{value:'64'}});
 fireEvent.click(screen.getByText('设为默认样式'));
 await waitFor(()=>expect(requests[0]).toEqual({url:'/companion-api/subtitle-settings',body:{style:{...defaultStyle,original:{...defaultStyle.original,size:64}}}}));
 await waitFor(()=>expect(screen.getByLabelText('样式模板')).toBeEnabled());
 fireEvent.change(screen.getByLabelText('样式模板'),{target:{value:'user1'}});
 fireEvent.click(screen.getByText('复制模板'));
 await waitFor(()=>expect(requests[1]).toEqual({url:'/companion-api/style-templates',body:{name:'测试模板 副本',style:defaultStyle,arctime_template_id:'project1',streamer:'',workflow:defaultWorkflow}}));
 await waitFor(()=>expect(screen.getByText('更新 / 重命名模板')).toBeEnabled());
 fireEvent.change(screen.getByLabelText('模板名称'),{target:{value:'改名'}});fireEvent.click(screen.getByText('更新 / 重命名模板'));
 expect(requests).toHaveLength(2);fireEvent.click(screen.getByText('确认'));
 await waitFor(()=>expect(requests[2].body).toMatchObject({id:'user1',name:'改名'}));
 await waitFor(()=>expect(screen.getByText('删除样式模板')).toBeEnabled());fireEvent.click(screen.getByText('删除样式模板'));fireEvent.click(screen.getByText('取消'));expect(requests).toHaveLength(3);
 fireEvent.click(screen.getByText('删除样式模板'));fireEvent.click(screen.getByText('确认'));
 await waitFor(()=>expect(requests[3].url).toBe('/companion-api/style-templates/user1/delete'));
 await waitFor(()=>expect(screen.getByLabelText('导入 ArcTime ATPJ')).toBeEnabled());
 const file=new File(['opaque'],'工程 空格.atpj');fireEvent.change(screen.getByLabelText('导入 ArcTime ATPJ'),{target:{files:[file]}});
 await waitFor(()=>expect(requests[4]).toEqual({url:`/companion-api/arctime-templates?name=${encodeURIComponent('工程 空格')}&filename=${encodeURIComponent(file.name)}`,body:file}));
});
it('surfaces import errors and permits retry without clearing style',async()=>{
 vi.stubGlobal('fetch',vi.fn(async()=>new Response(JSON.stringify({detail:'无效模板 JSON'}),{status:422})));
 mount();fireEvent.click(screen.getByText('字幕样式与模板'));
 fireEvent.change(screen.getByLabelText('导入样式 JSON'),{target:{files:[new File(['bad'],'bad.json')]}});
 expect(await screen.findByRole('alert')).toHaveTextContent('无效模板 JSON');expect(screen.getByLabelText('原文字号')).toHaveValue(48);expect(screen.getByLabelText('导入样式 JSON')).toBeEnabled();
});
it('inspects ASS and saves explicitly mapped original and translation styles',async()=>{
 const original={...defaultStyle.original,size:62,color:'#123456'};
 const translation={...defaultStyle.translation,size:38,color:'#ABCDEF'};
 const posts:{url:string;body:unknown}[]=[];
 vi.stubGlobal('fetch',vi.fn(async(url:string,init:RequestInit)=>{
   posts.push({url,body:typeof init.body==='string'?JSON.parse(init.body):init.body});
   if(url.endsWith('/inspect-ass')) return new Response(JSON.stringify({styles:[{name:'日本語',style:original},{name:'中文',style:translation}],warnings:['逐句动画不会导入']}));
   return new Response(JSON.stringify({id:'ass-template',name:'直播双语',style:{version:1,original,translation},builtin:false,arctime_template_id:null}));
 }));
 mount();fireEvent.click(screen.getByText('字幕样式与模板'));
 const file=new File(['ASS fixture'],'ArcTime.ass');
 fireEvent.change(screen.getByLabelText('导入 ArcTime ASS 样式'),{target:{files:[file]}});
 expect(await screen.findByText('逐句动画不会导入')).toBeVisible();
 fireEvent.change(screen.getByLabelText('ASS 模板名称'),{target:{value:'直播双语'}});
 fireEvent.change(screen.getByLabelText('ASS 原文样式'),{target:{value:'日本語'}});
 fireEvent.change(screen.getByLabelText('ASS 译文样式'),{target:{value:'中文'}});
 fireEvent.click(screen.getByRole('button',{name:'保存 ASS 为样式模板'}));
 await waitFor(()=>expect(screen.getByLabelText('样式模板')).toHaveValue('ass-template'));
 expect(posts[0].body).toBe(file);
 expect(posts[1]).toEqual({url:'/companion-api/style-templates',body:{name:'直播双语',style:{version:1,original,translation}}});
 expect(screen.getByLabelText('原文字号')).toHaveValue(62);
});
it('exports style and language with project only for ArcTime; blocks full source burn',async()=>{
 const fetch=vi.fn(async()=>new Response('{}'));vi.stubGlobal('fetch',fetch);
 mount(<SubtitleExports id="job1" video="source.mp4" bilingual style={defaultStyle} project="project1" busy={false} burnAvailable nativeAvailable={false} error={null}/>);
 expect(screen.getByText('烧录切片 MP4')).toBeDisabled();fireEvent.click(screen.getByText('导出 ASS'));
 await waitFor(()=>expect(fetch).toHaveBeenNthCalledWith(1,'/companion-api/jobs/job1/subtitle-export',expect.objectContaining({body:JSON.stringify({kind:'ass',video:'source.mp4',bilingual:true,style:defaultStyle})})));
 await waitFor(()=>expect(screen.getByText('导出 ArcTime ZIP')).toBeEnabled());
 fireEvent.click(screen.getByText('导出 ArcTime ZIP'));
 await waitFor(()=>expect(fetch).toHaveBeenNthCalledWith(2,'/companion-api/jobs/job1/subtitle-export',expect.objectContaining({body:JSON.stringify({kind:'arctime',video:'source.mp4',bilingual:true,style:defaultStyle,arctime_template_id:'project1'})})));
});
it('disables all export actions while busy and names prior output scope',()=>{
 mount(<SubtitleExports id="job1" video="clip-001.mp4" bilingual={false} style={defaultStyle} project={null} busy burnAvailable nativeAvailable={false} error={null} status={{active:{state:'running',message:'烧录中',error:null},outputs:[{id:'out1',kind:'ass',video:'source.mp4',bilingual:true,filename:'styled.ass'}]}}/>);
 for(const label of ['导出 ASS','烧录切片 MP4','导出 ArcTime ZIP']) expect(screen.getByText(label)).toBeDisabled();
 expect(screen.getByText('ASS 字幕 · 完整视频 · 中日双语')).toBeVisible();expect(screen.getByRole('link',{name:'下载ASS 字幕 · 完整视频 · 中日双语'})).toHaveAttribute('href','/companion-api/jobs/job1/files/styled.ass?download=true');
});
it('selects the returned copy id and keeps rename/export on that copy',async()=>{
 const posts:unknown[]=[];
 vi.stubGlobal('fetch',vi.fn(async(_url:string,init:RequestInit)=>{const body=JSON.parse(String(init.body));posts.push(body);return new Response(JSON.stringify({id:'copy2',name:body.name,style:defaultStyle,arctime_template_id:'project1',builtin:false}));}));
 mount();fireEvent.click(screen.getByText('字幕样式与模板'));fireEvent.change(screen.getByLabelText('样式模板'),{target:{value:'user1'}});fireEvent.click(screen.getByText('复制模板'));
 await waitFor(()=>expect(screen.getByLabelText('样式模板')).toHaveValue('copy2'));
 expect(screen.getByRole('link',{name:'导出样式 JSON'})).toHaveAttribute('href','/companion-api/style-templates/copy2/download');
 fireEvent.change(screen.getByLabelText('模板名称'),{target:{value:'副本改名'}});fireEvent.click(screen.getByText('更新 / 重命名模板'));fireEvent.click(screen.getByText('确认'));
 await waitFor(()=>expect(posts[1]).toMatchObject({id:'copy2',name:'副本改名',arctime_template_id:'project1'}));
});
it('labels exports with their captured style rather than the current draft',()=>{
 const captured={...defaultStyle,original:{...defaultStyle.original,font:'Saved Font',size:72,color:'#123456'}};
 mount(<SubtitleExports id="job1" video="clip-001.mp4" bilingual style={defaultStyle} project={null} busy={false} burnAvailable nativeAvailable={false} error={null} status={{active:null,outputs:[{id:'one',kind:'burn',video:'clip-001.mp4',bilingual:true,filename:'hash-one.mp4',style:captured},{id:'two',kind:'arctime',video:'source.mp4',bilingual:false,filename:'hash-two.zip',style:null}]}}/>);
 expect(screen.getByText('字幕视频 MP4 · 切片 1 · 中日双语')).toBeVisible();expect(screen.getByText(/原文：Saved Font · 72 · #123456/)).toBeVisible();expect(screen.getByText('样式信息未记录')).toBeVisible();expect(screen.getByRole('link',{name:'下载字幕视频 MP4 · 切片 1 · 中日双语'})).toHaveAttribute('title','hash-one.mp4');
});
it('sends template metadata and the selected revision when updating a saved template',async()=>{
 const requests:Record<string,unknown>[]=[];
 vi.stubGlobal('fetch',vi.fn(async(_url:string,init:RequestInit)=>{requests.push(JSON.parse(String(init.body)));return new Response('{}');}));
 const versioned={...settings,templates:[{...settings.templates[0],revision:4,streamer:'猫雷',workflow:{...defaultWorkflow,language:'ja' as const}}]};
 mount(<SubtitleEditor settings={versioned} error={null} style={defaultStyle} onStyle={()=>{}} project={null} onProject={()=>{}} busy={false}/>);
 fireEvent.click(screen.getByText('字幕样式与模板'));
 fireEvent.change(screen.getByLabelText('样式模板'),{target:{value:'user1'}});
 expect(screen.getByLabelText('主播 / 工作系列')).toHaveValue('猫雷');
 fireEvent.click(screen.getByText('更新 / 重命名模板'));fireEvent.click(screen.getByText('确认'));
 await waitFor(()=>expect(requests[0]).toMatchObject({id:'user1',expected_revision:4,streamer:'猫雷',workflow:{language:'ja'}}));
});
it('retains the draft revision when a background template refresh advances the server revision',async()=>{
 const requests:Record<string,unknown>[]=[];
 vi.stubGlobal('fetch',vi.fn(async(_url:string,init:RequestInit)=>{requests.push(JSON.parse(String(init.body)));return new Response(JSON.stringify({detail:'模板已更新，请重新载入'}),{status:409});}));
 const client=new QueryClient({defaultOptions:{queries:{retry:false},mutations:{retry:false}}});
 const view=(revision:number)=><QueryClientProvider client={client}><SubtitleEditor settings={{...settings,templates:[{...settings.templates[0],revision}]}} error={null} style={defaultStyle} onStyle={()=>{}} project={null} onProject={()=>{}} busy={false}/></QueryClientProvider>;
 const result=render(view(4));fireEvent.click(screen.getByText('字幕样式与模板'));
 fireEvent.change(screen.getByLabelText('样式模板'),{target:{value:'user1'}});
 result.rerender(view(5));
 fireEvent.click(screen.getByText('更新 / 重命名模板'));fireEvent.click(screen.getByText('确认'));
 await waitFor(()=>expect(requests[0]).toMatchObject({id:'user1',expected_revision:4}));
 expect(await screen.findByRole('alert')).toHaveTextContent('模板已更新');
});
it('primary save updates a selected user template using its captured revision',async()=>{
 const requests:Record<string,unknown>[]=[];
 vi.stubGlobal('fetch',vi.fn(async(_url:string,init:RequestInit)=>{requests.push(JSON.parse(String(init.body)));return new Response(JSON.stringify({...settings.templates[0],revision:5}));}));
 mount(<SubtitleEditor settings={{...settings,templates:[{...settings.templates[0],revision:4}]}} error={null} style={defaultStyle} onStyle={()=>{}} project={null} onProject={()=>{}} busy={false}/>);
 fireEvent.click(screen.getByText('字幕样式与模板'));fireEvent.change(screen.getByLabelText('样式模板'),{target:{value:'user1'}});
 fireEvent.click(screen.getByText('保存当前模板'));fireEvent.click(screen.getByText('确认'));
 await waitFor(()=>expect(requests[0]).toMatchObject({id:'user1',expected_revision:4}));
 expect(await screen.findByText(/已选模板：测试模板 · v5/)).toBeVisible();
});
