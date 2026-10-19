import { useEffect, useRef, useState } from "react";
import { Star } from "lucide-react";
import { toggleFontPin, useFontPins } from "./fontPins";

/** 字体选择器：模糊搜索 + 收藏置顶（多选，存 localStorage，多实例同步） */
export function FontPicker({ value, fonts, onChange }: { value: string; fonts: readonly string[]; onChange: (font: string) => void }) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const pins = useFontPins();
  const rootRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const close = (event: MouseEvent) => { if (rootRef.current && !rootRef.current.contains(event.target as Node)) setOpen(false); };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, [open]);
  const keyword = query.trim().toLowerCase();
  const pool = fonts.includes(value) ? fonts : [value, ...fonts];
  const matched = keyword ? pool.filter(font => font.toLowerCase().includes(keyword)) : pool;
  const shown = [...matched.filter(font => pins.includes(font)), ...matched.filter(font => !pins.includes(font))];
  return <div className="font-picker" ref={rootRef}>
    <button className="ny-input font-picker-current" type="button" style={{ fontFamily: value }} onClick={() => setOpen(v => !v)}>{value}</button>
    {open && <div className="font-picker-pop">
      <input className="ny-input" autoFocus placeholder="搜索字体…" value={query} onChange={event => setQuery(event.target.value)} />
      <ul role="listbox">
        {shown.map(font => <li key={font}>
          <button type="button" role="option" aria-selected={font === value} style={{ fontFamily: font }} onClick={() => { onChange(font); setOpen(false); setQuery(""); }}>{font}</button>
          <button type="button" className="font-pin" aria-pressed={pins.includes(font)} title={pins.includes(font) ? "取消置顶" : "置顶"} onClick={() => toggleFontPin(font)}><Star size={13} fill={pins.includes(font) ? "currentColor" : "none"} /></button>
        </li>)}
        {!shown.length && <li className="font-picker-empty">无匹配字体</li>}
      </ul>
    </div>}
  </div>;
}
