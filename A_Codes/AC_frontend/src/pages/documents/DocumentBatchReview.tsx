import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, downloadFile } from "../../api/client";
import type { DocumentBatch, ModelSummary, UploadItem } from "../../api/types";
import { useAuth } from "../../auth/AuthContext";
import { EmptyState, ErrorState, Loading } from "../../components/States";
import { BatchStatus } from "../imports/BatchDetail";
import { formatBytes, invalidateDocuments, useDocumentMeta } from "./shared";

const RUNNING = ["Validating", "Processing"];
const EDITABLE = ["Ready", "Validation Failed", "Failed"];
const ITEM_TONE: Record<string, string> = {
  Ready: "p-info", Stored: "p-good", "Needs mapping": "p-warn", Invalid: "p-bad", Failed: "p-bad", Skipped: "p-mute", Uploaded: "p-mute",
};

function confidence(c: number | null) {
  if (c === null) return null;
  const tone = c >= 0.85 ? "p-good" : c >= 0.7 ? "p-info" : "p-warn";
  return <span className={`pill ${tone}`}>{Math.round(c * 100)}%</span>;
}

/** Method B (BRD §33): assign one model to every file under a folder. */
function FolderMapping({ items, models, onApply, disabled }: {
  items: UploadItem[]; models: ModelSummary[]; disabled: boolean; onApply: (ids: number[], modelId: string) => void;
}) {
  const groups = useMemo(() => {
    const map = new Map<string, UploadItem[]>();
    for (const i of items) {
      if (["Invalid", "Stored"].includes(i.status)) continue;
      const parts = i.relative_path.split("/");
      const key = parts.length > 1 ? parts.slice(0, -1).join("/") : "(top level)";
      map.set(key, [...(map.get(key) ?? []), i]);
    }
    return [...map.entries()];
  }, [items]);
  const [choice, setChoice] = useState<Record<string, string>>({});
  if (!groups.length) return null;
  return (
    <section className="panel">
      <h4>Folder → model mapping <small>apply one model to all files in a folder</small></h4>
      <div className="tablewrap">
        <table>
          <thead><tr><th>Folder</th><th>Files</th><th>Detected model(s)</th><th>Assign model</th></tr></thead>
          <tbody>
            {groups.map(([folder, list]) => {
              const detected = [...new Set(list.map((i) => i.model_id).filter(Boolean))];
              return (
                <tr key={folder}>
                  <td className="mono">{folder}</td>
                  <td className="mono">{list.length}</td>
                  <td>{detected.length ? detected.map((m) => <span key={m} className="pill p-acc" style={{ marginRight: 4 }}>{m}</span>) : <span className="pill p-warn">none</span>}</td>
                  <td>
                    <span className="filters">
                      <input className="input" list="batch-models" placeholder="M-0012" style={{ width: 120 }}
                             value={choice[folder] ?? ""} onChange={(e) => setChoice({ ...choice, [folder]: e.target.value.trim() })} />
                      <button className="btn sm" disabled={disabled || !choice[folder]}
                              onClick={() => onApply(list.map((i) => i.item_id), choice[folder])}>Apply</button>
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <datalist id="batch-models">{models.map((m) => <option key={m.model_id} value={m.model_id}>{m.model_name}</option>)}</datalist>
    </section>
  );
}

export function DocumentBatchReview() {
  const { batchId } = useParams();
  const qc = useQueryClient();
  const { can } = useAuth();
  const meta = useDocumentMeta();
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState("");
  const batch = useQuery({
    queryKey: ["document-batch", batchId],
    queryFn: () => api<DocumentBatch>(`/api/documents/batches/${batchId}`),
    refetchInterval: (q) => (q.state.data && RUNNING.includes(q.state.data.status) ? 1000 : false),
  });
  const models = useQuery({ queryKey: ["models", ""], queryFn: () => api<ModelSummary[]>("/api/models") });
  const refresh = (b?: DocumentBatch) => {
    if (b) qc.setQueryData(["document-batch", batchId], b);
    qc.invalidateQueries({ queryKey: ["document-batch", batchId] });
    qc.invalidateQueries({ queryKey: ["document-batches"] });
  };
  const update = useMutation({
    mutationFn: (body: Record<string, unknown>) => api<DocumentBatch>(`/api/documents/batches/${batchId}/items`, { method: "PATCH", json: body }),
    onSuccess: refresh,
    onError: (e) => setError((e as Error).message),
  });
  const act = useMutation({
    mutationFn: (what: "confirm" | "cancel") => api<DocumentBatch>(`/api/documents/batches/${batchId}/${what}`, { method: "POST" }),
    onSuccess: (b) => { refresh(b); invalidateDocuments(qc); },
    onError: (e) => setError((e as Error).message),
  });

  if (batch.isLoading) return <Loading />;
  if (batch.isError) return <ErrorState error={batch.error} title={`Batch ${batchId}`} />;
  const b = batch.data!;
  const editable = EDITABLE.includes(b.status) && can("document:upload");
  const running = RUNNING.includes(b.status);
  const counts = b.items.reduce<Record<string, number>>((acc, i) => ({ ...acc, [i.status]: (acc[i.status] ?? 0) + 1 }), {});
  const shown = statusFilter ? b.items.filter((i) => i.status === statusFilter) : b.items;
  const setItem = (item: UploadItem, changes: Record<string, unknown>) => { setError(null); update.mutate({ item_ids: [item.item_id], ...changes }); };

  return (
    <div className="stack">
      <header>
        <div className="eyebrow"><Link to="/documents">Document Centre</Link> · Upload batch</div>
        <h1 className="mono" style={{ fontSize: 26 }}>{b.batch_id} <BatchStatus status={b.status} /></h1>
        <p className="lede">{b.total_files} file(s) · {b.source} upload by {b.uploaded_by ?? "system"} · {b.created_at ? new Date(b.created_at).toLocaleString() : ""}.
          {b.manifest_files.length > 0 && <> Manifest: <span className="mono">{b.manifest_files.join(", ")}</span>.</>}</p>
      </header>

      {running && (
        <div className="panel">
          <h4>{b.status === "Validating" ? "Analysing files (nothing is stored yet)" : "Storing documents"}</h4>
          <div className="bar"><i style={{ width: `${b.progress?.files_total ? Math.round(((b.progress.files_done ?? 0) / b.progress.files_total) * 100) : 5}%` }} /></div>
          <p className="note" style={{ marginTop: 8 }}>{b.progress?.current_file ?? "Queued…"} — you can leave this page.</p>
        </div>
      )}
      {b.manifest_errors.length > 0 && (
        <div className="state error"><b>Manifest problems</b>{b.manifest_errors.slice(0, 10).map((e) => <div key={e}>{e}</div>)}</div>
      )}

      {!running && (
        <div className="panel">
          <div className="tally">
            {["Ready", "Needs mapping", "Skipped", "Invalid", "Stored", "Failed"].map((s) => (
              <button key={s} className={`t${statusFilter === s ? " sel" : ""}`} onClick={() => setStatusFilter(statusFilter === s ? "" : s)}>
                <b>{counts[s] ?? 0}</b><span>{s}</span>
              </button>
            ))}
          </div>
          <div className="filters" style={{ marginTop: 12 }}>
            {editable && (
              <button className="btn primary" disabled={!counts.Ready || act.isPending} onClick={() => act.mutate("confirm")}>
                Store {counts.Ready ?? 0} document{counts.Ready === 1 ? "" : "s"}
              </button>
            )}
            {editable && <button className="btn" disabled={act.isPending} onClick={() => act.mutate("cancel")}>Cancel batch</button>}
            <button className="btn" onClick={() => downloadFile(`/api/documents/batches/${b.batch_id}/error-report`, `${b.batch_id}_document_errors.csv`).catch((e) => setError(e.message))}>
              Download issues report
            </button>
          </div>
          {error && <div className="errline" style={{ marginTop: 8 }}>{error}</div>}
        </div>
      )}

      {editable && models.data && (
        <FolderMapping items={b.items} models={models.data} disabled={update.isPending}
                       onApply={(ids, modelId) => { setError(null); update.mutate({ item_ids: ids, model_id: modelId }); }} />
      )}

      {shown.length === 0 ? <EmptyState title="No files in this view" /> : (
        <div className="tablewrap">
          <table>
            <thead><tr><th>File</th><th>Model</th><th>Type</th><th>Confidence</th><th>Version</th><th>Action</th><th>Status</th></tr></thead>
            <tbody>
              {shown.map((i) => {
                const locked = !editable || ["Invalid", "Stored"].includes(i.status);
                return (
                  <tr key={i.item_id}>
                    <td className="mono" style={{ maxWidth: 360 }}>
                      {i.relative_path}
                      <div style={{ color: "var(--faint)" }}>{formatBytes(i.size_bytes)} · sha256 {i.checksum.slice(0, 10)}…</div>
                      {i.duplicate_kind && <div style={{ color: "var(--warn)" }}>
                        {i.duplicate_kind === "exact" ? "Identical to" : i.duplicate_kind === "in_batch" ? "Same file as" : "New version of"} {i.duplicate_of}</div>}
                      {i.error && <div className="field-error">{i.error}</div>}
                    </td>
                    <td>
                      {locked ? <span className="mono">{i.model_id ?? "—"}</span> : (
                        <input className="input" list="batch-models" style={{ width: 110 }} defaultValue={i.model_id ?? ""}
                               onBlur={(e) => e.target.value.trim() !== (i.model_id ?? "") && setItem(i, { model_id: e.target.value.trim() || null })} />
                      )}
                      {i.model_source && <div style={{ color: "var(--faint)", fontSize: 11 }}>from {i.model_source}</div>}
                    </td>
                    <td>
                      {locked ? i.document_type ?? "—" : (
                        <select className="select" value={i.document_type ?? ""} onChange={(e) => setItem(i, { document_type: e.target.value || null })}>
                          <option value="">— choose —</option>
                          {(meta.data?.document_types ?? []).map((t) => <option key={t}>{t}</option>)}
                        </select>
                      )}
                    </td>
                    <td title={i.type_reason ?? ""}>{confidence(i.type_confidence)}<div style={{ color: "var(--faint)", fontSize: 11 }}>{i.type_source}</div></td>
                    <td>
                      {locked ? <span className="mono">{i.stored_version ?? i.version ?? "auto"}</span> : (
                        <input className="input" style={{ width: 70 }} defaultValue={i.version ?? ""} placeholder="auto"
                               onBlur={(e) => e.target.value.trim() !== (i.version ?? "") && setItem(i, { version: e.target.value.trim() || null })} />
                      )}
                    </td>
                    <td>
                      {locked ? i.action : (
                        <select className="select" value={i.action} onChange={(e) => setItem(i, { action: e.target.value })}>
                          <option value="create">Store</option>
                          <option value="new_version">Store as new version</option>
                          <option value="skip">Skip</option>
                        </select>
                      )}
                    </td>
                    <td>
                      <span className={`pill ${ITEM_TONE[i.status] ?? "p-mute"}`}>{i.status}</span>
                      {i.document_id && <div><Link className="mono" to={`/documents/${i.document_id}`}>{i.document_id} v{i.stored_version}</Link></div>}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
