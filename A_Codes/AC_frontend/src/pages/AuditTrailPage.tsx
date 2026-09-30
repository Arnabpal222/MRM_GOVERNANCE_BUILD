import { useQuery } from "@tanstack/react-query";
import { Fragment, useState } from "react";
import { api } from "../api/client";
import type { AuditEvent } from "../api/types";
import { EmptyState, ErrorState, Loading, PageHeader } from "../components/States";

const FILTERS = [
  { key: "user_id", label: "User", placeholder: "U-001" },
  { key: "model_id", label: "Model", placeholder: "M-0012" },
  { key: "entity", label: "Entity", placeholder: "policy_setting" },
  { key: "action", label: "Action", placeholder: "update" },
  { key: "batch_id", label: "Batch", placeholder: "B-…" },
  { key: "document_id", label: "Document", placeholder: "D-…" },
] as const;

type Filters = Record<string, string>;

const ACTION_TONE: Record<string, string> = { create: "p-good", update: "p-info", delete: "p-bad" };

function Diff({ event }: { event: AuditEvent }) {
  const keys = [...new Set([...Object.keys(event.before_json ?? {}), ...Object.keys(event.after_json ?? {})])];
  const show = (v: unknown) => (v === undefined ? "—" : JSON.stringify(v));
  return (
    <table>
      <thead><tr><th>Field</th><th>Before</th><th>After</th></tr></thead>
      <tbody>
        {keys.map((k) => {
          const before = event.before_json?.[k];
          const after = event.after_json?.[k];
          const changed = JSON.stringify(before) !== JSON.stringify(after);
          return (
            <tr key={k}>
              <td className="mono">{k}</td>
              <td className="mono" style={{ color: changed ? "var(--bad)" : "var(--muted)" }}>{show(before)}</td>
              <td className="mono" style={{ color: changed ? "var(--good)" : "var(--muted)" }}>{show(after)}</td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

export function AuditTrailPage() {
  const [draft, setDraft] = useState<Filters>({});
  const [applied, setApplied] = useState<Filters>({});
  const [open, setOpen] = useState<number | null>(null);

  const params = new URLSearchParams(Object.entries(applied).filter(([, v]) => v.trim() !== ""));
  const events = useQuery({
    queryKey: ["audit", applied],
    queryFn: () => api<AuditEvent[]>(`/api/audit?${params}`),
  });

  return (
    <div className="stack">
      <PageHeader
        eyebrow="Control"
        title="Audit Trail"
        lede="Every material write, with who made it, in which role, when, and the before and after values. Records are append-only."
      />
      <form
        className="filters"
        onSubmit={(e) => {
          e.preventDefault();
          setApplied(draft);
        }}
      >
        {FILTERS.map((f) => (
          <input
            key={f.key}
            className="input"
            aria-label={f.label}
            placeholder={`${f.label}: ${f.placeholder}`}
            value={draft[f.key] ?? ""}
            onChange={(e) => setDraft({ ...draft, [f.key]: e.target.value })}
            style={{ width: 150 }}
          />
        ))}
        <input className="input" type="date" aria-label="From date" value={draft.date_from ?? ""}
               onChange={(e) => setDraft({ ...draft, date_from: e.target.value })} />
        <input className="input" type="date" aria-label="To date" value={draft.date_to ?? ""}
               onChange={(e) => setDraft({ ...draft, date_to: e.target.value })} />
        <button className="btn primary" type="submit">Apply</button>
        <button className="btn" type="button" onClick={() => { setDraft({}); setApplied({}); }}>Clear</button>
      </form>

      {events.isLoading && <Loading />}
      {events.isError && <ErrorState error={events.error} />}
      {events.data && events.data.length === 0 && <EmptyState title="No audit events match these filters" />}
      {events.data && events.data.length > 0 && (
        <div className="tablewrap">
          <table>
            <thead>
              <tr><th>When</th><th>User</th><th>Role</th><th>Action</th><th>Entity</th><th>Record</th><th>Model</th><th>Reason</th></tr>
            </thead>
            <tbody>
              {events.data.map((e) => (
                <Fragment key={e.event_id}>
                  <tr className="click" onClick={() => setOpen(open === e.event_id ? null : e.event_id)}>
                    <td className="mono">{new Date(e.occurred_at).toLocaleString()}</td>
                    <td className="mono">{e.user_id ?? "system"}</td>
                    <td>{e.role}</td>
                    <td><span className={`pill ${ACTION_TONE[e.action] ?? "p-mute"}`}>{e.action}</span></td>
                    <td className="mono">{e.entity}</td>
                    <td className="mono">{e.entity_id}</td>
                    <td className="mono">{e.model_id ?? ""}</td>
                    <td>{e.reason ?? ""}</td>
                  </tr>
                  {open === e.event_id && (
                    <tr>
                      <td colSpan={8} style={{ background: "var(--sunk)" }}><Diff event={e} /></td>
                    </tr>
                  )}
                </Fragment>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
