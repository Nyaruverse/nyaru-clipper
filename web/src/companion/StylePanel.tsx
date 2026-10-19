/** 旧版字幕样式面板：滑杆交互、多层描边（最多 3 层）、X/Y 百分比定位、实时示例预览、模板保存/应用/删除。
 * 样式草稿由 useLegacyStyle 在 Companion 层持有，预览实时联动；修改 600ms 防抖自动保存。
 */
import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlignCenter, AlignLeft, AlignRight, Plus, Trash2 } from "lucide-react";
import { api, type LegacyStyleConfig, type LegacyStyleStore, type LegacyTextStyle, type OutlineLayer } from "./companionApi";
import { DEFAULT_STYLE, FALLBACK_FONTS, MAX_OUTLINES, StyledText, hexToRgba } from "./legacyStyle";
import { FontPicker } from "./FontPicker";

/** 旧版样式状态：草稿 + 防抖自动保存，供面板与视频预览共享 */
export function useLegacyStyle() {
  const queryClient = useQueryClient();
  const styles = useQuery({ queryKey: ["companion", "style"], queryFn: () => api<LegacyStyleStore>("/subtitle-style") });
  const [styleDraft, setStyleDraft] = useState<LegacyStyleConfig | null>(null);
  const [styleSaved, setStyleSaved] = useState(false);
  const saveStyle = useMutation({
    mutationFn: (next: LegacyStyleConfig) => api<LegacyStyleStore>("/subtitle-style", next, "PUT"),
    onSuccess: data => { setStyleSaved(true); queryClient.setQueryData(["companion", "style"], data); },
  });
  const currentStyle = styleDraft ?? styles.data?.current ?? DEFAULT_STYLE;
  const updateStyle = (next: LegacyStyleConfig) => { setStyleDraft(next); setStyleSaved(false); };
  const saveStyleMutate = saveStyle.mutate;
  useEffect(() => {
    if (!styleDraft) return;
    const timer = window.setTimeout(() => saveStyleMutate(styleDraft), 600);
    return () => window.clearTimeout(timer);
  }, [styleDraft, saveStyleMutate]);
  return { styles, currentStyle, updateStyle, saveStyle, styleSaved };
}

export type LegacyStyleState = ReturnType<typeof useLegacyStyle>;

function TextStyleFields({ title, value, onChange, fonts, sample, tone }: {
  title: string;
  value: LegacyTextStyle;
  onChange: (next: LegacyTextStyle) => void;
  fonts: readonly string[];
  sample: string;
  tone: "original" | "translated";
}) {
  const update = <K extends keyof LegacyTextStyle>(key: K, next: LegacyTextStyle[K]) => onChange({ ...value, [key]: next });
  const updateOutline = (index: number, patch: Partial<OutlineLayer>) =>
    update("outlines", value.outlines.map((item, i) => i === index ? { ...item, ...patch } : item));
  const alignButtons: { key: LegacyTextStyle["align"]; label: string; icon: React.ReactNode }[] = [
    { key: "left", label: "左对齐", icon: <AlignLeft size={15} /> },
    { key: "center", label: "居中对齐", icon: <AlignCenter size={15} /> },
    { key: "right", label: "右对齐", icon: <AlignRight size={15} /> },
  ];
  return <fieldset className={`style-block style-block--${tone}`}>
    <legend>{title}</legend>
    <div className="style-sample" aria-label={`${title}示例预览`}>
      <span style={{
        fontFamily: value.font_family,
        fontSize: Math.min(40, Math.max(12, value.font_size * 0.45)),
        textAlign: value.align,
        backgroundColor: value.background_opacity > 0 ? hexToRgba(value.background_color, value.background_opacity) : undefined,
        padding: value.background_opacity > 0 ? "0.05em 0.2em" : undefined,
        alignSelf: value.align === "left" ? "flex-start" : value.align === "right" ? "flex-end" : "center",
      }}><StyledText text={sample} style={value} scale={0.45} /></span>
    </div>
    <div className="style-group">
      <h3>文字</h3>
      <div className="style-grid">
        <label>字体<FontPicker value={value.font_family} fonts={fonts} onChange={font => update("font_family", font)} /></label>
        <label>字号<input className="ny-input" type="number" min={8} max={200} value={value.font_size} onChange={event => update("font_size", Math.min(200, Math.max(8, Number(event.target.value) || 8)))} /></label>
        <label>文字颜色<input type="color" value={value.text_color} onChange={event => update("text_color", event.target.value)} /></label>
      </div>
    </div>
    <div className="style-group">
      <h3>背景</h3>
      <div className="style-grid">
        <label>背景颜色<input type="color" value={value.background_color} onChange={event => update("background_color", event.target.value)} /></label>
        <label>背景透明度<span className="style-range"><input type="range" min={0} max={1} step={0.05} value={value.background_opacity} onChange={event => update("background_opacity", Number(event.target.value))} /><span>{Math.round(value.background_opacity * 100)}%</span></span></label>
      </div>
      <p className="style-hint">透明度 0% 时预览与合成视频都不绘制背景。</p>
    </div>
    <div className="style-group">
      <h3>描边 <span className="style-hint">{value.outlines.length}/{MAX_OUTLINES} 层 · 第 1 层最贴近文字</span></h3>
      {value.outlines.map((outline, index) => <div className="style-outline-row" key={index}>
        <span className="style-outline-index">{index + 1}</span>
        <input type="color" aria-label={`描边 ${index + 1} 颜色`} value={outline.color} onChange={event => updateOutline(index, { color: event.target.value })} />
        <span className="style-range"><input type="range" aria-label={`描边 ${index + 1} 宽度`} min={0.5} max={20} step={0.5} value={outline.width} onChange={event => updateOutline(index, { width: Number(event.target.value) })} /><span>{outline.width}px</span></span>
        <button className="ny-button ny-button--quiet" type="button" aria-label={`删除描边 ${index + 1}`} disabled={value.outlines.length <= 1} onClick={() => update("outlines", value.outlines.filter((_, i) => i !== index))}><Trash2 size={14} /></button>
      </div>)}
      <button className="ny-button" type="button" disabled={value.outlines.length >= MAX_OUTLINES} onClick={() => update("outlines", [...value.outlines, { color: "#000000", width: 4 }])}><Plus size={15} />添加描边</button>
    </div>
    <div className="style-group">
      <h3>位置</h3>
      <label className="style-slider">水平 X<span className="style-range"><input type="range" min={0} max={100} step={1} value={value.pos_x} onChange={event => update("pos_x", Number(event.target.value))} /><span>{Math.round(value.pos_x)}%</span></span></label>
      <label className="style-slider">垂直 Y<span className="style-range"><input type="range" min={0} max={100} step={1} value={value.pos_y} onChange={event => update("pos_y", Number(event.target.value))} /><span>{Math.round(value.pos_y)}%</span></span></label>
      <div className="style-align" role="group" aria-label="水平对齐">
        {alignButtons.map(item => <button key={item.key} className="ny-button" type="button" aria-pressed={value.align === item.key} title={item.label} onClick={() => update("align", item.key)}>{item.icon}{item.label.replace("对齐", "")}</button>)}
      </div>
    </div>
  </fieldset>;
}

