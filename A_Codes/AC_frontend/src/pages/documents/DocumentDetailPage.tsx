import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, downloadFile } from "../../api/client";
import type { AuditEvent, DocumentDetail } from "../../api/types";
import { useAuth } from "../../auth/AuthContext";
import { ErrorState, Loading } from "../../components/States";
import { Preview, formatBytes, invalidateDocuments } from "./shared";

export function DocumentDetailPage() {
  const { documentId } = useParams();
  const qc = useQueryClient();
  const { can } = useAuth();
  const [version, setVersion] = useState<string | null>(null);
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);
  const q = useQuery({ queryKey: ["document", documentId], queryFn: () => api<DocumentDetail>(`/api/documents/${documentId}`) });
  const audit = useQuery({
    queryKey: ["audit", { document_id: documentId }],
    queryFn: () => api<AuditEvent[]>(`/api/audit?document_id=${documentId}`),
    enabled: can("audit:read"),
  });
  const act = useMutation({
    mutationFn: ({ path, body }: { path: string; body: unknown }) => api(`/api/documents/${documentId}/${path}`, { method: "POST", json: body }),
    onSuccess: () => { setReason(""); qc.invalidateQueries({ queryKey: ["document", documentId] }); invalidateDocuments(qc, q.data?.model_id); },
    onError: (e) => setError((e as Error).message),
  });

  if (q.isLoading) return <Loading />;
  if (q.isError) return <ErrorState error={q.error} title={`Document ${documentId}`} />;
  const d = q.data!;
  const current = d.versions.find((v) => v.version === (version ?? d.current_version)) ?? d.versions[0];

  return (
    <div className="stack">
      <header>
        <div className="eyebrow"><Link to="/documents">Document Centre</Link> · <Link to={`/models/${d.model_id}`}>{d.model_id}</Link></div>
        <h1><span className="mono" style={{ color: "var(--muted)" }}>{d.document_id}</span> {d.title}</h1>
        <div className="filters">
          <span className="pill p-acc">{d.document_type}</span>
          <span className="pill p-mute mono">v{d.current_version}</span>
          <span className={`pill ${d.status === "Active" ? "p-good" : "p-mute"}`}>{d.status}</span>
          <span className="pill p-mute">{d.confidentiality}</span>
          {d.legal_hold && <span className="pill p-warn">Legal hold</span>}
        </div>
      </header>

      <div className="cols">
        <section className="panel">
          <h4>Details</h4>
          <dl className="kv">
            {([["Model", <Link to={`/models/${d.model_id}`}>{d.model_id}</Link>], ["Folder", <span className="mono">{d.folder_path ?? "—"}</span>],
              ["Effective date", d.effective_date ?? "—"], ["Source", d.source],
              ["Classification", `${d.classification_source ?? "—"}${d.classification_confidence !== null ? ` (${Math.round(d.classification_confidence * 100)}%)` : ""}`],
              ["Why", d.classification_reason ?? "—"], ["Extraction", `${d.extraction_status} (AI extraction arrives in Phase 5)`],
              ["Retention", `${d.retention_start ?? "—"} → ${d.retention_end ?? "—"}`]] as [string, React.ReactNode][]).map(([k, v]) => (
              <div key={k}><dt>{k}</dt><dd>{v}</dd></div>
            ))}
          </dl>
          {d.links.length > 0 && <p className="note" style={{ marginTop: 10 }}>Linked to: {d.links.map((l) => `${l.entity_type} ${l.entity_id}`).join(", ")}</p>}
        </section>
        <section className="panel">
          <h4>Versions <small>never overwritten</small></h4>
          <div className="tablewrap">
            <table>
              <thead><tr><th>Version</th><th>File</th><th>Uploaded</th><th>By</th><th>Batch</th><th /></tr></thead>
              <tbody>
                {d.versions.map((v) => (
                  <tr key={v.version_id} className={v.version === current.version ? "sel" : "click"} onClick={() => setVersion(v.version)}>
                    <td className="mono">{v.version}</td>
                    <td className="mono">{v.file_name}<div style={{ color: "var(--faint)" }}>{formatBytes(v.size_bytes)} · {v.checksum.slice(0, 12)}…</div></td>
                    <td className="mono">{new Date(v.uploaded_at).toLocaleString()}</td>
                    <td className="mono">{v.uploaded_by ?? "system"}</td>
                    <td className="mono">{v.import_batch_id ? <Link to={`/documents/batches/${v.import_batch_id}`} onClick={(e) => e.stopPropagation()}>{v.import_batch_id}</Link> : "single"}</td>
                    <td><button className="btn sm" onClick={(e) => { e.stopPropagation(); downloadFile(`/api/documents/${d.document_id}/versions/${v.version}/download`, v.file_name).catch((x) => setError(x.message)); }}>Download</button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {current.relative_path && <p className="note" style={{ marginTop: 8 }}>Uploaded from <span className="mono">{current.relative_path}</span>{current.change_reason ? ` — ${current.change_reason}` : ""}</p>}
        </section>
      </div>

      <section className="panel">
        <h4>Preview <small>v{current.version}</small></h4>
        <Preview documentId={d.document_id} version={current.version} mime={current.mime_type} />
      </section>

      {can("policy:edit") && (
        <section className="panel">
          <h4>Retention controls <small>documents are archived, never deleted</small></h4>
          <div className="filters">
            <input className="input" placeholder="Reason (required)" value={reason} onChange={(e) => setReason(e.target.value)} style={{ minWidth: 260 }} />
            <button className="btn" disabled={!reason || act.isPending} onClick={() => { setError(null); act.mutate({ path: "legal-hold", body: { hold: !d.legal_hold, reason } }); }}>
              {d.legal_hold ? "Release legal hold" : "Place legal hold"}
            </button>
            <button className="btn" disabled={!reason || d.status === "Archived" || act.isPending} onClick={() => { setError(null); act.mutate({ path: "archive", body: { reason } }); }}>
              Archive
            </button>
          </div>
        </section>
      )}
      {error && <div className="errline">{error}</div>}

      {can("audit:read") && (
        <section className="panel">
          <h4>Lineage and audit</h4>
          {audit.isLoading ? <Loading /> : (
            <ul className="checklist">
              {(audit.data ?? []).map((e) => (
                <li key={e.event_id}>{new Date(e.occurred_at).toLocaleString()} · <b>{e.action}</b> by {e.user_id ?? "system"} ({e.role})
                  {e.import_batch_id ? ` in batch ${e.import_batch_id}` : ""}{e.reason ? ` — ${e.reason}` : ""}</li>
              ))}
            </ul>
          )}
        </section>
      )}
    </div>
  );
}
