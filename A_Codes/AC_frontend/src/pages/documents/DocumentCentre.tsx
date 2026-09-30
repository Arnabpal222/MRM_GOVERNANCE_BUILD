import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../../api/client";
import type { Completeness, DocumentBatch, DocumentFolder, DocumentSummary, ImportBatch } from "../../api/types";
import { useAuth } from "../../auth/AuthContext";
import { EmptyState, ErrorState, Loading, PageHeader } from "../../components/States";
import { BatchStatus } from "../imports/BatchDetail";
import { SingleUploadForm, formatBytes, useDocumentMeta } from "./shared";

const TABS = ["Register", "Upload", "Batches", "Completeness"] as const;
type Tab = (typeof TABS)[number];

function FolderTree({ folders, selected, onSelect }: { folders: DocumentFolder[]; selected: number | null; onSelect: (id: number | null) => void }) {
  const [open, setOpen] = useState<Set<number>>(new Set());
  const children = useMemo(() => {
    const map = new Map<number | null, DocumentFolder[]>();
    for (const f of folders) map.set(f.parent_folder_id, [...(map.get(f.parent_folder_id) ?? []), f]);
    return map;
  }, [folders]);
  const render = (parent: number | null, depth: number): React.ReactNode =>
    (children.get(parent) ?? []).map((f) => {
      const kids = children.get(f.folder_id)?.length ?? 0;
      const isOpen = open.has(f.folder_id);
      return (
        <div key={f.folder_id}>
          <div className={`tree-row${selected === f.folder_id ? " on" : ""}`} style={{ paddingLeft: 6 + depth * 14 }}>
            <button className="tree-toggle" disabled={!kids} aria-label={isOpen ? "Collapse" : "Expand"}
                    onClick={() => { const n = new Set(open); if (isOpen) n.delete(f.folder_id); else n.add(f.folder_id); setOpen(n); }}>
              {kids ? (isOpen ? "▾" : "▸") : "·"}
            </button>
            <button className="tree-name" onClick={() => onSelect(f.folder_id)}>
              {f.folder_name}{f.model_id && <span className="pill p-acc" style={{ marginLeft: 6 }}>{f.model_id}</span>}
              {f.document_count > 0 && <span className="tree-count">{f.document_count}</span>}
            </button>
          </div>
          {isOpen && render(f.folder_id, depth + 1)}
        </div>
      );
    });
  return (
    <nav className="panel tree" aria-label="Folders">
      <h4>Folders</h4>
      <div className={`tree-row${selected === null ? " on" : ""}`}><button className="tree-name" onClick={() => onSelect(null)}>All documents</button></div>
      {folders.length === 0 ? <p className="note">Folders appear when a folder or ZIP is uploaded.</p> : render(null, 0)}
    </nav>
  );
}

