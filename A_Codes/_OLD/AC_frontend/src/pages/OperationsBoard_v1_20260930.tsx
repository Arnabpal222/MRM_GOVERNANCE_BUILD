import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { api } from "../api/client";
import { useModelMeta } from "../api/queries";
import type { ModelSummary } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { DaysToDue, Pill, ScoreValue } from "../components/Pills";
import { EmptyState, ErrorState, Loading, PageHeader } from "../components/States";

const FILTER_KEYS = ["model_type", "tier", "phase", "business_line", "column", "revalidation_status", "search"] as const;

type SortKey = "model_id" | "model_name" | "effective_tier" | "column" | "days" | "findings" | "score";

const COLUMNS: { key: SortKey; label: string; value: (m: ModelSummary) => string | number }[] = [
  { key: "model_id", label: "Model", value: (m) => m.model_id },
  { key: "model_name", label: "Name", value: (m) => m.model_name },
  { key: "effective_tier", label: "Tier", value: (m) => m.effective_tier },
  { key: "column", label: "Stage", value: (m) => m.state.displayed_column },
  { key: "days", label: "Revalidation", value: (m) => m.state.days_to_due ?? Number.MAX_SAFE_INTEGER },
  { key: "findings", label: "Open findings", value: (m) => m.state.open_findings },
  { key: "score", label: "Score", value: (m) => (m.state.score === null ? -1 : Number(m.state.score)) },
];

