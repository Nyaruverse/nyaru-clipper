/** 旧版字幕样式模型的前端渲染助手：多层描边（轮廓外扩，无重影）与 \pos 百分比定位。 */
import type { CSSProperties, ReactNode } from "react";
import type { LegacyStyleConfig, LegacyTextStyle, Segment, SubtitleMode } from "./companionApi";

export const MAX_OUTLINES = 3;
export const FALLBACK_FONTS = ["Microsoft YaHei", "SimHei", "SimSun", "KaiTi", "Arial"];
export const DEFAULT_STYLE: LegacyStyleConfig = {
  original: { font_family: "Microsoft YaHei", font_size: 48, text_color: "#FFFFFF", background_color: "#000000", background_opacity: 0, outlines: [{ color: "#000000", width: 2 }], pos_x: 50, pos_y: 78, align: "center" },
  translated: { font_family: "Microsoft YaHei", font_size: 64, text_color: "#FFFFFF", background_color: "#000000", background_opacity: 0, outlines: [{ color: "#000000", width: 2 }], pos_x: 50, pos_y: 92, align: "center" },
  show_original: true,
  show_translated: true,
};

export function hexToRgba(hex: string, opacity: number): string {
  const value = parseInt(hex.slice(1), 16);
  return `rgba(${(value >> 16) & 255}, ${(value >> 8) & 255}, ${value & 255}, ${opacity})`;
}

/** 真轮廓描边文字：-webkit-text-stroke 从字形轮廓向外扩展，多层用叠层实现，任意宽度无重影 */
export function StyledText({ text, style, scale }: { text: string; style: LegacyTextStyle; scale: number }) {
  let cumulative = 0;
  const widths = style.outlines.map(outline => (cumulative += outline.width));
  const layers: ReactNode[] = [];
  for (let i = style.outlines.length - 1; i >= 0; i--) {
    // stroke 以轮廓为中心向两侧各延伸一半，2× 宽度 + fill 覆盖内侧 = 与 ASS \bord 一致的外扩宽度
    layers.push(<span key={i} aria-hidden style={{
      position: "absolute", inset: 0, color: style.outlines[i].color,
      WebkitTextStroke: `${(2 * widths[i] * scale).toFixed(1)}px ${style.outlines[i].color}`,
      paintOrder: "stroke fill",
    }}>{text}</span>);
  }
  layers.push(<span key="fill" style={{ position: "relative", color: style.text_color }}>{text}</span>);
  return <span style={{ position: "relative", display: "inline-block", fontFamily: style.font_family }}>{layers}</span>;
}

/** 与 ASS \pos + 中部对齐一致的绝对定位 */
export function positionCss(style: LegacyTextStyle): CSSProperties {
  const translate = style.align === "center" ? "translate(-50%, -50%)" : style.align === "left" ? "translate(0, -50%)" : "translate(-100%, -50%)";
  return { position: "absolute", left: `${style.pos_x}%`, top: `${style.pos_y}%`, transform: translate };
}

/** 旧模型字幕叠层：bilingual 按 \n 切分（末行译文，其余原文）；zh 仅译文；original 仅原文 */
export function SubtitleOverlay({ mode, currentTime, original, translated, bilingual, style, scale, box }: {
  mode: SubtitleMode;
  currentTime: number;
  original: Segment[];
  translated: Segment[];
  bilingual: Segment[];
  style: LegacyStyleConfig;
  scale: number;
  /** letterbox 画面盒定位（width/height/left/top） */
  box?: CSSProperties;
}) {
  const lines: { key: string; text: string; style: LegacyTextStyle; layer: "original" | "translated" }[] = [];
  const active = (segments: Segment[]) => segments.filter(s => currentTime >= s.start_seconds && currentTime < s.end_seconds);
  if (mode === "bilingual") {
    active(bilingual).forEach((segment, index) => {
      const parts = segment.text.split("\n");
      lines.push({ key: `t${index}`, text: parts[parts.length - 1], style: style.translated, layer: "translated" });
      lines.push({ key: `o${index}`, text: parts.slice(0, -1).join("\n"), style: style.original, layer: "original" });
    });
  } else if (mode === "zh") {
    active(translated).forEach((segment, index) => lines.push({ key: `t${index}`, text: segment.text, style: style.translated, layer: "translated" }));
  } else {
    active(original).forEach((segment, index) => lines.push({ key: `o${index}`, text: segment.text, style: style.original, layer: "original" }));
  }
  const visible = lines.filter(line => line.layer === "original" ? style.show_original !== false : style.show_translated !== false);
  return <div className="subtitle-overlay" style={box}>{visible.map(line => (
    <div key={line.key} className="subtitle-overlay-line" style={{
      ...positionCss(line.style),
      fontFamily: line.style.font_family,
      fontSize: Math.max(8, line.style.font_size * scale),
      textAlign: line.style.align,
      backgroundColor: line.style.background_opacity > 0 ? hexToRgba(line.style.background_color, line.style.background_opacity) : undefined,
      padding: line.style.background_opacity > 0 ? "0.05em 0.2em" : undefined,
    }}><StyledText text={line.text} style={line.style} scale={scale} /></div>
  ))}</div>;
}
