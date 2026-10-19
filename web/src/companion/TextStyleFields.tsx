import { advancedDefaults } from './subtitleDocument';
import type { TextStyle } from './subtitleStyle';
import { FontPicker } from './FontPicker';

export interface FontCatalog { readonly available: boolean; readonly families: readonly string[] }
interface Props { readonly style: TextStyle; readonly onChange: (patch: Partial<TextStyle>) => void; readonly advancedOnly?: boolean; readonly fonts?: FontCatalog }
const numericFields = [
  { key: 'size', label: '字号', min: 8, max: 200, step: 1, basic: true },
  { key: 'outline', label: '描边宽度', min: 0, max: 20, step: 0.1, basic: true },
  { key: 'margin', label: '自动位置垂直边距', min: 0, max: 1080, step: 1, basic: true },
  { key: 'opacity', label: '文字不透明度', min: 0, max: 1, step: 0.05 },
  { key: 'spacing', label: '字距', min: -10, max: 100, step: 0.1 },
  { key: 'line_height', label: '行高倍数', min: 0.5, max: 3, step: 0.05 },
  { key: 'max_width', label: '换行宽度 %', min: 10, max: 100, step: 1 },
  { key: 'rotation', label: '旋转角度', min: -360, max: 360, step: 0.1 },
  { key: 'scale_x', label: '水平缩放 %', min: 10, max: 400, step: 1 },
  { key: 'scale_y', label: '垂直缩放 %', min: 10, max: 400, step: 1 },
  { key: 'shadow', label: '阴影距离', min: 0, max: 20, step: 0.1 },
  { key: 'padding', label: '底板内边距', min: 0, max: 40, step: 1 },
  { key: 'background_opacity', label: '底板不透明度', min: 0, max: 1, step: 0.05, basic: true },
] as const;

export function TextStyleFields({ style, onChange, advancedOnly = false, fonts }: Props) {
  const value = { ...advancedDefaults, ...style };
  const missing = fonts?.available && !fonts.families.some(name => name.toLocaleLowerCase() === style.font.trim().toLocaleLowerCase());
  return <div className="cue-style-fields">
    {!advancedOnly && <label className="ny-field cue-wide">字体<FontPicker value={style.font} fonts={fonts?.families ?? []} onChange={font => onChange({ font })} /></label>}
    {missing && <p role="status" className="companion-error cue-wide">未检测到字体“{style.font}”，渲染时可能使用替代字体；请选择已安装字体并核对预览。</p>}
    {fonts?.available === false && <p className="companion-footnote cue-wide">当前系统无法列出字体，请通过精确预览核对字体替代情况。</p>}
    <div className="cue-checks cue-wide">{([{ key: 'bold', label: '粗体' }, { key: 'italic', label: '斜体' }, { key: 'underline', label: '下划线' }, { key: 'hidden', label: '隐藏此语言' }] as const).map(field => <label key={field.key}><input type="checkbox" checked={value[field.key]} onChange={event => onChange({ [field.key]: event.target.checked })} />{field.label}</label>)}</div>
    {numericFields.filter(field => !advancedOnly || !('basic' in field)).map(field => <label className="ny-field" key={field.key}>{field.label}<input className="ny-input" type="number" min={field.min} max={field.max} step={field.step} value={value[field.key]} onChange={event => {
      const next = event.target.valueAsNumber;
      if (Number.isFinite(next)) onChange({ [field.key]: Math.max(field.min, Math.min(field.max, next)) });
    }} /></label>)}
    {([{ key: 'color', label: '文字颜色', basic: true }, { key: 'outline_color', label: '描边颜色', basic: true }, { key: 'background_color', label: '底板颜色', basic: true }, { key: 'shadow_color', label: '阴影颜色' }] as const).filter(field => !advancedOnly || !('basic' in field)).map(field => <label className="ny-field" key={field.key}>{field.label}<input className="ny-input" type="color" value={value[field.key]} onChange={event => onChange({ [field.key]: event.target.value })} /></label>)}
    {!advancedOnly && <label className="ny-field cue-wide">自动位置<select className="ny-input" value={style.position} onChange={event => onChange({ position: event.target.value === 'top' ? 'top' : 'bottom', align: event.target.value === 'top' ? 8 : 2, x: null, y: null })}><option value="bottom">底部</option><option value="top">顶部</option></select></label>}
  </div>;
}
