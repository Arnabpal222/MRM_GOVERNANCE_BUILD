import { useQuery } from "@tanstack/react-query";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { DaysToDue, Pill } from "../components/Pills";
import { EmptyState, ErrorState, Loading, PageHeader } from "../components/States";

interface DistItem { key: string; count: number; pct: number }
interface Insight { severity: string; rule: string; message: string; model_id: string | null; source: string; link: string }
interface Summary {
  as_of: string;
  calculated_at: string;
  tiles: Record<string, number | null>;
  distributions: Record<string, DistItem[]>;
  revalidation_timeline: { model_id: string; model_name: string; tier: string; next_due: string | null; days_to_due: number | null; status: string | null; latest_decision: string | null }[];
  insights: Insight[];
  insight_count: number;
  pending: Record<string, string>;
}

// Presentation only: which reserved status tone a category wears. Identity is always also in the label.
const STATUS_TONE: Record<string, string> = {
  High: "bad", Medium: "warn", Low: "good", Critical: "bad",
  Overdue: "bad", "Due Soon": "warn", Scheduled: "info",
  below_60: "bad", "60_80": "warn", "80_plus": "good",
};
const BAND_LABEL: Record<string, string> = { below_60: "Below 60", "60_80": "60 – 80", "80_plus": "80 and above" };
const BAND_FLAG: Record<string, string> = { below_60: "scored_below_60", "60_80": "scored_60_80", "80_plus": "scored_80_plus" };

function Tile({ label, value, sub, to, tone }: { label: string; value: React.ReactNode; sub?: React.ReactNode; to?: string; tone?: string }) {
  const navigate = useNavigate();
  const body = (
    <>
      <span className="tile-label">{label}</span>
      <b className={tone ? `tone-${tone}` : undefined}>{value}</b>
      {sub && <span className="tile-sub">{sub}</span>}
    </>
  );
  if (!to) return <div className="tile">{body}</div>;
  // A div rather than a <button>: the sub-line may contain its own link, and links cannot sit inside buttons.
  return (
    <div className="tile click" role="link" tabIndex={0} title="Open the matching models" onClick={() => navigate(to)}
         onKeyDown={(e) => { if (e.key === "Enter") navigate(to); }}>
      {body}
    </div>
  );
}

