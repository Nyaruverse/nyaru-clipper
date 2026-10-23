import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { Companion } from './Companion';
import { defaultStyle } from './subtitleStyle';

afterEach(() => vi.unstubAllGlobals());
function setup(postResponse?: (body:Record<string,unknown>)=>Promise<Response>) {
 const posts: {url:string;body:Record<string,unknown>}[]=[];
 const client=new QueryClient({defaultOptions:{queries:{retry:false},mutations:{retry:false}}});
 vi.stubGlobal('fetch',vi.fn(async(url:string,options?:RequestInit)=>{
  if(options?.method==='POST'){const body:Record<string,unknown>=JSON.parse(String(options.body));posts.push({url,body});return postResponse?postResponse(body):new Response(JSON.stringify(body));}
  return new Response(JSON.stringify(url.endsWith('/config')?{ready:true,missing:[],translation_configured:false}:url.endsWith('/jobs')?[]:url.endsWith('/studio-settings')?{default_template_id:null,language:'auto',mode:'ranges',highlights:3,export_format:'ass',bilingual:true}:url.endsWith('/subtitle-settings')?{style:defaultStyle,templates:[],arctime_templates:[]}:{}));
 }));
 render(<QueryClientProvider client={client}><Companion /></QueryClientProvider>);
 return {posts,client};
}
it('retains task form draft across design and settings round trips',async()=>{
 setup();fireEvent.click(screen.getByRole('button',{name:'新建任务'}));
 fireEvent.change(screen.getByLabelText('BV 号'),{target:{value:'BV1xx411c7mD'}});
 fireEvent.click(screen.getByRole('tab',{name:'模板设计'}));
 fireEvent.click(screen.getByRole('button',{name:'设置'}));
 fireEvent.click(screen.getByRole('button',{name:'返回工作区'}));
 fireEvent.click(screen.getByRole('tab',{name:'日常模式'}));
 fireEvent.click(screen.getByRole('button',{name:'新建任务'}));
 expect(screen.getByLabelText('BV 号')).toHaveValue('BV1xx411c7mD');
});
it('guards dirty defaults and saves only explicit settings changes',async()=>{
 const {posts}=setup();fireEvent.click(screen.getByRole('button',{name:'设置'}));
 fireEvent.click(screen.getByRole('button',{name:'识别与处理'}));
 const language=await screen.findByLabelText('默认视频语种');
 fireEvent.change(language,{target:{value:'ja'}});
 const confirm=vi.spyOn(window,'confirm').mockReturnValue(false);
 fireEvent.click(screen.getByRole('button',{name:'返回工作区'}));
 expect(confirm).toHaveBeenCalled();expect(language).toBeVisible();expect(posts).toHaveLength(0);
 fireEvent.click(screen.getByRole('button',{name:'保存更改'}));
 await waitFor(()=>expect(posts).toEqual([{url:'/companion-api/studio-settings',body:{default_template_id:null,language:'ja',mode:'ranges',highlights:3,export_format:'ass',bilingual:true}}]));
 await waitFor(()=>expect(screen.getByRole('status')).toHaveTextContent('默认设置已保存'));
 expect(language).toHaveValue('ja');
 expect(screen.getByRole('button',{name:'保存更改'})).toBeDisabled();
 confirm.mockClear();
 fireEvent.click(screen.getByRole('button',{name:'返回工作区'}));
 expect(confirm).not.toHaveBeenCalled();
 confirm.mockRestore();
});
it('preserves newer defaults after a delayed save and persists them on the next save',async()=>{
 let accept:(response:Response)=>void=vi.fn();
 const firstResponse=new Promise<Response>(resolve=>{accept=resolve;});
 const response=vi.fn<(body:Record<string,unknown>)=>Promise<Response>>()
  .mockImplementationOnce(()=>firstResponse)
  .mockImplementation(async body=>new Response(JSON.stringify(body)));
 const {posts,client}=setup(response);
 fireEvent.click(screen.getByRole('button',{name:'设置'}));
 fireEvent.click(screen.getByRole('button',{name:'识别与处理'}));
 await waitFor(()=>expect(screen.getByRole('button',{name:'保存更改'})).toBeDisabled());
 const language=screen.getByLabelText('默认视频语种');
 fireEvent.change(language,{target:{value:'ja'}});
 const save=screen.getByRole('button',{name:'保存更改'});
 await waitFor(()=>expect(save).toBeEnabled());
 fireEvent.click(save);
 await waitFor(()=>expect(posts).toHaveLength(1));
 expect(posts[0]).toEqual({url:'/companion-api/studio-settings',body:{default_template_id:null,language:'ja',mode:'ranges',highlights:3,export_format:'ass',bilingual:true}});
 expect(screen.getByRole('status')).toHaveTextContent('正在保存…');
 expect(language).toBeEnabled();
 fireEvent.change(language,{target:{value:'en'}});
 accept(new Response(JSON.stringify(posts[0].body)));
 await waitFor(()=>expect(screen.getByRole('status')).toHaveTextContent('有未保存的默认设置'));
 expect(language).toHaveValue('en');
 expect(client.getQueryData(['companion','studio-settings'])).toEqual(posts[0].body);
 expect(save).toBeEnabled();
 fireEvent.click(save);
 await waitFor(()=>expect(screen.getByRole('status')).toHaveTextContent('默认设置已保存'));
 expect(posts).toHaveLength(2);
 expect(posts[1]).toEqual({url:'/companion-api/studio-settings',body:{...posts[0].body,language:'en'}});
 expect(language).toHaveValue('en');
 expect(client.getQueryData(['companion','studio-settings'])).toEqual(posts[1].body);
 expect(save).toBeDisabled();
});
it('keeps failed defaults dirty and saves them when retried',async()=>{
 const response=vi.fn<(body:Record<string,unknown>)=>Promise<Response>>()
  .mockResolvedValueOnce(new Response(JSON.stringify({detail:'保存失败'}),{status:500}))
  .mockImplementation(async body=>new Response(JSON.stringify(body)));
 const {posts,client}=setup(response);
 fireEvent.click(screen.getByRole('button',{name:'设置'}));
 fireEvent.click(screen.getByRole('button',{name:'识别与处理'}));
 const language=await screen.findByLabelText('默认视频语种');
 fireEvent.change(language,{target:{value:'ja'}});
 const save=screen.getByRole('button',{name:'保存更改'});
 await waitFor(()=>expect(save).toBeEnabled());
 fireEvent.click(save);
 expect(await screen.findByRole('alert')).toHaveTextContent('保存失败');
 expect(language).toHaveValue('ja');
 expect(screen.getByRole('status')).toHaveTextContent('有未保存的默认设置');
 expect(client.getQueryData(['companion','studio-settings'])).toMatchObject({language:'auto'});
 expect(save).toBeEnabled();
 fireEvent.click(save);
 await waitFor(()=>expect(screen.getByRole('status')).toHaveTextContent('默认设置已保存'));
 expect(posts).toHaveLength(2);
 expect(posts[0]).toEqual({url:'/companion-api/studio-settings',body:{default_template_id:null,language:'ja',mode:'ranges',highlights:3,export_format:'ass',bilingual:true}});
 expect(posts[1]).toEqual(posts[0]);
 expect(client.getQueryData(['companion','studio-settings'])).toEqual(posts[1].body);
 expect(language).toHaveValue('ja');
 expect(save).toBeDisabled();
 expect(screen.queryByRole('alert')).not.toBeInTheDocument();
});
it('applies default template workflow above software defaults and preserves task adjustments on roundtrip',async()=>{
 vi.stubGlobal('fetch',vi.fn(async(url:string)=>new Response(JSON.stringify(url.endsWith('/config')?{ready:true,missing:[]}:url.endsWith('/jobs')?[]:url.endsWith('/studio-settings')?{default_template_id:'test',language:'auto',mode:'ranges',highlights:3,export_format:'ass',bilingual:true}:url.endsWith('/subtitle-settings')?{style:defaultStyle,templates:[{id:'test',name:'工作模板',style:defaultStyle,workflow:{language:'ja',mode:'highlights',highlights:7,export_format:'arctime',bilingual:false}}],arctime_templates:[]}:{}))));
 render(<QueryClientProvider client={new QueryClient({defaultOptions:{queries:{retry:false}}})}><Companion/></QueryClientProvider>);
 fireEvent.click(screen.getByRole('button',{name:'新建任务'}));
 await waitFor(()=>expect(screen.getByLabelText('视频语种')).toHaveValue('ja'));
 fireEvent.change(screen.getByLabelText('视频语种'),{target:{value:'en'}});
 fireEvent.click(screen.getByRole('button',{name:'设置'}));fireEvent.click(screen.getByRole('button',{name:'返回工作区'}));
 expect(screen.getByLabelText('视频语种')).toHaveValue('en');
});
it('keeps design template appearance isolated from the settings template draft',async()=>{
 const styleA={...defaultStyle,original:{...defaultStyle.original,size:52}};
 const styleB={...defaultStyle,original:{...defaultStyle.original,size:88}};
 vi.stubGlobal('fetch',vi.fn(async(url:string)=>new Response(JSON.stringify(url.endsWith('/config')?{ready:true,missing:[]}:url.endsWith('/jobs')?[]:url.endsWith('/studio-settings')?{default_template_id:null,language:'auto',mode:'ranges',highlights:3,export_format:'ass',bilingual:true}:url.endsWith('/subtitle-settings')?{style:defaultStyle,templates:[{id:'a',name:'A',style:styleA},{id:'b',name:'B',style:styleB}],arctime_templates:[]}:{}))));
 render(<QueryClientProvider client={new QueryClient({defaultOptions:{queries:{retry:false}}})}><Companion/></QueryClientProvider>);
 fireEvent.click(screen.getByRole('tab',{name:'模板设计'}));
 await screen.findByRole('option',{name:'A'});
 fireEvent.change(screen.getByRole('combobox',{name:'样式模板'}),{target:{value:'a'}});
 expect(screen.getByRole('spinbutton',{name:'原文字号'})).toHaveValue(52);
 fireEvent.click(screen.getByRole('button',{name:'设置'}));fireEvent.click(screen.getByRole('button',{name:'字幕与模板'}));
 fireEvent.change(screen.getByRole('combobox',{name:'样式模板'}),{target:{value:'b'}});
 expect(screen.getByRole('spinbutton',{name:'原文字号'})).toHaveValue(88);
 fireEvent.click(screen.getByRole('button',{name:'返回工作区'}));
 expect(screen.getByRole('combobox',{name:'样式模板'})).toHaveValue('a');
 expect(screen.getByRole('spinbutton',{name:'原文字号'})).toHaveValue(52);
});
