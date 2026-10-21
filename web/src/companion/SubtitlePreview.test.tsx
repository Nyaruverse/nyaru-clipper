import { useRef, useState } from 'react';
import { render,screen,fireEvent } from '@testing-library/react';
import { expect,it,vi } from 'vitest';
import { SubtitlePreview } from './SubtitlePreview';
import { defaultStyle } from './subtitleStyle';
function Harness({background = 0}: {background?: number}){const video=useRef<HTMLVideoElement>(null);const [style,setStyle]=useState({...defaultStyle,original:{...defaultStyle.original,background_opacity:background}});return <><button onClick={()=>setStyle({...defaultStyle,original:{...defaultStyle.original,color:'#FF0000',size:80}})}>change</button><SubtitlePreview video={video} segments={[{start_seconds:10,end_seconds:12,text:'原文\n二行'}]} bilingual={[{start_seconds:10,end_seconds:12,text:'原文\n二行\n译文'}]} offset={10} source="clip.mp4" style={style}><video ref={video} aria-label="test video"/></SubtitlePreview></>;}
it('responds to seeking/pause, applies style and keeps native captions selectable',()=>{
 render(<Harness/>);const video=screen.getByLabelText('test video');
 Object.defineProperties(video,{clientWidth:{value:1920},clientHeight:{value:1080},videoWidth:{value:1920},videoHeight:{value:1080},textTracks:{value:[{mode:'showing'}]}});
 fireEvent.loadedMetadata(video);
 expect(screen.getByTestId('subtitle-original')).toHaveStyle({fontSize:'48px'});
 expect(screen.getByTestId('subtitle-translation')).toHaveTextContent('译文');
 fireEvent.click(screen.getByText('change'));expect(screen.getByTestId('subtitle-original')).toHaveStyle({fontSize:'80px',color:'#FF0000'});
 fireEvent.seeking(video,{target:{currentTime:2}});expect(screen.queryByTestId('subtitle-original')).toBeNull();
 fireEvent.pause(video,{target:{currentTime:1}});expect(screen.getByTestId('subtitle-original')).toBeVisible();
 fireEvent.click(screen.getByRole('checkbox',{name:'样式字幕预览'}));expect(screen.queryByTestId('subtitle-original')).toBeNull();
});
it('requests fullscreen on the wrapper containing subtitles and video',()=>{
 render(<Harness/>);const wrapper=document.querySelector('.subtitle-video-wrapper');const request=vi.fn().mockResolvedValue(undefined);Object.defineProperty(wrapper,'requestFullscreen',{value:request});
 fireEvent.click(screen.getByText('含字幕全屏'));expect(request).toHaveBeenCalledOnce();expect(wrapper?.querySelector('video')).not.toBeNull();
});
it('paints a nonzero-opacity background only on text content',()=>{
 render(<Harness background={0.4}/>);const text=screen.getByTestId('subtitle-original');expect(text).toHaveStyle({backgroundColor:'rgba(0, 0, 0, 0.4)'});expect(text.parentElement?.style.backgroundColor).toBe('');
});
it('exposes an exit action inside fullscreen and exits through the document API',async()=>{
 render(<Harness/>);const video=screen.getByLabelText('test video');const wrapper=video.parentElement;
 const exit=vi.fn().mockResolvedValue(undefined);Object.defineProperty(document,'exitFullscreen',{value:exit,configurable:true});Object.defineProperty(document,'fullscreenElement',{value:wrapper,configurable:true});
 fireEvent(document,new Event('fullscreenchange'));
 const button=screen.getByRole('button',{name:'退出含字幕全屏'});expect(wrapper?.contains(button)).toBe(true);fireEvent.click(button);expect(exit).toHaveBeenCalledOnce();
 Object.defineProperty(document,'fullscreenElement',{value:null,configurable:true});fireEvent(document,new Event('fullscreenchange'));expect(screen.queryByRole('button',{name:'退出含字幕全屏'})).toBeNull();
});