function Register() {
  const meta = useDocumentMeta();
  const navigate = useNavigate();
  const [folder, setFolder] = useState<number | null>(null);
  const [filters, setFilters] = useState({ search: "", document_type: "", model_id: "" });
  const [applied, setApplied] = useState(filters);
  const folders = useQuery({ queryKey: ["document-folders"], queryFn: () => api<DocumentFolder[]>("/api/documents/folders") });
  const params = new URLSearchParams(Object.entries({ ...applied, folder_id: folder ? String(folder) : "" }).filter(([, v]) => v));
  const docs = useQuery({ queryKey: ["documents", params.toString()], queryFn: () => api<DocumentSummary[]>(`/api/documents?${params}`) });

  return (
    <div className="doc-layout">
      {folders.isLoading ? <Loading /> : folders.isError ? <ErrorState error={folders.error} /> :
        <FolderTree folders={folders.data!} selected={folder} onSelect={setFolder} />}
      <div className="stack">
        <form className="filters" onSubmit={(e) => { e.preventDefault(); setApplied(filters); }}>
          <input className="input" placeholder="Search title, file name, ID" value={filters.search}
                 onChange={(e) => setFilters({ ...filters, search: e.target.value })} />
          <input className="input" placeholder="Model (M-0012)" value={filters.model_id} style={{ width: 130 }}
                 onChange={(e) => setFilters({ ...filters, model_id: e.target.value.trim() })} />
          <select className="select" value={filters.document_type} onChange={(e) => setFilters({ ...filters, document_type: e.target.value })}>
            <option value="">Type: all</option>
            {(meta.data?.document_types ?? []).map((t) => <option key={t}>{t}</option>)}
          </select>
          <button className="btn primary" type="submit">Search</button>
          <button className="btn" type="button" onClick={() => { const e = { search: "", document_type: "", model_id: "" }; setFilters(e); setApplied(e); setFolder(null); }}>Clear</button>
        </form>
        {docs.isLoading ? <Loading /> : docs.isError ? <ErrorState error={docs.error} /> : docs.data!.length === 0 ?
          <EmptyState title="No documents match">Upload documents, or clear the filters.</EmptyState> : (
          <div className="tablewrap">
            <table>
              <thead><tr><th>Document</th><th>Title</th><th>Model</th><th>Type</th><th>Version</th><th>File</th><th>Folder</th><th>Uploaded</th></tr></thead>
              <tbody>
                {docs.data!.map((d) => (
                  <tr key={d.document_id} className="click" onClick={() => navigate(`/documents/${d.document_id}`)}>
                    <td className="mono">{d.document_id}</td>
                    <td>{d.title}{d.legal_hold && <span className="pill p-warn" style={{ marginLeft: 6 }}>Legal hold</span>}</td>
                    <td className="mono"><Link to={`/models/${d.model_id}`} onClick={(e) => e.stopPropagation()}>{d.model_id}</Link></td>
                    <td>{d.document_type}</td>
                    <td className="mono">{d.current_version}</td>
                    <td className="mono">{d.file_name} <span style={{ color: "var(--faint)" }}>{formatBytes(d.size_bytes)}</span></td>
                    <td className="mono" style={{ color: "var(--muted)" }}>{d.folder_path ?? "—"}</td>
                    <td className="mono">{new Date(d.uploaded_at).toLocaleDateString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {docs.data && docs.data.length >= 500 && <p className="note">Showing the 500 most recent. Narrow the search.</p>}
      </div>
    </div>
  );
}

function BatchUpload() {
  const meta = useDocumentMeta();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const files = useRef<HTMLInputElement>(null);
  const folder = useRef<HTMLInputElement>(null);
  const [picked, setPicked] = useState<{ file: File; path: string }[]>([]);
  const [source, setSource] = useState<"batch" | "folder">("batch");
  const upload = useMutation({
    mutationFn: () => {
      const fd = new FormData();
      for (const p of picked) { fd.append("files", p.file); fd.append("paths", p.path); }
      fd.append("source", source);
      return api<DocumentBatch>("/api/documents/batches", { method: "POST", body: fd });
    },
    onSuccess: (b) => { qc.invalidateQueries({ queryKey: ["document-batches"] }); navigate(`/documents/batches/${b.batch_id}`); },
  });
  const add = (list: FileList | null, kind: "batch" | "folder") => {
    if (!list) return;
    setSource(kind);
    setPicked((prev) => [...prev, ...Array.from(list).map((f) => ({ file: f, path: (f as File & { webkitRelativePath?: string }).webkitRelativePath || f.name }))
      .filter((p) => !prev.some((x) => x.path === p.path))]);
  };
  const m = meta.data;
  return (
    <section className="panel stack">
      <h4>Upload many files, a folder or a ZIP package <small>{m ? `up to ${m.max_files} files · ZIP up to ${m.max_zip_mb} MB` : ""}</small></h4>
      <div className="dropzone" onDragOver={(e) => e.preventDefault()} onDrop={(e) => { e.preventDefault(); add(e.dataTransfer.files, "batch"); }}>
        <p>Drop files or a .zip here, or</p>
        <div className="filters" style={{ justifyContent: "center" }}>
          <button className="btn" type="button" onClick={() => files.current?.click()}>Choose files / ZIP</button>
          <button className="btn" type="button" onClick={() => folder.current?.click()}>Choose folder</button>
        </div>
        <input ref={files} type="file" multiple hidden onChange={(e) => { add(e.target.files, "batch"); e.target.value = ""; }} />
        <input ref={folder} type="file" hidden {...({ webkitdirectory: "", directory: "" } as Record<string, string>)}
               onChange={(e) => { add(e.target.files, "folder"); e.target.value = ""; }} />
        <p className="note" style={{ margin: "8px auto 0" }}>
          Folder paths are kept. Models are recognised from folder or file names such as <span className="mono">M-0012/Validation/</span>,
          types from names such as <span className="mono">TOR</span>, <span className="mono">MDD</span>, <span className="mono">Validation_Report</span>.
          Include a <span className="mono">manifest.xlsx</span> (T17) to set model, type and version explicitly. You review the mapping before anything is stored.
        </p>
      </div>
      {picked.length > 0 && (
        <div className="tablewrap scroll">
          <table>
            <thead><tr><th>Path</th><th>Size</th><th /></tr></thead>
            <tbody>
              {picked.map((p) => (
                <tr key={p.path}>
                  <td className="mono">{p.path}</td><td className="mono">{formatBytes(p.file.size)}</td>
                  <td><button className="btn sm" onClick={() => setPicked(picked.filter((x) => x.path !== p.path))}>Remove</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <div className="filters">
        <span className="note">{picked.length} file(s)</span>
        <span style={{ flex: 1 }} />
        <button className="btn" disabled={!picked.length} onClick={() => setPicked([])}>Clear</button>
        <button className="btn primary" disabled={!picked.length || upload.isPending} onClick={() => upload.mutate()}>
          {upload.isPending ? "Uploading…" : "Upload and analyse"}
        </button>
      </div>
      {upload.isError && <div className="errline">{(upload.error as Error).message}</div>}
    </section>
  );
}

function Batches() {
  const q = useQuery({ queryKey: ["document-batches"], queryFn: () => api<ImportBatch[]>("/api/documents/batches") });
  if (q.isLoading) return <Loading />;
  if (q.isError) return <ErrorState error={q.error} />;
  if (!q.data!.length) return <EmptyState title="No document batches yet" />;
  return (
    <div className="tablewrap">
      <table>
        <thead><tr><th>Batch</th><th>Date</th><th>User</th><th>Source</th><th>Files</th><th>Stored</th><th>Rejected</th><th>Status</th></tr></thead>
        <tbody>
          {q.data!.map((b) => (
            <tr key={b.batch_id}>
              <td className="mono"><Link to={`/documents/batches/${b.batch_id}`}>{b.batch_id}</Link></td>
              <td className="mono">{b.created_at ? new Date(b.created_at).toLocaleString() : "—"}</td>
              <td className="mono">{b.uploaded_by ?? "system"}</td>
              <td>{b.source}</td>
              <td className="mono">{b.total_files}</td>
              <td className="mono">{b.successful_records}</td>
              <td className="mono">{b.failed_records}</td>
              <td><BatchStatus status={b.status} /></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function CompletenessTab() {
  const q = useQuery({ queryKey: ["completeness", "gaps"], queryFn: () => api<Completeness[]>("/api/documents/completeness?missing_only=true") });
  if (q.isLoading) return <Loading />;
  if (q.isError) return <ErrorState error={q.error} />;
  if (!q.data!.length) return <EmptyState title="Every model has its required documents" />;
  return (
    <section className="stack">
      <p className="note">{q.data!.length} models are missing required documents for their lifecycle phase (policy: Admin → required_docs_*).</p>
      <div className="tablewrap">
        <table>
          <thead><tr><th>Model</th><th>Name</th><th>Phase</th><th>Complete</th><th>Missing</th></tr></thead>
          <tbody>
            {q.data!.map((c) => (
              <tr key={c.model_id}>
                <td className="mono"><Link to={`/models/${c.model_id}`}>{c.model_id}</Link></td>
                <td>{c.model_name}</td><td>{c.lifecycle_phase}</td>
                <td className="mono">{c.score}%</td>
                <td>{c.missing.map((m) => <span key={m} className="pill p-bad" style={{ marginRight: 4 }}>{m}</span>)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

export function DocumentCentre() {
  const { can } = useAuth();
  const navigate = useNavigate();
  const tabs = TABS.filter((t) => t !== "Upload" || can("document:upload"));
  const [tab, setTab] = useState<Tab>("Register");
  return (
    <div className="stack">
      <PageHeader eyebrow="Evidence & data" title="Document Centre"
                  lede="Governance evidence for every model: upload one file, many files, a folder or a ZIP package. Folder structure and versions are kept, duplicates are detected by SHA-256, and completeness is checked against the required-document policy." />
      <nav className="tabs" role="tablist">
        {tabs.map((t) => <button key={t} role="tab" aria-selected={tab === t} className={tab === t ? "on" : ""} onClick={() => setTab(t)}>{t}</button>)}
      </nav>
      {tab === "Register" && <Register />}
      {tab === "Upload" && (
        <div className="stack">
          <SingleUploadForm onDone={(d) => navigate(`/documents/${d.document_id}`)} />
          <BatchUpload />
        </div>
      )}
      {tab === "Batches" && <Batches />}
      {tab === "Completeness" && <CompletenessTab />}
    </div>
  );
}
