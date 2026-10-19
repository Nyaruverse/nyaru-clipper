import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, Shapes, Trash2 } from "lucide-react";
import { api, type Shape } from "./companionApi";

const MAX_SHAPES = 20;
const DEFAULT_SHAPE: Shape = { x: 50, y: 50, width: 40, height: 20, radius: 0, fill_color: "#000000", fill_opacity: 0.5, outline_color: "#FFFFFF", outline_width: 0 };

/** 图形数据全局共享：编辑面板与视频预览 overlay 用同一 queryKey。
 *  修改即时写入 query 缓存（预览立刻生效），仅保存请求防抖 250ms。 */
export function useShapes() {
  return useQuery({ queryKey: ["companion", "shapes"], queryFn: () => api<{ shapes: Shape[] }>("/shapes") });
}

function ShapeFields({ shape, index, onChange, onDelete }: {
  shape: Shape;
  index: number;
  onChange: (next: Shape) => void;
  onDelete: () => void;
}) {
  const update = <K extends keyof Shape>(key: K, next: Shape[K]) => onChange({ ...shape, [key]: next });
  return <fieldset className="style-block shape-item">
    <legend>矩形 {index + 1}</legend>
    <div className="style-group">
      <h3>位置与尺寸</h3>
      <label className="style-slider">水平 X<span className="style-range"><input type="range" min={0} max={100} step={1} value={shape.x} onChange={event => update("x", Number(event.target.value))} /><span>{Math.round(shape.x)}%</span></span></label>
      <label className="style-slider">垂直 Y<span className="style-range"><input type="range" min={0} max={100} step={1} value={shape.y} onChange={event => update("y", Number(event.target.value))} /><span>{Math.round(shape.y)}%</span></span></label>
      <label className="style-slider">宽度<span className="style-range"><input type="range" min={1} max={100} step={1} value={shape.width} onChange={event => update("width", Number(event.target.value))} /><span>{Math.round(shape.width)}%</span></span></label>
      <label className="style-slider">高度<span className="style-range"><input type="range" min={1} max={100} step={1} value={shape.height} onChange={event => update("height", Number(event.target.value))} /><span>{Math.round(shape.height)}%</span></span></label>
      <label className="style-slider">圆角<span className="style-range"><input type="range" min={0} max={200} step={2} value={shape.radius} onChange={event => update("radius", Number(event.target.value))} /><span>{shape.radius}px</span></span></label>
    </div>
    <div className="style-group">
      <h3>填充</h3>
      <div className="style-grid">
        <label>填充颜色<input type="color" value={shape.fill_color} onChange={event => update("fill_color", event.target.value)} /></label>
        <label>不透明度<span className="style-range"><input type="range" min={0} max={1} step={0.05} value={shape.fill_opacity} onChange={event => update("fill_opacity", Number(event.target.value))} /><span>{Math.round(shape.fill_opacity * 100)}%</span></span></label>
      </div>
    </div>
    <div className="style-group">
      <h3>描边</h3>
      <div className="style-grid">
        <label>描边颜色<input type="color" value={shape.outline_color} onChange={event => update("outline_color", event.target.value)} /></label>
        <label>描边粗细<span className="style-range"><input type="range" min={0} max={40} step={1} value={shape.outline_width} onChange={event => update("outline_width", Number(event.target.value))} /><span>{shape.outline_width}px</span></span></label>
      </div>
      <p className="style-hint">粗细为 0 时不绘制描边。</p>
    </div>
    <button className="ny-button ny-button--quiet shape-delete" type="button" onClick={onDelete}><Trash2 size={14} />删除矩形</button>
  </fieldset>;
}

export function ShapesPanel() {
  const queryClient = useQueryClient();
  const shapesQuery = useShapes();
  const [draft, setDraft] = useState<Shape[] | null>(null);
  const seeded = useRef(false);
  const save = useMutation({
    mutationFn: (next: Shape[]) => api<{ shapes: Shape[] }>("/shapes", { shapes: next }, "PUT"),
    onSuccess: data => { queryClient.setQueryData(["companion", "shapes"], data); },
  });
  const saveMutate = save.mutate;
  useEffect(() => {
    if (!draft) return;
    const timer = window.setTimeout(() => saveMutate(draft), 250);
    return () => window.clearTimeout(timer);
  }, [draft, saveMutate]);
  function commit(next: Shape[]) {
    setDraft(next);
    queryClient.setQueryData(["companion", "shapes"], { shapes: next });
  }
  useEffect(() => {
    if (seeded.current || shapesQuery.isLoading || !shapesQuery.data) return;
    seeded.current = true;
    // 首次使用（存储为空且从未初始化过）自动放一个默认矩形，方便直接调整
    if (!shapesQuery.data.shapes.length && !window.localStorage.getItem("nyaru-shapes-seeded")) {
      window.localStorage.setItem("nyaru-shapes-seeded", "1");
      commit([{ ...DEFAULT_SHAPE }]);
    }
  }, [shapesQuery.data, shapesQuery.isLoading]);
  const shapes = draft ?? shapesQuery.data?.shapes ?? [];
  return <section className="companion-panel companion-shapes" aria-label="图形绘制">
    <h2><Shapes size={17} />图形绘制 <span>{shapes.length}/{MAX_SHAPES}</span></h2>
    <p className="companion-muted">矩形显示在所有字幕下层，预览与合成视频实时生效。</p>
    <button className="ny-button" type="button" disabled={shapes.length >= MAX_SHAPES} onClick={() => commit([...shapes, { ...DEFAULT_SHAPE }])}><Plus size={15} />添加矩形</button>
    {shapes.map((shape, index) => <ShapeFields key={index} shape={shape} index={index}
      onChange={next => commit(shapes.map((item, i) => i === index ? next : item))}
      onDelete={() => commit(shapes.filter((_, i) => i !== index))} />)}
    {!shapes.length && <p className="companion-muted">还没有图形。添加矩形后可调整位置、尺寸、圆角、填充与描边。</p>}
    <p className="companion-footnote">{save.isPending ? "正在保存图形…" : "修改后自动保存"}</p>
    {save.isError && <p className="companion-error" role="alert">{save.error.message}</p>}
  </section>;
}
