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
    {!advancedOnly && <FontPicker value={style.font} fonts={fonts?.families ?? []} onChange={font => onChange({font})} />}
    {missing && <p role="status" className="companion-error cue-wide">未检测到字体“{style.font}”，渲染时可能使用替代字体；请选择已安装字体并核对预览。</p>}
    {fonts?.available === false && <p className="companion-footnote cue-wide">当前系统无法列出字体，请通过精确预览核对字体替代情况。</p>}
    <div className="cue-checks cue-wide">{([{ key: 'bold', label: '粗体' }, { key: 'italic', label: '斜体' }, { key: 'underline', label: '下划线' }, { key: 'hidden', label: '隐藏此语言' }] as const).map(field => <label key={field.key}><input type="checkbox" checked={value[field.key]} onChange={event => onChange({ [field.key]: event.target.checked })} />{field.label}</label>)}</div>
    {numericFields.filter(field => !advancedOnly || !('basic' in field)).map(field => <label className="ny-field" key={field.key}>{field.label}<input className="ny-input" type="number" min={field.min} max={field.max} step={field.step} value={value[field.key]} onChange={event => {
      const next = event.target.valueAsNumber;
      if (Number.isFinite(next)) onChange({ [field.key]: Math.max(field.min, Math.min(field.max, next)) });
    }} /></label>)}
    {([{ key: 'color', label: '文字颜色', basic: true }, { key: 'outline_color', label: '描边颜色', basic: true }, { key: 'background_color', label: '底板颜色', basic: true }, { key: 'shadow_color', label: '阴影颜色' }] as const).filter(field => !advancedOnly || !('basic' in field)).map(field => <label className="ny-field" key={field.key}>{field.label}<input className="ny-input" type="color" value={value[field.key]} onChange={event => onChange({ [field.key]: event.target.value })} /></label>)}
    <fieldset className="cue-wide outline-layers"><legend>多层描边</legend>
      <p className="companion-footnote">保留基础描边，最多叠加两层；宽描边位于外侧。</p>
      {(style.outline_layers ?? []).map((layer, index, layers) => <div className="cue-style-fields" key={index}>
        <label className="ny-field">第 {index + 2} 层颜色<input type="color" className="ny-input" value={layer.color}
          onChange={event => onChange({outline_layers: layers.map((item, i) => i === index ? {...item, color: event.target.value} : item)})} /></label>
        <label className="ny-field">第 {index + 2} 层宽度<input type="number" className="ny-input" min={0} max={20} step={0.1} value={layer.width}
          onChange={event => { const width = event.target.valueAsNumber; if (Number.isFinite(width)) onChange({outline_layers: layers.map((item, i) => i === index ? {...item, width: Math.min(20, Math.max(0, width))} : item)}); }} /></label>
        <button type="button" className="ny-button ny-button--quiet" onClick={() => onChange({outline_layers: layers.filter((_, i) => i !== index)})}>删除第 {index + 2} 层</button>
      </div>)}
      <button type="button" className="ny-button" disabled={(style.outline_layers?.length ?? 0) >= 2}
        onClick={() => onChange({outline_layers: [...style.outline_layers ?? [], {color: style.outline_color, width: Math.min(20, Math.max(style.outline, ...(style.outline_layers ?? []).map(layer => layer.width)) + 2)}]})}>添加描边层</button>
    </fieldset>
    {!advancedOnly && <label className="ny-field cue-wide">自动位置<select className="ny-input" value={style.position} onChange={event => onChange({ position: event.target.value === 'top' ? 'top' : 'bottom', align: event.target.value === 'top' ? 8 : 2, x: null, y: null })}><option value="bottom">底部</option><option value="top">顶部</option></select></label>}
  </div>;
}
