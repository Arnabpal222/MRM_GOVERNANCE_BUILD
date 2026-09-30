import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { api, blobUrl } from "../../api/client";
import type { Completeness, DocumentDetail, DocumentMeta, ModelSummary } from "../../api/types";
import { ErrorState, Loading } from "../../components/States";

export function useDocumentMeta() {
  return useQuery({ queryKey: ["document-meta"], queryFn: () => api<DocumentMeta>("/api/documents/meta"), staleTime: 60_000 });
}

export function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1048576) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / 1048576).toFixed(1)} MB`;
}

export function invalidateDocuments(qc: ReturnType<typeof useQueryClient>, modelId?: string) {
  qc.invalidateQueries({ queryKey: ["documents"] });
  qc.invalidateQueries({ queryKey: ["document-folders"] });
  qc.invalidateQueries({ queryKey: ["completeness"] });
  qc.invalidateQueries({ queryKey: ["models"] });
  if (modelId) qc.invalidateQueries({ queryKey: ["model", modelId] });
}

/** Individual upload (BRD §29): model → type → version → file. Stored when saved. */
export function SingleUploadForm({ fixedModelId, onDone }: { fixedModelId?: string; onDone?: (d: DocumentDetail) => void }) {
  const qc = useQueryClient();
  const meta = useDocumentMeta();
  const models = useQuery({ queryKey: ["models", ""], queryFn: () => api<ModelSummary[]>("/api/models"), enabled: !fixedModelId });
  const [file, setFile] = useState<File | null>(null);
  const [form, setForm] = useState({ model_id: fixedModelId ?? "", document_type: "", version: "", effective_date: "",
    title: "", confidentiality: "", change_reason: "" });
  const upload = useMutation({
    mutationFn: () => {
      const fd = new FormData();
      fd.append("file", file!);
      for (const [k, v] of Object.entries(form)) if (v) fd.append(k, v);
      return api<DocumentDetail>("/api/documents", { method: "POST", body: fd });
    },
    onSuccess: (d) => {
      invalidateDocuments(qc, d.model_id);
      setFile(null);
      onDone?.(d);
    },
  });
  if (meta.isLoading) return <Loading />;
  if (meta.isError) return <ErrorState error={meta.error} />;
  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => setForm({ ...form, [k]: e.target.value });
  const m = meta.data!;

  return (
    <form className="panel action-form" onSubmit={(e) => { e.preventDefault(); upload.mutate(); }}>
      <h4>Upload a document <small>{m.extensions.map((x) => `.${x}`).join(", ")} · up to {m.max_document_mb} MB</small></h4>
      <div className="form-grid">
        {!fixedModelId && (
          <label className="field">Model
            <input className="input" list="doc-model-list" value={form.model_id} onChange={set("model_id")} placeholder="M-0012" />
            <datalist id="doc-model-list">
              {(models.data ?? []).map((m) => <option key={m.model_id} value={m.model_id}>{m.model_name}</option>)}
            </datalist>
          </label>
        )}
        <label className="field">Document type
          <select className="select" value={form.document_type} onChange={set("document_type")}>
            <option value="">—</option>
            {m.document_types.map((t) => <option key={t}>{t}</option>)}
          </select>
        </label>
        <label className="field">Version <input className="input" value={form.version} onChange={set("version")} placeholder="auto (1.0, next)" /></label>
        <label className="field">Effective date <input className="input" type="date" value={form.effective_date} onChange={set("effective_date")} /></label>
        <label className="field">Title <input className="input" value={form.title} onChange={set("title")} placeholder="from the file name" /></label>
        <label className="field">Confidentiality
          <select className="select" value={form.confidentiality} onChange={set("confidentiality")}>
            <option value="">{m.default_confidentiality} (default)</option>
            {m.confidentiality_levels.map((c) => <option key={c}>{c}</option>)}
          </select>
        </label>
        <label className="field">File <input className="input" type="file" accept={m.extensions.map((x) => `.${x}`).join(",")}
          onChange={(e) => setFile(e.target.files?.[0] ?? null)} /></label>
        <label className="field">Change reason <input className="input" value={form.change_reason} onChange={set("change_reason")} /></label>
      </div>
      <p className="note">A file identical to one already stored is refused. A file with the same model, type and title becomes the next version; versions are never overwritten.</p>
      {upload.isError && <div className="errline">{(upload.error as Error).message}</div>}
      <div><button className="btn primary" disabled={!file || !form.document_type || !form.model_id || upload.isPending}>
        {upload.isPending ? "Uploading…" : "Upload"}</button></div>
    </form>
  );
}

export function CompletenessPanel({ modelId }: { modelId: string }) {
  const q = useQuery({
    queryKey: ["completeness", modelId],
    queryFn: () => api<Completeness[]>(`/api/documents/completeness?model_id=${modelId}`),
  });
  if (q.isLoading) return <Loading />;
  if (q.isError) return <ErrorState error={q.error} />;
  const c = q.data![0];
  if (!c) return null;
  return (
    <section className="panel">
      <h4>Required documents <small>{c.lifecycle_phase} · {c.score === null ? "none required" : `${c.score}% complete`}</small></h4>
      {c.required.length === 0 ? <p className="note">No documents are required in this phase.</p> : (
        <ul className="checklist">
          {c.required.map((t) => (
            <li key={t} className={c.present.includes(t) ? "ok" : "miss"}>
              <span className="mk">{c.present.includes(t) ? "✓" : "✕"}</span>{t}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

/** Inline preview for PDFs; other types offer download. */
export function Preview({ documentId, version, mime }: { documentId: string; version: string; mime: string }) {
  const [url, setUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    let current: string | null = null;
    setUrl(null);
    if (mime === "application/pdf") {
      blobUrl(`/api/documents/${documentId}/versions/${version}/download?inline=true`)
        .then((u) => { current = u; setUrl(u); })
        .catch((e) => setError(e.message));
    }
    return () => { if (current) URL.revokeObjectURL(current); };
  }, [documentId, version, mime]);
  if (mime !== "application/pdf") return <p className="note">Preview is available for PDF files. Download the file to view it.</p>;
  if (error) return <div className="errline">{error}</div>;
  if (!url) return <Loading label="Loading preview…" />;
  return <iframe className="doc-preview" title={`${documentId} v${version}`} src={url} />;
}