/** Horizontal bar list: one thin bar per category, value labelled directly, click to drill down. */
function BarList({ title, items, label = (k) => k, toneFor, linkFor, note }: {
  title: string; items: DistItem[]; label?: (k: string) => string; toneFor?: (k: string) => string | undefined;
  linkFor?: (k: string) => string | null; note?: string;
}) {
  const navigate = useNavigate();
  const max = Math.max(1, ...items.map((i) => i.count));
  return (
    <section className="panel">
      <h4>{title}{note && <small>{note}</small>}</h4>
      {items.length === 0 ? <p className="note">No data.</p> : (
        <ul className="barlist">
          {items.map((i) => {
            const to = linkFor?.(i.key) ?? null;
            const tone = toneFor?.(i.key);
            return (
              <li key={i.key}>
                <button className="barrow" disabled={!to} onClick={() => to && navigate(to)}
                        title={`${label(i.key)}: ${i.count} (${i.pct}%)${to ? " — click to list them" : ""}`}>
                  <span className="bar-label">{label(i.key)}</span>
                  <span className="bar-track"><i className={tone ? `fill-${tone}` : "fill-accent"} style={{ width: `${(i.count / max) * 100}%` }} /></span>
                  <span className="bar-value mono">{i.count}<span className="bar-pct"> · {i.pct}%</span></span>
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}

const q = (params: Record<string, string>) => `/operations?${new URLSearchParams(params)}`;

export function CommandCenter() {
  const { can } = useAuth();
  const s = useQuery({ queryKey: ["dashboard"], queryFn: () => api<Summary>("/api/dashboard/summary") });
  if (s.isLoading) return <Loading label="Calculating the portfolio…" />;
  if (s.isError) return <ErrorState error={s.error} title="Command Center" />;
  const d = s.data!;
  const t = d.tiles;
  if (!t.total_models) {
    return (
      <div className="stack">
        <PageHeader eyebrow="Portfolio" title="Command Center" />
        <EmptyState title="No models loaded yet">
          {can("import:run") ? <>Load the inventory in the <Link to="/imports">Import Centre</Link>, or use Admin → Reset to seed.</> : "Ask an Admin to load the model inventory."}
        </EmptyState>
      </div>
    );
  }
  const dist = d.distributions;

  return (
    <div className="stack">
      <PageHeader eyebrow="Portfolio" title="Command Center"
                  lede={`Model risk across the portfolio as of ${new Date(d.as_of).toLocaleDateString()}. Every figure is calculated from the governance records and opens the matching models.`} />

      <div className="tiles">
        <Tile label="Total models" value={t.total_models} sub={`${t.active_models} active`} to="/operations" />
        <Tile label="In production" value={t.in_production}
              sub={`${Math.round((100 * (t.in_production ?? 0)) / (t.total_models ?? 1))}% of the inventory`} to={q({ flag: "in_production" })} />
        <Tile label="High risk" value={t.high_tier} tone="bad" sub="effective tier High" to={q({ tier: "High" })} />
        <Tile label="Revalidation queue" value={t.revalidation_queue}
              sub={<Link to={q({ revalidation_status: "Overdue" })} onClick={(e) => e.stopPropagation()}>{t.revalidation_overdue} overdue</Link>}
              to={q({ column: "Revalidation" })} />
        <Tile label="Open findings" value={t.open_findings}
              sub={<Link to={q({ flag: "overdue_findings" })} onClick={(e) => e.stopPropagation()}>{t.overdue_findings} overdue · {t.critical_overdue_findings} Critical</Link>}
              to={q({ flag: "open_findings" })} />
        <Tile label="Document completeness" value={`${t.document_completeness_pct}%`}
              sub={`${t.models_with_document_gaps} models with gaps`} to={q({ flag: "doc_gaps" })} />
        <Tile label="Open MRC conditions" value={t.models_with_open_conditions} sub="models" to={q({ flag: "open_conditions" })} />
        <Tile label="Portfolio score" value={t.portfolio_score ?? "n/a"} sub={`average of ${t.scored_models} scored models`} />
      </div>

      <div className="cols">
        <BarList title="Risk tier" items={dist.tier} toneFor={(k) => STATUS_TONE[k]} linkFor={(k) => q({ tier: k })} />
        <BarList title="Model type" items={dist.model_type} linkFor={(k) => q({ model_type: k })} />
        <BarList title="Lifecycle stage" items={dist.stage} note="Revalidation is derived from due dates" linkFor={(k) => q({ column: k })} />
        <BarList title="Revalidation status" items={dist.revalidation_status} toneFor={(k) => STATUS_TONE[k]}
                 linkFor={(k) => q({ revalidation_status: k })} note="models with a due date" />
        <BarList title="Open findings by severity" items={dist.open_findings_by_severity} toneFor={(k) => STATUS_TONE[k] ?? "info"}
                 linkFor={() => q({ flag: "open_findings" })} note="findings" />
        <BarList title="Governance score" items={dist.score_band} label={(k) => BAND_LABEL[k] ?? k} toneFor={(k) => STATUS_TONE[k]}
                 linkFor={(k) => q({ flag: BAND_FLAG[k] })} note="scored models" />
      </div>

      <div className="cols">
        <section className="panel">
          <h4>Governance insights <small>{d.insights.length} of {d.insight_count} · generated from current data</small></h4>
          {d.insights.length === 0 ? <p className="note">No issues detected.</p> : (
            <ul className="insights">
              {d.insights.map((i, n) => (
                <li key={n}>
                  <Pill value={i.severity} tone={i.severity === "Critical" ? "p-bad" : i.severity === "High" ? "p-warn" : "p-info"} />
                  <div>
                    <Link to={i.link}>{i.message}</Link>
                    <div className="tile-sub">Source: {i.source}</div>
                  </div>
                </li>
              ))}
            </ul>
          )}
          {t.sod_breaches ? <p className="note" style={{ marginTop: 8 }}><Link to={q({ flag: "sod_breach" })}>{t.sod_breaches} segregation-of-duties breach(es)</Link></p> : null}
        </section>

        <section className="panel">
          <h4>Revalidation timeline <small>{d.revalidation_timeline.length} models in the Revalidation column</small></h4>
          {d.revalidation_timeline.length === 0 ? <p className="note">No models are due for revalidation.</p> : (
            <div className="tablewrap scroll">
              <table>
                <thead><tr><th>Model</th><th>Tier</th><th>Due</th><th>Days</th><th>Status</th></tr></thead>
                <tbody>
                  {d.revalidation_timeline.map((r) => (
                    <tr key={r.model_id}>
                      <td><Link className="mono" to={`/models/${r.model_id}`}>{r.model_id}</Link> {r.model_name}</td>
                      <td><Pill value={r.tier} /></td>
                      <td className="mono">{r.next_due ?? "—"}</td>
                      <td><DaysToDue days={r.days_to_due} /></td>
                      <td><Pill value={r.status} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      </div>

      <div className="cols">
        {Object.entries(d.pending).map(([k, text]) => (
          <div key={k} className="state"><b>{k === "monitoring" ? "Monitoring breaches & completion" : "Data-quality health"}</b>{text}</div>
        ))}
      </div>
    </div>
  );
}
