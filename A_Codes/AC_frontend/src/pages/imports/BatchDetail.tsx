import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, downloadFile } from "../../api/client";
import type { AuditEvent, ImportBatchDetail, ImportIssue, ImportTemplate } from "../../api/types";
import { useAuth } from "../../auth/AuthContext";
import { EmptyState, ErrorState, Loading } from "../../components/States";

const RUNNING = ["Validating", "Processing"];
const EDITABLE = ["Uploaded", "Ready", "Validation Failed", "Failed"];
const TONE: Record<string, string> = {
  Completed: "p-good", Ready: "p-info", "Partially Completed": "p-warn", "Validation Failed": "p-bad", Failed: "p-bad",
  Cancelled: "p-mute", Validating: "p-acc", Processing: "p-acc", Uploaded: "p-mute",
  Validated: "p-info", Loaded: "p-good", "Partially loaded": "p-warn", Invalid: "p-bad", Unmapped: "p-warn", "Not loaded": "p-mute",
};

export function BatchStatus({ status }: { status: string }) {
  return <span className={`pill ${TONE[status] ?? "p-mute"}`}>{status}</span>;
}

function Progress({ batch }: { batch: ImportBatchDetail }) {
  const p = batch.progress;
  if (!RUNNING.includes(batch.status)) return null;
  const pct = p?.files_total ? Math.round(((p.files_done ?? 0) / p.files_total) * 100) : 0;
  return (
    <div className="panel">
      <h4>{batch.status === "Validating" ? "Validating (dry run — nothing is saved)" : "Loading"} <small>{pct}%</small></h4>
      <div className="bar"><i style={{ width: `${pct}%` }} /></div>
      <p className="note" style={{ marginTop: 8 }}>
        {p ? `File ${Math.min((p.files_done ?? 0) + 1, p.files_total ?? 1)} of ${p.files_total} · ${p.current_file ?? ""} · row ${p.row ?? 0} of ${p.rows_total ?? "?"}`
          : "Queued…"} You can leave this page; the batch continues in the background.
      </p>
    </div>
  );
}

