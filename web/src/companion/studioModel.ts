export interface StudioWorkflow { readonly language:'auto'|'zh'|'ja'|'en'; readonly mode:'ranges'|'highlights'|'saozi'; readonly highlights:number; readonly export_format:'ass'|'mp4'|'arctime'; readonly bilingual:boolean }
export interface StudioDefaults extends StudioWorkflow { readonly default_template_id:string|null }
export const defaultWorkflow:StudioWorkflow={language:'auto',mode:'ranges',highlights:3,export_format:'ass',bilingual:true};
export function parseStudioDefaults(value:unknown):StudioDefaults {
 if(typeof value!=='object'||value===null||!('language' in value)||!('mode' in value)||!('highlights' in value)||!('export_format' in value)||!('bilingual' in value)||!('default_template_id' in value))throw new Error('工作台默认设置响应无效');
 const {language,mode,highlights,export_format,bilingual,default_template_id}=value;
 if((language!=='auto'&&language!=='zh'&&language!=='ja'&&language!=='en')||(mode!=='ranges'&&mode!=='highlights'&&mode!=='saozi')||typeof highlights!=='number'||!Number.isInteger(highlights)||highlights<1||highlights>100||(export_format!=='ass'&&export_format!=='mp4'&&export_format!=='arctime')||typeof bilingual!=='boolean'||(default_template_id!==null&&typeof default_template_id!=='string'))throw new Error('工作台默认设置响应无效');
 return {language,mode,highlights,export_format,bilingual,default_template_id};
}
