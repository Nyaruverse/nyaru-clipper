import { useMemo, useRef, useState, type ChangeEvent, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BookA, Check, Trash2, Upload, X } from "lucide-react";
import { api, TERM_CATEGORIES, type GlossaryCandidate, type GlossaryStore, type GlossaryTerm, type TermCategory } from "./companionApi";

/** 翻译术语表：统一人名与专有名词译法，翻译时自动应用；翻译完成后自动识别未收录词条 */
export function GlossaryPanel() {
  const queryClient = useQueryClient();
  const glossaryQuery = useQuery({ queryKey: ["companion", "glossary"], queryFn: () => api<GlossaryStore>("/glossary") });
  const [srcDraft, setSrcDraft] = useState("");
  const [dstDraft, setDstDraft] = useState("");
  const [categoryDraft, setCategoryDraft] = useState<TermCategory>("术语");
  const [termQuery, setTermQuery] = useState("");
  const [formError, setFormError] = useState<string | null>(null);
  const [importMessage, setImportMessage] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const formRef = useRef<HTMLFormElement>(null);
  const srcInputRef = useRef<HTMLInputElement>(null);
  /** 点击词条：填入编辑表单并平滑滚动回编辑栏、聚焦原文输入框 */
  function editTerm(term: GlossaryTerm) {
    setSrcDraft(term.src);
    setDstDraft(term.dst);
    setCategoryDraft(term.category);
    formRef.current?.scrollIntoView({ behavior: "smooth", block: "center" });
    srcInputRef.current?.focus({ preventScroll: true });
  }
  const apply = (data: GlossaryStore) => queryClient.setQueryData(["companion", "glossary"], data);
  const saveTerms = useMutation({ mutationFn: (terms: GlossaryTerm[]) => api<GlossaryStore>("/glossary", { terms }, "PUT"), onSuccess: apply,
    onError: err => setFormError(err.message) });
  const accept = useMutation({ mutationFn: (payload: { index: number; candidate: GlossaryCandidate }) =>
    api<GlossaryStore>(`/glossary/candidates/${payload.index}/accept`, payload.candidate), onSuccess: apply,
    onError: err => setFormError(err.message) });
  const ignore = useMutation({ mutationFn: (index: number) => api<GlossaryStore>(`/glossary/candidates/${index}/ignore`, {}), onSuccess: apply,
    onError: err => setFormError(err.message) });
  const importTerms = useMutation({ mutationFn: (text: string) => api<GlossaryStore>("/glossary/import", { text }),
    onSuccess: data => { apply(data); setImportMessage(`已导入，当前共 ${data.terms.length} 条`); },
    onError: err => { setFormError(err.message); setImportMessage(null); } });
  const store = glossaryQuery.data;
  const terms = useMemo(() => store?.terms ?? [], [store]);
  const candidates = store?.candidates ?? [];
  const keyword = termQuery.trim().toLowerCase();
  const shownTerms = keyword ? terms.filter(term => term.src.toLowerCase().includes(keyword) || term.dst.toLowerCase().includes(keyword)) : terms;
  const editing = terms.some(term => term.src === srcDraft.trim());
  const mutating = saveTerms.isPending || accept.isPending || ignore.isPending || importTerms.isPending;
  function submitTerm(event: FormEvent) {
    event.preventDefault();
    setFormError(null);
    const src = srcDraft.trim();
    const dst = dstDraft.trim();
    if (!src || !dst) return;
    const next: GlossaryTerm = { src, dst, category: categoryDraft };
    saveTerms.mutate([...terms.filter(term => term.src !== src), next]);
    setSrcDraft("");
    setDstDraft("");
    setCategoryDraft("术语");
  }
  function pickFile() { setFormError(null); setImportMessage(null); fileRef.current?.click(); }
  async function onFileChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    try {
      const text = await file.text();
      importTerms.mutate(text);
    } catch {
      setFormError("读取文件失败，请重试");
    }
  }
  return <section className="companion-panel companion-glossary" aria-label="翻译术语表">
    <h2><BookA size={17} />翻译术语表 <span>{terms.length} 条</span>
      <button className="ny-button ny-button--quiet glossary-import-btn" type="button" disabled={mutating} onClick={pickFile} title="从 TXT 文件导入，每行格式：# 原文=统一译文">
        <Upload size={14} />导入 TXT
      </button>
    </h2>
    <input ref={fileRef} type="file" accept=".txt,text/plain" hidden onChange={onFileChange} />
    <p className="companion-muted">统一人名与专有名词译法，翻译时自动应用；每次翻译后自动识别未收录词条。</p>
    {importMessage && <p className="glossary-import-msg" role="status">{importMessage}</p>}
    {candidates.length > 0 && <div className="glossary-candidates">
      <h3>待确认候选 <span>{candidates.length}</span></h3>
      {candidates.map((candidate, index) => <div className="glossary-row" key={`${candidate.src}-${index}`}>
        <span className="glossary-text"><strong>{candidate.src}</strong><small>{candidate.dst}</small></span>
        <span className="glossary-badge">{candidate.category}</span>
        <span className="glossary-actions">
          <button className="ny-button" type="button" disabled={mutating} title="加入术语表" onClick={() => { setFormError(null); accept.mutate({ index, candidate }); }}><Check size={14} />接受</button>
          <button className="ny-button ny-button--quiet" type="button" disabled={mutating} title="忽略并不再提示" onClick={() => { setFormError(null); ignore.mutate(index); }}><X size={14} />忽略</button>
        </span>
      </div>)}
    </div>}
    <form className="glossary-form" ref={formRef} onSubmit={submitTerm}>
      <div className="style-grid">
        <label>原文<input className="ny-input" ref={srcInputRef} required maxLength={64} placeholder="日文原文" value={srcDraft} onChange={event => setSrcDraft(event.target.value)} /></label>
        <label>统一译名<input className="ny-input" required maxLength={64} placeholder="中文译名" value={dstDraft} onChange={event => setDstDraft(event.target.value)} /></label>
      </div>
      <div className="glossary-form-actions">
        <select className="ny-input" aria-label="词条分类" value={categoryDraft} onChange={event => setCategoryDraft(event.target.value as TermCategory)}>
          {TERM_CATEGORIES.map(category => <option key={category} value={category}>{category}</option>)}
        </select>
        <button className="ny-button" type="submit" disabled={!srcDraft.trim() || !dstDraft.trim() || mutating}>{editing ? "保存词条" : "添加词条"}</button>
      </div>
    </form>
    {formError && <p className="companion-error" role="alert">{formError}</p>}
    <input className="ny-input glossary-search" type="search" placeholder="搜索词条…" value={termQuery} onChange={event => setTermQuery(event.target.value)} />
    {shownTerms.map(term => <div className="glossary-row" key={term.src}>
      <button className="glossary-text glossary-edit" type="button" title="点击编辑该词条" onClick={() => editTerm(term)}>
        <strong>{term.src}</strong><small>{term.dst}</small>
      </button>
      <span className="glossary-badge">{term.category}</span>
      <span className="glossary-actions">
        <button className="ny-button ny-button--quiet" type="button" disabled={mutating} title="删除词条" onClick={() => { setFormError(null); saveTerms.mutate(terms.filter(item => item.src !== term.src)); }}><Trash2 size={14} /></button>
      </span>
    </div>)}
    {!terms.length && <p className="companion-muted">还没有词条。添加后翻译会自动采用统一译法。</p>}
    {terms.length > 0 && !shownTerms.length && <p className="companion-muted">无匹配词条。</p>}
  </section>;
}

