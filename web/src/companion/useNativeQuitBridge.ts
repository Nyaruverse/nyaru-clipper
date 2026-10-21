import { useEffect, useRef } from 'react';

declare global {
  interface Window {
    nyaruQuit?: {
      readonly status: () => 'dirty' | 'clean';
      readonly save: () => Promise<string | null>;
    };
  }
}

export function useNativeQuitBridge(settingsDirty: boolean, hasUnsaved: () => boolean, flush: () => Promise<string | null>) {
  const settings = useRef(settingsDirty);
  settings.current = settingsDirty;
  useEffect(() => {
    const settingsMessage = '默认设置尚未保存，请先在设置中保存，再退出';
    const bridge = {
      status: (): 'dirty' | 'clean' => settings.current || hasUnsaved() ? 'dirty' : 'clean',
      save: async () => {
        if (settings.current) return settingsMessage;
        const error = await flush();
        return error ?? (settings.current ? settingsMessage : null);
      },
    };
    window.nyaruQuit = bridge;
    return () => { if (window.nyaruQuit === bridge) delete window.nyaruQuit; };
  }, [hasUnsaved, flush]);
}
