import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { subtitleApi, type SubtitleStyle } from './subtitleStyle';
import type { SubtitleDocument } from './subtitleDocument';
export interface ExportStatus {active:null | {state:string;message:string;error:string|null};outputs:{id:string;kind:string;video:string;bilingual:boolean;filename:string;style?:SubtitleStyle|null}[]}
export function useSubtitleExports(id: string | null) {return useQuery({queryKey:['companion','subtitle-exports',id],queryFn:()=>subtitleApi<ExportStatus>(`/jobs/${id}/subtitle-exports`),enabled:!!id,refetchInterval:1000});}
interface Props {id:string;video:string;bilingual:boolean;style:SubtitleStyle;project:string|null;busy:boolean;burnAvailable:boolean;nativeAvailable:boolean;status?:ExportStatus;error:Error|null;document?:SubtitleDocument|null}
export function SubtitleExports({id,video,bilingual,style,project,busy,burnAvailable,nativeAvailable,status,error,document}:Props) {
 const client=useQueryClient();
 const mutation=useMutation({mutationFn:(kind:string)=>subtitleApi(`/jobs/${id}/subtitle-export`,{kind,video,bilingual,style,arctime_template_id:project,...(document ? {document} : {})}),onSuccess:()=>client.invalidateQueries({queryKey:['companion']})});
 const handoff=useMutation({mutationFn:(path:string)=>subtitleApi(path,{})});
 return <div className="subtitle-exports"><h3>样式字幕导出</h3><p className="companion-muted">当前范围：{video === 'source.mp4' ? '完整视频' : video} · {bilingual ? '中日双语' : '原文'}。导出使用当前预览样式。</p>
 <div className="companion-downloads">{(['ass','burn','arctime'] as const).map(kind=><button key={kind} className="ny-button" disabled={busy || mutation.isPending || !!error || (kind==='burn' && (video==='source.mp4'||!burnAvailable))} onClick={()=>mutation.mutate(kind)}>{kind==='ass'?'导出 ASS':kind==='burn'?'烧录切片 MP4':'导出 ArcTime ZIP'}</button>)}</div>
 {document && <p className="companion-footnote">包含逐条字幕编辑稿第 {document.revision} 版。原始 SRT 下载仍保留识别结果；编辑后的 SRT 在 ArcTime ZIP 中。</p>}
 {!burnAvailable && <p className="companion-muted">当前 FFmpeg 不支持字幕烧录。</p>}{video==='source.mp4' && <p className="companion-muted">烧录仅支持切片，请在预览中选择切片。</p>}
 {(error || mutation.error || handoff.error || status?.active?.error) && <p role="alert" className="companion-error">{error?.message ?? mutation.error?.message ?? handoff.error?.message ?? status?.active?.error}</p>}
 {status?.active && <p role="status">{status.active.message}</p>}
 {status?.outputs?.map(output=>{
   const product = output.kind === 'burn' ? '字幕视频 MP4' : output.kind === 'arctime' ? 'ArcTime 精修包' : 'ASS 字幕';
   const clipNumber = /^clip-(\d+)\.mp4$/.exec(output.video)?.[1];
   const scope = output.video === 'source.mp4' ? '完整视频' : clipNumber ? `切片 ${Number(clipNumber)}` : output.video;
   const label = `${product} · ${scope} · ${output.bilingual ? '中日双语' : '原文'}`;
   return <div className="companion-result" key={output.id}><div><span>{label}</span><p className="companion-muted">{output.style ? (['original', ...(output.bilingual ? ['translation'] as const : [])] as const).map(key => {const saved=output.style?.[key];return saved ? `${key === 'original' ? '原文' : '译文'}：${saved.font} · ${saved.size} · ${saved.color}` : '';}).join(' / ') : '样式信息未记录'}</p></div><a className="ny-button" title={output.filename} href={`/companion-api/jobs/${id}/files/${encodeURIComponent(output.filename)}?download=true`}>下载{label}</a></div>;
 })}
 {nativeAvailable && <div className="companion-downloads"><button className="ny-button" disabled={handoff.isPending} onClick={()=>handoff.mutate('/arctime/open')}>打开 ArcTime</button><button className="ny-button" disabled={handoff.isPending} onClick={()=>handoff.mutate(`/jobs/${id}/subtitle-exports/open-folder`)}>打开导出文件夹</button></div>}
 <p className="companion-footnote">ArcTime ZIP 包含字幕和交接说明。先导入视频；如需 ATPJ 样式，先通过「从其它工程文件导入样式」导入，再导入 ASS 样式。旧模板的同名样式可能覆盖字号，请检查分辨率和双语排列。</p></div>;
}
