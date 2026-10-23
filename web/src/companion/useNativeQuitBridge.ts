import { useEffect, useRef } from 'react';

declare global {
  interface Window {
    nyaruQuit?: {
      readonly status: () => 'dirty' | 'clean';
      readonly save: () => Promise<string | null>;
    };
  }
}

export function useNativeQuitBridge(settingsDirty: boolean, hasUnsaved: () => boolean, flush: () => Promise<string | null>,
  metadataUnsaved?: () => boolean) {
  const settings = useRef(settingsDirty);
  settings.current = settingsDirty;
  useEffect(() => {
    const settingsMessage = '默认设置尚未保存，请先在设置中保存，再退出';
    const bridge = {
      status: (): 'dirty' | 'clean' => settings.current || hasUnsaved() || metadataUnsaved?.() ? 'dirty' : 'clean',
      save: async () => {
        if (settings.current) return settingsMessage;
        if (metadataUnsaved?.()) return '任务标题与标签尚未保存，请在任务记录中保存后再退出';
        const error = await flush();
        return error ?? (settings.current ? settingsMessage : null);
      },
    };
    window.nyaruQuit = bridge;
    const guard = (event: BeforeUnloadEvent) => {if (bridge.status() === 'dirty') {event.preventDefault();event.returnValue = '';}};
    window.addEventListener('beforeunload', guard);
    return () => {window.removeEventListener('beforeunload', guard);if (window.nyaruQuit === bridge) delete window.nyaruQuit;};
  }, [hasUnsaved, flush, metadataUnsaved]);
}
