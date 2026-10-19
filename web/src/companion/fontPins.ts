import { useSyncExternalStore } from "react";

/* 字体置顶列表全局共享：所有字体选择器（原文/译文/逐条字幕）实时同步，持久化到 localStorage */
const FONT_PINS_KEY = "companion-font-pins";

function loadFontPins(): string[] {
  try {
    const parsed = JSON.parse(localStorage.getItem(FONT_PINS_KEY) ?? "[]");
    return Array.isArray(parsed) ? parsed.filter(item => typeof item === "string") : [];
  } catch { return []; }
}

let fontPinsCache: string[] = loadFontPins();
const pinListeners = new Set<() => void>();

function subscribeFontPins(listener: () => void) {
  pinListeners.add(listener);
  return () => { pinListeners.delete(listener); };
}

export function toggleFontPin(font: string) {
  fontPinsCache = fontPinsCache.includes(font) ? fontPinsCache.filter(item => item !== font) : [...fontPinsCache, font];
  try { localStorage.setItem(FONT_PINS_KEY, JSON.stringify(fontPinsCache)); } catch { /* 忽略写入失败 */ }
  pinListeners.forEach(listener => listener());
}

export function useFontPins(): string[] {
  return useSyncExternalStore(subscribeFontPins, () => fontPinsCache);
}
