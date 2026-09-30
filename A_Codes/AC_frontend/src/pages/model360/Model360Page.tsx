import { useQuery } from "@tanstack/react-query";
import { Fragment, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api } from "../../api/client";
import { useModel360, useModelMeta } from "../../api/queries";
import type { AuditEvent, DocumentSummary, Model360, ModelMeta } from "../../api/types";
import { CompletenessPanel, SingleUploadForm } from "../documents/shared";
import { useAuth } from "../../auth/AuthContext";
import { DaysToDue, Pill, ScoreValue, SeverityPill } from "../../components/Pills";
import { EmptyState, ErrorState, Loading } from "../../components/States";
import {
  ApprovalForm, FindingForm, FindingUpdateForm, MarkConditionMet, OverrideForm, Reveal, TransitionForm, ValidationForm,
} from "./actions";

const TABS = ["Overview", "Validation", "Findings", "Approvals", "Score", "Documents", "Monitoring", "CDE / DQ", "History"] as const;
type Tab = (typeof TABS)[number];

const LATER: Partial<Record<Tab, string>> = {
  Monitoring: "Monitoring plan, runs, KPI scorecard, trends and breaches arrive with Model Monitoring (Phase 6).",
  "CDE / DQ": "Critical data elements and data-quality results arrive with Data Audit (Phase 7).",
};

function fmt(d: string | null | undefined) {
  return d ? new Date(d).toLocaleDateString() : "—";
}

function KV({ rows }: { rows: [string, React.ReactNode][] }) {
  return (
    <dl className="kv">
      {rows.map(([k, v]) => (
        <div key={k}><dt>{k}</dt><dd>{v ?? "—"}</dd></div>
      ))}
    </dl>
  );
}

function Stepper({ phases, current }: { phases: string[]; current: string }) {
  const idx = phases.indexOf(current);
  return (
    <ol className="stepper">
      {phases.map((p, i) => (
        <li key={p} className={i < idx ? "done" : i === idx ? "cur" : ""}><span className="dot" />{p}</li>
      ))}
    </ol>
  );
}

