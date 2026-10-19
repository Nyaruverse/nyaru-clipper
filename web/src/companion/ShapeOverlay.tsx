import type { CSSProperties } from "react";
import type { Shape } from "./companionApi";

export function hexToRgba(hex: string, opacity: number): string {
  const value = parseInt(hex.slice(1), 16);
  return `rgba(${(value >> 16) & 255}, ${(value >> 8) & 255}, ${value & 255}, ${opacity})`;
}

/** 图形overlay：矩形显示在所有字幕图层下方，随预览画面等比缩放。
 *  根元素自身就是定位层（.shape-overlay 为 absolute），宽度高度由 box 内联样式提供，
 *  矩形的百分比坐标相对该层计算——不能再在外部额外包一层定位 div（会导致尺寸塌缩为 0）。 */
export function ShapeOverlay({ shapes, scale, style }: { shapes: readonly Shape[]; scale: number; style?: CSSProperties }) {
  return <div className="shape-overlay" style={style} aria-hidden>
    {shapes.map((shape, index) => <div key={index} style={{
      position: "absolute", left: `${shape.x}%`, top: `${shape.y}%`, transform: "translate(-50%, -50%)",
      width: `${shape.width}%`, height: `${shape.height}%`,
      borderRadius: shape.radius * scale,
      backgroundColor: hexToRgba(shape.fill_color, shape.fill_opacity),
      border: shape.outline_width > 0 ? `${Math.max(1, shape.outline_width * scale)}px solid ${shape.outline_color}` : undefined,
    }} />)}
  </div>;
}