function toCsv(rows: ModelSummary[]): string {
  const header = ["model_id", "model_name", "model_type", "model_subtype", "business_line", "tier", "lifecycle_phase",
    "stage", "next_due", "days_to_due", "revalidation_status", "open_findings", "overdue_findings", "score"];
  const esc = (v: unknown) => {
    const s = v === null || v === undefined ? "" : String(v);
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  const lines = rows.map((m) => [m.model_id, m.model_name, m.model_type, m.model_subtype, m.business_line,
    m.effective_tier, m.lifecycle_phase, m.state.displayed_column, m.state.next_due, m.state.days_to_due,
    m.state.revalidation_status, m.state.open_findings, m.state.overdue_findings, m.state.score].map(esc).join(","));
  return [header.join(","), ...lines].join("\n");
}

function download(filename: string, text: string) {
  const url = URL.createObjectURL(new Blob([text], { type: "text/csv" }));
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export function OperationsBoard() {
  const navigate = useNavigate();
  const { can } = useAuth();
  const meta = useModelMeta();
  const [params, setParams] = useSearchParams();
  const [sort, setSort] = useState<{ key: SortKey; asc: boolean }>({ key: "model_id", asc: true });
  const [searchDraft, setSearchDraft] = useState(params.get("search") ?? "");

  // Filters live in the URL so Command Center tiles can deep-link here later.
  const filters = Object.fromEntries(FILTER_KEYS.map((k) => [k, params.get(k) ?? ""]));
  const query = new URLSearchParams(Object.entries(filters).filter(([, v]) => v));
  const models = useQuery({
    queryKey: ["models", query.toString()],
    queryFn: () => api<ModelSummary[]>(`/api/models?${query}`),
  });

  const sorted = useMemo(() => {
    const col = COLUMNS.find((c) => c.key === sort.key)!;
    return [...(models.data ?? [])].sort((a, b) => {
      const va = col.value(a), vb = col.value(b);
      const cmp = typeof va === "number" && typeof vb === "number" ? va - vb : String(va).localeCompare(String(vb));
      return sort.asc ? cmp : -cmp;
    });
  }, [models.data, sort]);

  const stageCounts = useMemo(() => {
    const counts = new Map<string, number>();
    for (const m of models.data ?? []) counts.set(m.state.displayed_column, (counts.get(m.state.displayed_column) ?? 0) + 1);
    return counts;
  }, [models.data]);

  function setFilter(key: string, value: string) {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value);
    else next.delete(key);
    setParams(next, { replace: true });
  }

  const select = (key: string, label: string, options: string[] | undefined) => (
    <select className="select" aria-label={label} value={filters[key]} onChange={(e) => setFilter(key, e.target.value)}>
      <option value="">{label}: all</option>
      {(options ?? []).map((o) => <option key={o} value={o}>{o}</option>)}
    </select>
  );

  return (
    <div className="stack">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end", gap: 16, flexWrap: "wrap" }}>
        <PageHeader eyebrow="Portfolio" title="Operations Board"
                    lede="Model inventory by governance stage. Revalidation is a work state derived from the due date, not a stored phase." />
        {can("model:edit") && <button className="btn primary" onClick={() => navigate("/models/new")}>Register model</button>}
      </div>

      <div className="filters">
        {select("model_type", "Type", meta.data?.model_types)}
        {select("tier", "Tier", meta.data?.tiers)}
        {select("phase", "Phase", meta.data?.lifecycle_phases)}
        {select("column", "Stage", meta.data?.displayed_columns)}
        {select("revalidation_status", "Revalidation", meta.data?.revalidation_statuses)}
        {select("business_line", "Business line", meta.data?.business_lines)}
        <form onSubmit={(e) => { e.preventDefault(); setFilter("search", searchDraft.trim()); }}>
          <input className="input" placeholder="Search ID, name, subtype" value={searchDraft}
                 onChange={(e) => setSearchDraft(e.target.value)} aria-label="Search models" />
        </form>
        <button className="btn" onClick={() => { setSearchDraft(""); setParams({}, { replace: true }); }}>Clear</button>
        <span style={{ flex: 1 }} />
        <button className="btn" disabled={!sorted.length}
                onClick={() => download("model_inventory.csv", toCsv(sorted))}>Export CSV</button>
      </div>

      {meta.data && (
        <div className="pipeline" role="list" aria-label="Models by stage">
          {meta.data.displayed_columns.map((col) => (
            <button key={col} role="listitem" className={`stage-node${filters.column === col ? " on" : ""}`}
                    onClick={() => setFilter("column", filters.column === col ? "" : col)}>
              <span className="l">{col}</span>
              <span className="v mono">{stageCounts.get(col) ?? 0}</span>
            </button>
          ))}
        </div>
      )}

      {models.isLoading && <Loading />}
      {models.isError && <ErrorState error={models.error} />}
      {models.data && models.data.length === 0 && (
        <EmptyState title="No models match these filters">Clear a filter, or register a model.</EmptyState>
      )}
      {sorted.length > 0 && (
        <div className="tablewrap">
          <table>
            <thead>
              <tr>
                {COLUMNS.map((c) => (
                  <th key={c.key} aria-sort={sort.key === c.key ? (sort.asc ? "ascending" : "descending") : "none"}>
                    <button className="th-sort" onClick={() => setSort({ key: c.key, asc: sort.key === c.key ? !sort.asc : true })}>
                      {c.label}{sort.key === c.key ? (sort.asc ? " ▲" : " ▼") : ""}
                    </button>
                  </th>
                ))}
                <th>Type</th><th>Business line</th>
              </tr>
            </thead>
            <tbody>
              {sorted.map((m) => (
                <tr key={m.model_id} className="click" onClick={() => navigate(`/models/${m.model_id}`)}>
                  <td className="mono">{m.model_id}</td>
                  <td>
                    {m.model_name}
                    {m.state.sod_breach && <span className="pill p-bad" style={{ marginLeft: 6 }} title={m.state.sod_breach}>SoD</span>}
                  </td>
                  <td><Pill value={m.effective_tier} /></td>
                  <td>{m.state.displayed_column}</td>
                  <td>
                    <DaysToDue days={m.state.days_to_due} />{" "}
                    {m.state.revalidation_status && <Pill value={m.state.revalidation_status} />}
                  </td>
                  <td className="mono">
                    {m.state.open_findings}
                    {m.state.overdue_findings > 0 && <span style={{ color: "var(--bad)" }}> ({m.state.overdue_findings} overdue)</span>}
                  </td>
                  <td><ScoreValue value={m.state.score} /></td>
                  <td>{m.model_type} · {m.model_subtype}</td>
                  <td>{m.business_line}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {models.data && <p className="note">{sorted.length} models shown.</p>}
    </div>
  );
}