function Overview({ d, meta, name }: { d: Model360; meta: ModelMeta; name: (id: string | null) => string }) {
  const m = d.model;
  return (
    <div className="cols">
      <section className="panel">
        <h4>Profile</h4>
        <p style={{ margin: "0 0 10px", color: "var(--muted)" }}>{m.purpose}</p>
        <KV rows={[["Type", `${m.model_type} · ${m.model_subtype}`], ["Business line", m.business_line],
          ["Model family", m.model_family], ["Version", <span className="mono">{m.version}</span>],
          ["Go-live", fmt(m.go_live_date)]]} />
      </section>
      <section className="panel">
        <h4>Owners</h4>
        <KV rows={[["Owner", name(m.owner_id)], ["Developer", name(m.developer_id)], ["Validator", name(m.validator_id)]]} />
        {d.state.sod_breach && <div className="errline" style={{ marginTop: 10 }}>{d.state.sod_breach}</div>}
      </section>
      <section className="panel">
        <h4>Revalidation</h4>
        <KV rows={[["Frequency", m.revalidation_frequency], ["Last validation", fmt(m.last_validation_date)],
          ["Next due", fmt(d.state.next_due)], ["Days to due", <DaysToDue days={d.state.days_to_due} />],
          ["Status", <Pill value={d.state.revalidation_status} />], ["Stage", d.state.displayed_column]]} />
      </section>
      <section className="panel">
        <h4>Risk tier <small>score {m.tier_score}</small></h4>
        <KV rows={[
          ...Object.entries(meta.tiering_questions).map(([q, text]) =>
            [text, <span className="mono">{(m.tiering as unknown as Record<string, number>)[q]}</span>] as [string, React.ReactNode]),
          ["Calculated tier", <Pill value={m.calculated_tier} />],
          ["Override", m.tiering.override_tier ? <><Pill value={m.tiering.override_tier} /> {m.tiering.override_reason}</> : "None"],
        ]} />
        {d.tier_overrides.length > 0 && (
          <ul className="checklist" style={{ marginTop: 10 }}>
            {d.tier_overrides.map((o, i) => (
              <li key={i}>{fmt(o.created_at)} · {o.previous_tier} → {o.new_tier} by {o.user_id}: {o.reason}</li>
            ))}
          </ul>
        )}
      </section>
      <section className="panel" style={{ gridColumn: "1 / -1" }}>
        <h4>Lifecycle</h4>
        <Stepper phases={meta.lifecycle_phases} current={m.lifecycle_phase} />
        <ul className="checklist" style={{ marginTop: 12 }}>
          {d.phase_history.map((h, i) => (
            <li key={i}>{fmt(h.changed_at)} · {h.from_phase ?? "—"} → <b>{h.to_phase}</b>{h.user_id ? ` by ${h.user_id}` : ""}{h.reason ? ` — ${h.reason}` : ""}</li>
          ))}
        </ul>
      </section>
      <section className="panel">
        <h4>Related models</h4>
        {d.relationships.length === 0 ? <p className="note">No related models.</p> : (
          <ul className="checklist">
            {d.relationships.map((r) => (
              <li key={r.relationship + r.model_id}>{r.relationship}: <Link to={`/models/${r.model_id}`}>{r.model_id}</Link> {r.model_name}</li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

function DocumentsTab({ modelId }: { modelId: string }) {
  const { can } = useAuth();
  const docs = useQuery({
    queryKey: ["documents", `model_id=${modelId}`],
    queryFn: () => api<DocumentSummary[]>(`/api/documents?model_id=${modelId}`),
  });
  return (
    <div className="stack">
      <CompletenessPanel modelId={modelId} />
      {can("document:upload") && <Reveal label="Upload document">{(close) => <SingleUploadForm fixedModelId={modelId} onDone={close} />}</Reveal>}
      {docs.isLoading ? <Loading /> : docs.isError ? <ErrorState error={docs.error} /> : !docs.data!.length ?
        <EmptyState title="No documents for this model">Upload them here or in the Document Centre.</EmptyState> : (
        <div className="tablewrap">
          <table>
            <thead><tr><th>Document</th><th>Title</th><th>Type</th><th>Version</th><th>File</th><th>Folder</th><th>Uploaded</th></tr></thead>
            <tbody>
              {docs.data!.map((x) => (
                <tr key={x.document_id}>
                  <td className="mono"><Link to={`/documents/${x.document_id}`}>{x.document_id}</Link></td>
                  <td>{x.title}</td><td>{x.document_type}</td><td className="mono">{x.current_version}</td>
                  <td className="mono">{x.file_name}</td><td className="mono" style={{ color: "var(--muted)" }}>{x.folder_path ?? "—"}</td>
                  <td className="mono">{new Date(x.uploaded_at).toLocaleDateString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function ScorePanel({ d }: { d: Model360 }) {
  if (d.score.overall === null && d.score.components.length === 0) {
    return <EmptyState title="No governance score">{d.score.reason}</EmptyState>;
  }
  return (
    <section className="panel">
      <h4>Governance score <small>calculated {new Date(d.score.calculated_at).toLocaleString()}</small></h4>
      <p style={{ fontSize: 28, margin: "0 0 12px" }}><ScoreValue value={d.score.overall} /></p>
      <div className="tablewrap">
        <table>
          <thead><tr><th>Component</th><th>Weight</th><th>Applied weight</th><th>Score</th><th>How it was calculated</th><th>Missing information</th></tr></thead>
          <tbody>
            {d.score.components.map((c) => (
              <tr key={c.key}>
                <td>{c.label}</td>
                <td className="mono">{Number(c.weight)}%</td>
                <td className="mono">{c.effective_weight ? `${c.effective_weight}%` : "—"}</td>
                <td><ScoreValue value={c.score} /></td>
                <td>{c.explanation}</td>
                <td style={{ color: "var(--muted)" }}>{c.missing.join("; ") || "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="note" style={{ marginTop: 10 }}>Weights come from policy settings and are rescaled to 100% across applicable components.</p>
    </section>
  );
}

function HistoryPanel({ modelId, d }: { modelId: string; d: Model360 }) {
  const { can } = useAuth();
  const events = useQuery({
    queryKey: ["audit", { model_id: modelId }],
    queryFn: () => api<AuditEvent[]>(`/api/audit?model_id=${modelId}`),
    enabled: can("audit:read"),
  });
  return (
    <div className="stack">
      <section className="panel">
        <h4>Versions</h4>
        <ul className="checklist">
          {d.versions.map((v) => <li key={v.version}><span className="mono">{v.version}</span> · {fmt(v.recorded_at)} {v.change_reason ? `— ${v.change_reason}` : ""}</li>)}
        </ul>
      </section>
      <section className="panel">
        <h4>Audit history</h4>
        {!can("audit:read") ? <p className="note">Your role cannot read the audit trail.</p>
          : events.isLoading ? <Loading /> : events.isError ? <ErrorState error={events.error} /> : (
            <div className="tablewrap">
              <table>
                <thead><tr><th>When</th><th>User</th><th>Action</th><th>Entity</th><th>Record</th><th>Reason</th></tr></thead>
                <tbody>
                  {(events.data ?? []).map((e) => (
                    <tr key={e.event_id}>
                      <td className="mono">{new Date(e.occurred_at).toLocaleString()}</td>
                      <td className="mono">{e.user_id ?? "system"} <span style={{ color: "var(--faint)" }}>{e.role}</span></td>
                      <td><Pill value={e.action} tone="p-info" /></td>
                      <td className="mono">{e.entity}</td>
                      <td className="mono">{e.entity_id}</td>
                      <td>{e.reason}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
      </section>
    </div>
  );
}

export function Model360Page() {
  const { modelId } = useParams();
  const navigate = useNavigate();
  const { can } = useAuth();
  const meta = useModelMeta();
  const q = useModel360(modelId);
  const [tab, setTab] = useState<Tab>("Overview");
  const [editingFinding, setEditingFinding] = useState<string | null>(null);

  if (q.isLoading || meta.isLoading) return <Loading />;
  if (q.isError) return <ErrorState error={q.error} title={`Model ${modelId}`} />;
  if (meta.isError) return <ErrorState error={meta.error} />;
  const d = q.data!, m = d.model, md = meta.data!;
  const name = (id: string | null) => (id ? `${d.user_names[id] ?? id} (${id})` : "—");

  return (
    <div className="stack">
      <header className="m360-head">
        <div>
          <div className="eyebrow">Model 360 · <Link to="/operations">Operations Board</Link></div>
          <h1><span className="mono" style={{ color: "var(--muted)" }}>{m.model_id}</span> {m.model_name}</h1>
          <div className="filters">
            <Pill value={m.effective_tier} />
            {m.tiering.override_tier && <span className="pill p-mute">calculated {m.calculated_tier}</span>}
            <span className="pill p-acc">{m.lifecycle_phase}</span>
            {d.state.displayed_column !== m.lifecycle_phase && <span className="pill p-warn">{d.state.displayed_column}</span>}
            <span className="pill p-mute mono">{m.version}</span>
            {d.state.revalidation_status && <><Pill value={d.state.revalidation_status} /> <DaysToDue days={d.state.days_to_due} /></>}
          </div>
        </div>
        <div className="m360-score">
          <span>Governance score</span>
          <b><ScoreValue value={d.score.overall} /></b>
        </div>
      </header>

      {d.state.sod_breach && (
        <div className="state error"><b>Segregation of duties breach</b>{d.state.sod_breach}{m.legacy_sod_exception ? " Loaded as a legacy exception; reassign the validator to resolve it." : ""}</div>
      )}

      <div className="filters">
        {can("model:edit") && <button className="btn sm" onClick={() => navigate(`/models/${m.model_id}/edit`)}>Edit model</button>}
        {can("model:edit") && <Reveal label="Change phase">{(close) => <TransitionForm model={m} meta={md} close={close} />}</Reveal>}
        {can("tier:override") && <Reveal label="Override tier">{(close) => <OverrideForm model={m} meta={md} close={close} />}</Reveal>}
      </div>

      <nav className="tabs" role="tablist">
        {TABS.map((t) => (
          <button key={t} role="tab" aria-selected={tab === t} className={tab === t ? "on" : ""} onClick={() => setTab(t)}>
            {t}
            {t === "Findings" && d.state.open_findings > 0 && <span className="count">{d.state.open_findings}</span>}
            {t === "Approvals" && d.state.open_conditions > 0 && <span className="count">{d.state.open_conditions}</span>}
          </button>
        ))}
      </nav>

      {tab === "Overview" && <Overview d={d} meta={md} name={name} />}

      {tab === "Validation" && (
        <section className="stack">
          {can("validation:edit") && <Reveal label="Record validation">{(close) => <ValidationForm model={m} meta={md} close={close} />}</Reveal>}
          {d.validations.length === 0 ? <EmptyState title="No validations recorded for this model" /> : (
            <div className="tablewrap">
              <table>
                <thead><tr><th>ID</th><th>Type</th><th>Validator</th><th>Start</th><th>Completed</th><th>Outcome</th><th>Summary</th></tr></thead>
                <tbody>
                  {d.validations.map((v) => (
                    <tr key={v.validation_id}>
                      <td className="mono">{v.validation_id}</td><td>{v.validation_type}</td><td>{name(v.validator_id)}</td>
                      <td className="mono">{v.start_date}</td><td className="mono">{v.completion_date ?? "—"}</td>
                      <td><Pill value={v.outcome} /></td><td>{v.summary}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      )}

      {tab === "Findings" && (
        <section className="stack">
          {can("finding:edit") && <Reveal label="Raise finding">{(close) => <FindingForm model={m} meta={md} close={close} />}</Reveal>}
          {d.findings.length === 0 ? <EmptyState title="No findings for this model" /> : (
            <div className="tablewrap">
              <table>
                <thead><tr><th>ID</th><th>Finding</th><th>Severity</th><th>Category</th><th>Status</th><th>Owner</th><th>Due</th><th>Age</th><th /></tr></thead>
                <tbody>
                  {d.findings.map((f) => (
                    <Fragment key={f.finding_id}>
                      <tr>
                        <td className="mono">{f.finding_id}</td>
                        <td><b>{f.title}</b><div style={{ color: "var(--muted)" }}>{f.description}</div></td>
                        <td><SeverityPill value={f.severity} /></td>
                        <td>{f.category}</td>
                        <td><Pill value={f.status} /></td>
                        <td>{name(f.owner_id)}</td>
                        <td className="mono">{f.due_date}{f.is_overdue && <div style={{ color: "var(--bad)" }}>{f.days_overdue}d overdue</div>}</td>
                        <td className="mono">{f.days_open}d</td>
                        <td>{can("finding:edit") && <button className="btn sm" onClick={() => setEditingFinding(editingFinding === f.finding_id ? null : f.finding_id)}>Update</button>}</td>
                      </tr>
                      {editingFinding === f.finding_id && (
                        <tr><td colSpan={9}><FindingUpdateForm finding={f} meta={md} close={() => setEditingFinding(null)} /></td></tr>
                      )}
                    </Fragment>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      )}

      {tab === "Approvals" && (
        <section className="stack">
          {can("approval:record") && <Reveal label="Record decision">{(close) => <ApprovalForm model={m} meta={md} close={close} />}</Reveal>}
          {d.approvals.length === 0 ? <EmptyState title="No MRC or approval decisions recorded" /> : (
            <div className="tablewrap">
              <table>
                <thead><tr><th>ID</th><th>Date</th><th>Forum</th><th>Type</th><th>Decision</th><th>Conditions</th><th>Condition due</th><th>Status</th><th /></tr></thead>
                <tbody>
                  {d.approvals.map((a) => (
                    <tr key={a.approval_id}>
                      <td className="mono">{a.approval_id}</td><td className="mono">{a.decision_date}</td><td>{a.forum}</td>
                      <td>{a.decision_type}</td><td><Pill value={a.decision} /></td><td>{a.conditions}</td>
                      <td className="mono">{a.condition_due_date ?? "—"}</td><td><Pill value={a.condition_status} /></td>
                      <td>{can("approval:record") && a.condition_status === "Open" && <MarkConditionMet approval={a} />}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      )}

      {tab === "Documents" && <DocumentsTab modelId={m.model_id} />}
      {tab === "Score" && <ScorePanel d={d} />}
      {tab === "History" && <HistoryPanel modelId={m.model_id} d={d} />}
      {LATER[tab] && <EmptyState title={`No ${tab.toLowerCase()} data yet`}>{LATER[tab]}</EmptyState>}
    </div>
  );
}
