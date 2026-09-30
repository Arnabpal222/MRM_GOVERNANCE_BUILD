import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Fragment, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, downloadFile } from "../../api/client";
import type { ImportBatch, ImportBatchDetail, ImportTemplate } from "../../api/types";
import { useAuth } from "../../auth/AuthContext";
import { EmptyState, ErrorState, Loading, PageHeader } from "../../components/States";
import { BatchStatus } from "./BatchDetail";

const TABS = ["Upload", "Templates", "History"] as const;
type Tab = (typeof TABS)[number];

function Upload() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const fileInput = useRef<HTMLInputElement>(null);
  const folderInput = useRef<HTMLInputElement>(null);
  const [files, setFiles] = useState<File[]>([]);
  const [onExisting, setOnExisting] = useState("update");

  const upload = useMutation({
    mutationFn: () => {
      const form = new FormData();
      for (const f of files) {
        form.append("files", f);
        form.append("paths", (f as File & { webkitRelativePath?: string }).webkitRelativePath || f.name);
      }
      form.append("on_existing", onExisting);
      return api<ImportBatchDetail>("/api/imports/batches", { method: "POST", body: form });
    },
    onSuccess: (b) => {
      qc.invalidateQueries({ queryKey: ["import-batches"] });
      navigate(`/imports/${b.batch_id}`);
    },
  });

  const add = (list: FileList | null) => {
    if (!list) return;
    const picked = Array.from(list).filter((f) => /\.(xlsx|csv)$/i.test(f.name));
    setFiles((prev) => [...prev, ...picked.filter((p) => !prev.some((x) => x.name === p.name && x.size === p.size))]);
  };

  return (
    <section className="panel stack">
      <h4>Upload files <small>Excel (.xlsx) or CSV — one or many files per batch</small></h4>
      <div
        className="dropzone"
        onDragOver={(e) => e.preventDefault()}
        onDrop={(e) => { e.preventDefault(); add(e.dataTransfer.files); }}
      >
        <p>Drop files here, or</p>
        <div className="filters" style={{ justifyContent: "center" }}>
          <button className="btn" type="button" onClick={() => fileInput.current?.click()}>Choose files</button>
          <button className="btn" type="button" onClick={() => folderInput.current?.click()}>Choose folder</button>
        </div>
        <input ref={fileInput} type="file" multiple accept=".xlsx,.csv" hidden onChange={(e) => { add(e.target.files); e.target.value = ""; }} />
        <input ref={folderInput} type="file" hidden
               {...({ webkitdirectory: "", directory: "" } as Record<string, string>)}
               onChange={(e) => { add(e.target.files); e.target.value = ""; }} />
        <p className="note" style={{ margin: "8px auto 0" }}>
          Files are matched to a template by the T-number in the name (e.g. T02_models.xlsx) or by their columns.
          Nothing is saved until you review the preview and choose Load.
        </p>
      </div>

      {files.length > 0 && (
        <div className="tablewrap">
          <table>
            <thead><tr><th>File</th><th>Size</th><th /></tr></thead>
            <tbody>
              {files.map((f, i) => (
                <tr key={`${f.name}-${i}`}>
                  <td className="mono">{(f as File & { webkitRelativePath?: string }).webkitRelativePath || f.name}</td>
                  <td className="mono">{(f.size / 1024).toFixed(1)} KB</td>
                  <td><button className="btn sm" onClick={() => setFiles(files.filter((_, j) => j !== i))}>Remove</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="filters">
        <label className="field" style={{ flexDirection: "row", alignItems: "center", gap: 8 }}>
          Existing records
          <select className="select" value={onExisting} onChange={(e) => setOnExisting(e.target.value)}>
            <option value="update">Update them</option>
            <option value="skip">Skip them</option>
            <option value="reject">Reject them as errors</option>
          </select>
        </label>
        <span style={{ flex: 1 }} />
        <button className="btn" disabled={!files.length} onClick={() => setFiles([])}>Clear</button>
        <button className="btn primary" disabled={!files.length || upload.isPending} onClick={() => upload.mutate()}>
          {upload.isPending ? "Uploading…" : `Upload and validate ${files.length || ""} file${files.length === 1 ? "" : "s"}`}
        </button>
      </div>
      {upload.isError && <div className="errline">{(upload.error as Error).message}</div>}
    </section>
  );
}

function Templates() {
  const templates = useQuery({ queryKey: ["import-templates"], queryFn: () => api<ImportTemplate[]>("/api/imports/templates") });
  const [open, setOpen] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  if (templates.isLoading) return <Loading />;
  if (templates.isError) return <ErrorState error={templates.error} />;
  const get = (id: string, fmt: string) =>
    downloadFile(`/api/imports/templates/${id}/blank?format=${fmt}`, `${id}_template.${fmt}`).catch((e) => setError(e.message));

  return (
    <section className="stack">
      <p className="note">Templates load in this order; each depends on records created by the ones before it.
        Blank downloads include an instructions sheet with allowed values from the current policy settings.</p>
      {error && <div className="errline">{error}</div>}
      <div className="tablewrap">
        <table>
          <thead><tr><th>#</th><th>Template</th><th>Loads into</th><th>Format</th><th>Records</th><th>Prerequisites</th><th>Download</th></tr></thead>
          <tbody>
            {templates.data!.map((t) => (
              <Fragment key={t.template_id}>
                <tr className={t.available ? "click" : ""} onClick={() => t.available && setOpen(open === t.template_id ? null : t.template_id)}
                    style={t.available ? undefined : { opacity: 0.55 }}>
                  <td className="mono">{t.order}</td>
                  <td><span className="mono">{t.template_id}</span> {t.name}</td>
                  <td className="mono">{t.target}</td>
                  <td className="mono">{t.format}</td>
                  <td className="mono">{t.record_count ?? "—"}</td>
                  <td>
                    {t.channel === "documents" ? <span className="pill p-acc" title="Include in a Document Centre upload">Document Centre manifest</span>
                      : !t.available ? <span className="pill p-mute">{t.phase}</span>
                      : t.prerequisites_met ? <span className="pill p-good">Ready</span>
                        : <span className="pill p-warn" title="Load these templates first">Needs {t.missing_prerequisites.join(", ")}</span>}
                  </td>
                  <td onClick={(e) => e.stopPropagation()}>
                    {t.available && <span className="filters">
                      <button className="btn sm" onClick={() => get(t.template_id, "xlsx")}>xlsx</button>
                      <button className="btn sm" onClick={() => get(t.template_id, "csv")}>csv</button>
                    </span>}
                  </td>
                </tr>
                {open === t.template_id && (
                  <tr>
                    <td colSpan={7} style={{ background: "var(--sunk)" }}>
                      <table>
                        <thead><tr><th>Column</th><th>Type</th><th>Required</th><th>Allowed values / rule</th><th>Example</th></tr></thead>
                        <tbody>
                          {t.columns.map((c) => (
                            <tr key={c.name}>
                              <td className="mono">{c.name}</td><td className="mono">{c.type}</td>
                              <td>{c.required ? "Yes" : c.condition ? "Conditional" : "No"}</td>
                              <td>{[c.allowed?.join(", "), c.condition, c.reference && `must exist in ${c.reference}`, c.description].filter(Boolean).join(" · ")}</td>
                              <td className="mono">{c.example}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </td>
                  </tr>
                )}
              </Fragment>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function History() {
  const batches = useQuery({ queryKey: ["import-batches"], queryFn: () => api<ImportBatch[]>("/api/imports/batches") });
  if (batches.isLoading) return <Loading />;
  if (batches.isError) return <ErrorState error={batches.error} />;
  if (!batches.data!.length) return <EmptyState title="No imports yet">Upload a file to create the first batch.</EmptyState>;
  return (
    <div className="tablewrap">
      <table>
        <thead><tr><th>Batch</th><th>Date</th><th>User</th><th>Source</th><th>Files</th><th>Records</th><th>Loaded</th><th>Rejected</th><th>Warnings</th><th>Status</th></tr></thead>
        <tbody>
          {batches.data!.map((b) => (
            <tr key={b.batch_id}>
              <td className="mono"><Link to={`/imports/${b.batch_id}`}>{b.batch_id}</Link></td>
              <td className="mono">{b.created_at ? new Date(b.created_at).toLocaleString() : "—"}</td>
              <td className="mono">{b.uploaded_by ?? "system"}</td>
              <td>{b.source}</td>
              <td className="mono">{b.total_files}</td>
              <td className="mono">{b.total_records}</td>
              <td className="mono">{b.successful_records}</td>
              <td className="mono">{b.failed_records}</td>
              <td className="mono">{b.warning_count}</td>
              <td><BatchStatus status={b.status} /></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function ImportCentre() {
  const { can } = useAuth();
  const canImport = can("import:run");
  const tabs = TABS.filter((t) => canImport || t === "Templates");
  const [tab, setTab] = useState<Tab>(canImport ? "Upload" : "Templates");
  return (
    <div className="stack">
      <PageHeader eyebrow="Evidence & data" title="Import Centre"
                  lede="Load governance data from Excel and CSV templates. Every file is validated row by row; you see a preview and choose Load. Valid rows load, invalid rows are rejected with a downloadable error report." />
      <nav className="tabs" role="tablist">
        {tabs.map((t) => (
          <button key={t} role="tab" aria-selected={tab === t} className={tab === t ? "on" : ""} onClick={() => setTab(t)}>{t}</button>
        ))}
      </nav>
      {tab === "Upload" && <Upload />}
      {tab === "Templates" && <Templates />}
      {tab === "History" && <History />}
    </div>
  );
}
