import { useCallback, useEffect, useRef, useState } from 'react';
import { subtitleApi } from './subtitleStyle';
import { documentProblem, parseDocument, type SubtitleDocument } from './subtitleDocument';

interface Session {
  readonly document: SubtitleDocument | null;
  readonly saved: SubtitleDocument | null;
  readonly past: readonly SubtitleDocument[];
  readonly future: readonly SubtitleDocument[];
  readonly saving: boolean;
  readonly error: string | null;
}
const empty: Session = { document: null, saved: null, past: [], future: [], saving: false, error: null };

export function useSubtitleDocument(id: string | null, enabled: boolean, sourceToken = '') {
  const [sessions, setSessions] = useState<Readonly<Record<string, Session>>>({});
  const loading = useRef(new Set<string>());
  const inFlight = useRef(new Set<string>());
  const sourceTokens = useRef(new Map<string, string>());
  const latest = useRef(sessions);
  latest.current = sessions;
  const mounted = useRef(true);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);

  const load = useCallback((key: string, source = false) => {
    if (loading.current.has(key)) return;
    const before = latest.current[key]?.document;
    loading.current.add(key);
    void subtitleApi<unknown>(`/jobs/${key}/subtitle-document${source ? '?source=true' : ''}`).then(parseDocument).then(document => {
      if (mounted.current) setSessions(current => {
        const session = current[key];
        if (session?.document && session.document !== before) return { ...current, [key]: { ...session, error: '载入期间的修改已保留；请核对当前编辑稿后重试，或从源字幕重新开始' } };
        return { ...current, [key]: { ...empty, document, saved: source ? null : document } };
      });
    }).catch((error: unknown) => {
      if (mounted.current) setSessions(current => ({ ...current, [key]: { ...current[key] ?? empty, error: error instanceof Error ? error.message : '字幕编辑稿载入失败' } }));
    }).finally(() => loading.current.delete(key));
  }, []);

  useEffect(() => { if (id && enabled && !sessions[id]) load(id); }, [id, enabled, sessions, load]);
  useEffect(() => {
    if (!id || !enabled) return;
    const previous = sourceTokens.current.get(id);
    sourceTokens.current.set(id, sourceToken);
    if (previous !== undefined && previous !== sourceToken) {
      const session = latest.current[id];
      if (session?.document && session.document !== session.saved) setSessions(current => ({ ...current, [id]: { ...current[id], error: '源字幕状态已变化；当前修改已保留，请保存副本后核对或从源字幕重新开始' } }));
      else load(id);
    }
  }, [id, enabled, sourceToken, load]);

  const save = useCallback(async (key: string, sent: SubtitleDocument) => {
    if (inFlight.current.has(key)) return;
    inFlight.current.add(key);
    setSessions(current => ({ ...current, [key]: { ...current[key], saving: true } }));
    try {
      const saved = parseDocument(await subtitleApi<unknown>(`/jobs/${key}/subtitle-document`, sent));
      if (mounted.current) setSessions(current => {
        const session = current[key];
        if (!session?.document) return current;
        return { ...current, [key]: { ...session, saved,
          document: session.document === sent ? saved : { ...session.document, revision: saved.revision }, saving: false, error: null } };
      });
    } catch (error) {
      if (mounted.current) setSessions(current => ({ ...current, [key]: { ...current[key], saving: false, error: error instanceof Error ? error.message : '保存失败，请重试' } }));
    } finally { inFlight.current.delete(key); }
  }, []);

  useEffect(() => {
    const pending = Object.entries(sessions).filter(([, session]) => session.document && session.document !== session.saved && !session.saving && !session.error && !documentProblem(session.document));
    if (!pending.length) return;
    const timer = window.setTimeout(() => {
      for (const [key, session] of pending) if (session.document) void save(key, session.document);
    }, 650);
    return () => window.clearTimeout(timer);
  }, [sessions, save]);

  useEffect(() => {
    const warn = (event: BeforeUnloadEvent) => {
      if (Object.values(sessions).some(session => session.document && session.document !== session.saved)) { event.preventDefault(); event.returnValue = ''; }
    };
    window.addEventListener('beforeunload', warn);
    return () => window.removeEventListener('beforeunload', warn);
  }, [sessions]);

  const session = id ? sessions[id] ?? empty : empty;
  const change = useCallback((update: (document: SubtitleDocument) => SubtitleDocument) => {
    if (!id) return;
    setSessions(current => {
      const previous = current[id];
      if (!previous?.document) return current;
      const document = update(previous.document);
      if (document === previous.document) return current;
      return { ...current, [id]: { ...previous, document, past: [...previous.past.slice(-99), previous.document], future: [] } };
    });
  }, [id]);
  const travel = (redo: boolean) => {
    if (!id) return;
    setSessions(current => {
      const previous = current[id];
      if (!previous?.document) return current;
      const stack = redo ? previous.future : previous.past, target = stack[stack.length - 1];
      if (!target) return current;
      const document = { ...target, revision: previous.document.revision };
      return { ...current, [id]: { ...previous, document,
        past: redo ? [...previous.past, previous.document] : previous.past.slice(0, -1),
        future: redo ? previous.future.slice(0, -1) : [...previous.future, previous.document] } };
    });
  };
  return { document: session.document, change, dirty: !!session.document && session.document !== session.saved,
    saving: session.saving, error: session.error, canUndo: !!session.past.length, canRedo: !!session.future.length,
    undo: () => travel(false), redo: () => travel(true),
    retry: () => { if (id && session.document && !documentProblem(session.document)) void save(id, session.document); else if (id) load(id); },
    reload: () => { if (id) load(id); },
    resetSource: () => { if (id) load(id, true); },
  };
}
