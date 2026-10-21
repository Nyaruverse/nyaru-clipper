import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { TemplatePreview } from './TemplatePreview';
import { defaultStyle } from './subtitleStyle';
afterEach(()=>{vi.unstubAllGlobals();vi.restoreAllMocks();});
it('removes a prior image when the new preview fails',async()=>{
 let failed=false;
 vi.stubGlobal('fetch',vi.fn(async()=>new Response('png',{status:failed?500:200})));
 vi.stubGlobal('URL', {...URL,createObjectURL:()=> 'blob:test-preview',revokeObjectURL:()=>{}});
 render(<TemplatePreview style={defaultStyle}/>);
 await screen.findByAltText('当前模板的示例字幕效果');
 failed=true;fireEvent.change(screen.getByLabelText('样片原文'),{target:{value:'新字幕'}});
 await screen.findByRole('alert');
 await waitFor(()=>expect(screen.queryByAltText('当前模板的示例字幕效果')).toBeNull());
});