export function StylePanel({ style }: { style: LegacyStyleState }) {
  const queryClient = useQueryClient();
  const { styles, currentStyle, updateStyle, saveStyle, styleSaved } = style;
  const [templatePick, setTemplatePick] = useState("");
  const [templateName, setTemplateName] = useState("");
  const fontsQuery = useQuery({
    queryKey: ["companion", "fonts"],
    queryFn: () => api<{ available: boolean; families: string[] }>("/subtitle-fonts"),
    staleTime: Infinity,
  });
  const saveTemplate = useMutation({
    mutationFn: (payload: { name: string; config: LegacyStyleConfig }) =>
      api<LegacyStyleStore>(`/subtitle-style/templates/${encodeURIComponent(payload.name)}`, payload.config, "PUT"),
    onSuccess: data => { queryClient.setQueryData(["companion", "style"], data); setTemplateName(""); },
  });
  const deleteTemplate = useMutation({
    mutationFn: (name: string) => api<LegacyStyleStore>(`/subtitle-style/templates/${encodeURIComponent(name)}`, undefined, "DELETE"),
    onSuccess: data => { queryClient.setQueryData(["companion", "style"], data); setTemplatePick(""); },
  });
  const templateNames = Object.keys(styles.data?.templates ?? {});
  const applyTemplate = () => {
    const template = styles.data?.templates[templatePick];
    if (template) updateStyle({ original: { ...template.original }, translated: { ...template.translated } });
  };
  const fonts = fontsQuery.data?.families ?? FALLBACK_FONTS;
  return <>
    <p className="companion-muted">原文与译文可分别设置，修改实时应用到预览，合成视频时使用相同样式。</p>
    <div className="style-templates">
      <label className="ny-field">模板
        <select className="ny-input" value={templatePick} onChange={event => setTemplatePick(event.target.value)}>
          <option value="">{templateNames.length ? "选择模板…" : "暂无保存的模板"}</option>
          {templateNames.map(name => <option key={name} value={name}>{name}</option>)}
        </select>
      </label>
      <div className="style-template-actions">
        <button className="ny-button" type="button" disabled={!templatePick} onClick={applyTemplate}>应用模板</button>
        <button className="ny-button ny-button--quiet" type="button" disabled={!templatePick || deleteTemplate.isPending} onClick={() => { if (templatePick) deleteTemplate.mutate(templatePick); }}>删除模板</button>
      </div>
      <form className="style-template-save" onSubmit={event => { event.preventDefault(); const name = templateName.trim(); if (name) saveTemplate.mutate({ name, config: currentStyle }); }}>
        <input className="ny-input" placeholder="新模板名称" maxLength={32} value={templateName} onChange={event => setTemplateName(event.target.value)} />
        <button className="ny-button" type="submit" disabled={!templateName.trim() || saveTemplate.isPending}>存为模板</button>
      </form>
    </div>
    <TextStyleFields title="原文字幕" value={currentStyle.original} onChange={original => updateStyle({ ...currentStyle, original })} fonts={fonts} sample="あ、ここですか！？" tone="original" />
    <TextStyleFields title="译文字幕" value={currentStyle.translated} onChange={translated => updateStyle({ ...currentStyle, translated })} fonts={fonts} sample="啊，是这里吗！？" tone="translated" />
    <p className="companion-footnote">{saveStyle.isPending ? "正在保存样式…" : styleSaved ? "样式已保存 · 立即生效" : "修改后自动保存"}</p>
    {saveStyle.isError && <p className="companion-error" role="alert">{saveStyle.error.message}</p>}
    {saveTemplate.isError && <p className="companion-error" role="alert">{saveTemplate.error.message}</p>}
    {deleteTemplate.isError && <p className="companion-error" role="alert">{deleteTemplate.error.message}</p>}
  </>;
}