export function BatchDetail() {
  const { batchId } = useParams();
  const qc = useQueryClient();
  const { can } = useAuth();
  const [fileFilter, setFileFilter] = useState<number | "">("");
  const [error, setError] = useState<string | null>(null);

  const batch = useQuery({
    queryKey: ["import-batch", batchId],
    queryFn: () => api<ImportBatchDetail>(`/api/imports/batches/${batchId}`),
    refetchInterval: (q) => (q.state.data && RUNNING.includes(q.state.data.status) ? 1000 : false),
  });
  const running = !!batch.data && RUNNING.includes(batch.data.status);
  const issues = useQuery({
    queryKey: ["import-issues", batchId, batch.data?.status, fileFilter],
    queryFn: () => api<ImportIssue[]>(`/api/imports/batches/${batchId}/issues?limit=500${fileFilter ? `&file_id=${fileFilter}` : ""}`),
    enabled: !!batch.data && !running,
  });
  const templates = useQuery({ queryKey: ["import-templates"], queryFn: () => api<ImportTemplate[]>("/api/imports/templates") });
  const audit = useQuery({
    queryKey: ["audit", { batch_id: batchId }],
    queryFn: () => api<AuditEvent[]>(`/api/audit?batch_id=${batchId}&limit=200`),
    enabled: can("audit:read") && !!batch.data && !running,
  });

  const refresh = () => {
    qc.invalidateQueries({ queryKey: ["import-batch", batchId] });
    qc.invalidateQueries({ queryKey: ["import-batches"] });
    qc.invalidateQueries({ queryKey: ["models"] });
    qc.invalidateQueries({ queryKey: ["import-templates"] });
  };
  const action = useMutation({
    mutationFn: (what: "validate" | "load" | "cancel") =>
      api<ImportBatchDetail>(`/api/imports/batches/${batchId}/${what}`, { method: "POST" }),
    onSuccess: refresh,
  });
  const remap = useMutation({
    mutationFn: ({ fileId, templateId }: { fileId: number; templateId: string }) =>
      api(`/api/imports/files/${fileId}`, { method: "PATCH", json: { template_id: templateId || null } }),
    onSuccess: refresh,
  });

  if (batch.isLoading) return <Loading />;
  if (batch.isError) return <ErrorState error={batch.error} title={`Batch ${batchId}`} />;
  const b = batch.data!;
  const editable = EDITABLE.includes(b.status) && can("import:run");
  const validRows = b.files.reduce((n, f) => n + f.rows_valid, 0);
  const invalidRows = b.files.reduce((n, f) => n + f.rows_invalid, 0);
  const loaded = ["Completed", "Partially Completed"].includes(b.status) || (b.status === "Failed" && !!b.completed_at);
  const names = Object.fromEntries(b.files.map((f) => [f.import_file_id, f.file_name]));

  return (
    <div className="stack">
      <header>
        <div className="eyebrow"><Link to="/imports">Import Centre</Link> · Batch</div>
        <h1 className="mono" style={{ fontSize: 26 }}>{b.batch_id} <BatchStatus status={b.status} /></h1>
        <p className="lede">
          {b.total_files} file(s) uploaded by {b.uploaded_by ?? "system"} ({b.source}) on {b.created_at ? new Date(b.created_at).toLocaleString() : "—"}.
          Existing records: <b>{String(b.options.on_existing ?? "update")}</b>.
        </p>
      </header>

      <Progress batch={b} />
      {b.error_message && <div className="state error"><b>Processing error</b>{b.error_message}</div>}

      {!running && (
        <div className="panel">
          <h4>{loaded ? "Load result" : "Preview"}</h4>
          <div className="tally">
            <div className="t"><b>{b.files.reduce((n, f) => n + f.rows_total, 0)}</b><span>rows</span></div>
            <div className="t good"><b>{loaded ? b.successful_records : validRows}</b><span>{loaded ? "loaded" : "will be loaded"}</span></div>
            <div className="t bad"><b>{invalidRows}</b><span>{loaded ? "rejected" : "will be rejected"}</span></div>
            <div className="t"><b>{b.files.reduce((n, f) => n + f.rows_new, 0)}</b><span>new</span></div>
            <div className="t"><b>{b.files.reduce((n, f) => n + f.rows_update, 0)}</b><span>updates</span></div>
            <div className="t"><b>{b.files.reduce((n, f) => n + f.rows_unchanged, 0)}</b><span>unchanged / skipped</span></div>
            <div className="t warn"><b>{b.warning_count}</b><span>warnings</span></div>
          </div>
          {b.status === "Ready" && (
            <p className="note" style={{ marginTop: 12 }}>
              <b>{validRows} rows will be loaded; {invalidRows} rows will be rejected.</b> Loading re-checks every row.
            </p>
          )}
          <div className="filters" style={{ marginTop: 12 }}>
            {can("import:run") && b.status === "Ready" && (
              <button className="btn primary" disabled={action.isPending} onClick={() => action.mutate("load")}>Load {validRows} rows</button>
            )}
            {editable && <button className="btn" disabled={action.isPending} onClick={() => action.mutate("validate")}>Validate again</button>}
            {editable && <button className="btn" disabled={action.isPending} onClick={() => action.mutate("cancel")}>Cancel batch</button>}
            <button className="btn" onClick={() => downloadFile(`/api/imports/batches/${b.batch_id}/error-report`, `${b.batch_id}_errors.csv`).catch((e) => setError(e.message))}>
              Download error report
            </button>
          </div>
          {(action.isError || error) && <div className="errline" style={{ marginTop: 8 }}>{error ?? (action.error as Error).message}</div>}
        </div>
      )}

      <section className="panel">
        <h4>Files <small>processed in template load order</small></h4>
        <div className="tablewrap">
          <table>
            <thead><tr><th>File</th><th>Template</th><th>Status</th><th>Rows</th><th>Valid</th><th>Invalid</th><th>New</th><th>Update</th><th>Unchanged</th><th>SHA-256</th></tr></thead>
            <tbody>
              {b.files.map((f) => (
                <tr key={f.import_file_id}>
                  <td className="mono">
                    {f.relative_path}
                    {f.file_error && <div className="field-error">{f.file_error}</div>}
                    {f.duplicate_of_batch && <div style={{ color: "var(--warn)" }}>Identical file already loaded in {f.duplicate_of_batch}</div>}
                  </td>
                  <td>
                    {editable ? (
                      <select className="select" value={f.template_id ?? ""} disabled={remap.isPending}
                              onChange={(e) => remap.mutate({ fileId: f.import_file_id, templateId: e.target.value })}>
                        <option value="">— choose —</option>
                        {(templates.data ?? []).filter((t) => t.available).map((t) => (
                          <option key={t.template_id} value={t.template_id}>{t.template_id} {t.name}</option>
                        ))}
                      </select>
                    ) : <span className="mono">{f.template_id ?? "—"}</span>}
                    {f.template_source && <div style={{ color: "var(--faint)", fontSize: 11 }}>matched by {f.template_source}</div>}
                  </td>
                  <td><BatchStatus status={f.status} /></td>
                  <td className="mono">{f.rows_total}</td>
                  <td className="mono">{f.rows_valid}</td>
                  <td className="mono" style={{ color: f.rows_invalid ? "var(--bad)" : undefined }}>{f.rows_invalid}</td>
                  <td className="mono">{f.rows_new}</td>
                  <td className="mono">{f.rows_update}</td>
                  <td className="mono">{f.rows_unchanged}</td>
                  <td className="mono" title={f.checksum}>{f.checksum.slice(0, 12)}…</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {remap.isError && <div className="errline">{(remap.error as Error).message}</div>}
      </section>

      {!running && (
        <section className="panel">
          <h4>
            Errors and warnings
            <select className="select" value={fileFilter} onChange={(e) => setFileFilter(e.target.value ? Number(e.target.value) : "")}>
              <option value="">All files</option>
              {b.files.map((f) => <option key={f.import_file_id} value={f.import_file_id}>{f.file_name}</option>)}
            </select>
          </h4>
          {issues.isLoading ? <Loading /> : issues.isError ? <ErrorState error={issues.error} />
            : !issues.data!.length ? <EmptyState title="No errors or warnings" /> : (
              <div className="tablewrap scroll">
                <table>
                  <thead><tr><th>File</th><th>Row</th><th>Column</th><th>Type</th><th>Message</th><th>Value</th></tr></thead>
                  <tbody>
                    {issues.data!.map((i) => (
                      <tr key={i.issue_id}>
                        <td className="mono">{names[i.import_file_id]}</td>
                        <td className="mono">{i.row_number ?? "file"}</td>
                        <td className="mono">{i.column_name ?? ""}</td>
                        <td><span className={`pill ${i.severity === "error" ? "p-bad" : "p-warn"}`}>{i.error_type}</span></td>
                        <td>{i.message}</td>
                        <td className="mono">{i.original_value ?? ""}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          {issues.data && issues.data.length >= 500 && <p className="note">Showing the first 500. Download the error report for all of them.</p>}
        </section>
      )}

      {can("audit:read") && loaded && (
        <section className="panel">
          <h4>Changes made by this batch <small>audit events</small></h4>
          {audit.isLoading ? <Loading /> : !audit.data?.length ? <EmptyState title="No changes recorded" /> : (
            <div className="tablewrap scroll">
              <table>
                <thead><tr><th>When</th><th>Action</th><th>Entity</th><th>Record</th><th>Model</th></tr></thead>
                <tbody>
                  {audit.data.map((e) => (
                    <tr key={e.event_id}>
                      <td className="mono">{new Date(e.occurred_at).toLocaleString()}</td>
                      <td>{e.action}</td><td className="mono">{e.entity}</td><td className="mono">{e.entity_id}</td>
                      <td className="mono">{e.model_id ? <Link to={`/models/${e.model_id}`}>{e.model_id}</Link> : ""}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      )}
    </div>
  );
}
