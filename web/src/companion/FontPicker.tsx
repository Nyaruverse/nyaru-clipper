import { useId, useSyncExternalStore } from 'react';

// Font pinning adapted from collaborator commit 69d3fa0; keep the native searchable input.
const key = 'companion-font-pins';
const changed = 'nyaru-font-pins';
function snapshot(): string {
  try { return localStorage.getItem(key) ?? '[]'; } catch { return '[]'; }
}
function subscribe(listener: () => void) {
  window.addEventListener(changed, listener);
  window.addEventListener('storage', listener);
  return () => { window.removeEventListener(changed, listener); window.removeEventListener('storage', listener); };
}
function parsePins(value: string): string[] {
  try {
    const parsed: unknown = JSON.parse(value);
    return Array.isArray(parsed) ? parsed.filter((font: unknown): font is string => typeof font === 'string' && font.length <= 100).slice(0, 50) : [];
  } catch { return []; }
}

export function FontPicker({value, fonts, onChange, label = '字体'}: {value: string; fonts: readonly string[]; onChange: (font: string) => void; label?: string}) {
  const list = useId();
  const pins = parsePins(useSyncExternalStore(subscribe, snapshot));
  const pinned = pins.includes(value);
  return <div className="cue-wide font-picker">
    <label className="ny-field">{label}<input className="ny-input" list={list} maxLength={100} value={value} placeholder="搜索或输入字体名称"
      onChange={event => { if (!/[,{}\\\x00-\x1f\x7f-\x9f]/.test(event.target.value)) onChange(event.target.value); }} />
      <datalist id={list}>{[...new Set([...pins, ...fonts])].map(font => <option key={font} value={font} />)}</datalist>
    </label>
    <div className="cue-checks" role="group" aria-label="字体收藏">
      <button type="button" className="ny-button ny-button--quiet" aria-pressed={pinned} disabled={!value.trim()}
        onClick={() => {
          const next = pinned ? pins.filter(font => font !== value) : [...pins, value].slice(-50);
          try { localStorage.setItem(key, JSON.stringify(next)); window.dispatchEvent(new Event(changed)); }
          catch { window.alert('浏览器未允许保存字体收藏，当前字幕样式仍可正常编辑。'); }
        }}>{pinned ? '取消收藏当前字体' : '收藏当前字体'}</button>
      {pins.map(font => <button type="button" className="ny-button ny-button--quiet" key={font}
        aria-label={`使用收藏字体 ${font}`} onClick={() => onChange(font)}>{font}</button>)}
    </div>
  </div>;
}
