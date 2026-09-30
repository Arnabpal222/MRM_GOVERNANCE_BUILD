// Write actions on Model 360. Each form posts to the API; the server enforces permissions,
// segregation of duties and business rules, and its error message is shown as-is.
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";
import { api } from "../../api/client";
import type { Approval, Finding, ModelMeta, ModelRecord } from "../../api/types";

type Values = Record<string, string>;

function useModelMutation<T>(modelId: string, fn: (body: Record<string, unknown>) => Promise<T>, onDone?: () => void) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: fn,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["model", modelId] });
      qc.invalidateQueries({ queryKey: ["models"] });
      qc.invalidateQueries({ queryKey: ["audit"] });
      onDone?.();
    },
  });
}

function clean(values: Values): Record<string, unknown> {
  return Object.fromEntries(Object.entries(values).map(([k, v]) => [k, v === "" ? null : v]));
}

interface FieldSpec {
  name: string;
  label: string;
  type?: "text" | "date" | "select" | "textarea";
  options?: string[] | { value: string; label: string }[];
}

function ActionForm({ title, fields, initial, submitLabel, onSubmit, onCancel, pending, error }: {
  title: string; fields: FieldSpec[]; initial: Values; submitLabel: string; pending: boolean; error: unknown;
  onSubmit: (v: Values) => void; onCancel: () => void;
}) {
  const [values, setValues] = useState<Values>(initial);
  const set = (k: string, v: string) => setValues({ ...values, [k]: v });
  return (
    <form className="panel action-form" onSubmit={(e) => { e.preventDefault(); onSubmit(values); }}>
      <h4>{title}</h4>
      <div className="form-grid">
        {fields.map((f) => (
          <label key={f.name} className="field" style={f.type === "textarea" ? { gridColumn: "1 / -1" } : undefined}>
            {f.label}
            {f.type === "select" ? (
              <select className="select" value={values[f.name] ?? ""} onChange={(e) => set(f.name, e.target.value)}>
                <option value="">—</option>
                {(f.options ?? []).map((o) => typeof o === "string"
                  ? <option key={o} value={o}>{o}</option>
                  : <option key={o.value} value={o.value}>{o.label}</option>)}
              </select>
            ) : f.type === "textarea" ? (
              <textarea className="input" rows={2} value={values[f.name] ?? ""} onChange={(e) => set(f.name, e.target.value)} />
            ) : (
              <input className="input" type={f.type ?? "text"} value={values[f.name] ?? ""} onChange={(e) => set(f.name, e.target.value)} />
            )}
          </label>
        ))}
      </div>
      {error ? <div className="errline">{(error as Error).message}</div> : null}
      <div style={{ display: "flex", gap: 8 }}>
        <button className="btn primary" type="submit" disabled={pending}>{pending ? "Saving…" : submitLabel}</button>
        <button className="btn" type="button" onClick={onCancel}>Cancel</button>
      </div>
    </form>
  );
}

/** A button that reveals an action form in place. */
export function Reveal({ label, children }: { label: string; children: (close: () => void) => ReactNode }) {
  const [open, setOpen] = useState(false);
  if (!open) return <button className="btn sm" onClick={() => setOpen(true)}>{label}</button>;
  return <div style={{ width: "100%" }}>{children(() => setOpen(false))}</div>;
}

const userOptions = (meta: ModelMeta, role?: string) =>
  meta.users.filter((u) => u.active && (!role || u.roles.includes(role)))
    .map((u) => ({ value: u.user_id, label: `${u.full_name} (${u.user_id})` }));

export function TransitionForm({ model, meta, close }: { model: ModelRecord; meta: ModelMeta; close: () => void }) {
  const m = useModelMutation(model.model_id, (b) =>
    api(`/api/models/${model.model_id}/transition`, { method: "POST", json: { ...b, row_version: model.row_version } }), close);
  return (
    <ActionForm title="Change lifecycle phase" submitLabel="Record transition" pending={m.isPending} error={m.error}
      initial={{ to_phase: "", reason: "" }} onCancel={close} onSubmit={(v) => m.mutate(clean(v))}
      fields={[
        { name: "to_phase", label: "New phase", type: "select", options: meta.lifecycle_phases.filter((p) => p !== model.lifecycle_phase) },
        { name: "reason", label: "Reason", type: "textarea" },
      ]} />
  );
}

export function OverrideForm({ model, meta, close }: { model: ModelRecord; meta: ModelMeta; close: () => void }) {
  const m = useModelMutation(model.model_id, (b) =>
    api(`/api/models/${model.model_id}/tier-override`, { method: "POST", json: { ...b, row_version: model.row_version } }), close);
  return (
    <ActionForm title="Override risk tier" submitLabel="Apply" pending={m.isPending} error={m.error}
      initial={{ tier: model.tiering.override_tier ?? "", reason: "" }} onCancel={close}
      onSubmit={(v) => m.mutate({ tier: v.tier || null, reason: v.reason })}
      fields={[
        { name: "tier", label: `Override tier (blank removes the override; calculated: ${model.calculated_tier})`, type: "select", options: meta.tiers },
        { name: "reason", label: "Justification (required)", type: "textarea" },
      ]} />
  );
}

export function ValidationForm({ model, meta, close }: { model: ModelRecord; meta: ModelMeta; close: () => void }) {
  const m = useModelMutation(model.model_id, (b) => api("/api/validations", { method: "POST", json: { ...b, model_id: model.model_id } }), close);
  return (
    <ActionForm title="Record validation" submitLabel="Save validation" pending={m.isPending} error={m.error}
      initial={{ validation_type: "", validator_id: model.validator_id ?? "", start_date: "", completion_date: "", outcome: "", summary: "" }}
      onCancel={close} onSubmit={(v) => m.mutate(clean(v))}
      fields={[
        { name: "validation_type", label: "Type", type: "select", options: meta.validation_types },
        { name: "validator_id", label: "Validator", type: "select", options: userOptions(meta, "Validator") },
        { name: "start_date", label: "Start date", type: "date" },
        { name: "completion_date", label: "Completion date", type: "date" },
        { name: "outcome", label: "Outcome", type: "select", options: meta.validation_outcomes },
        { name: "summary", label: "Summary", type: "textarea" },
      ]} />
  );
}

export function FindingForm({ model, meta, close }: { model: ModelRecord; meta: ModelMeta; close: () => void }) {
  const m = useModelMutation(model.model_id, (b) => api("/api/findings", { method: "POST", json: { ...b, model_id: model.model_id } }), close);
  return (
    <ActionForm title="Raise finding" submitLabel="Save finding" pending={m.isPending} error={m.error}
      initial={{ title: "", severity: "", category: "", owner_id: model.owner_id, due_date: "", description: "" }}
      onCancel={close} onSubmit={(v) => m.mutate(clean(v))}
      fields={[
        { name: "title", label: "Title" },
        { name: "severity", label: "Severity", type: "select", options: meta.finding_severities },
        { name: "category", label: "Category", type: "select", options: meta.finding_categories },
        { name: "owner_id", label: "Owner", type: "select", options: userOptions(meta) },
        { name: "due_date", label: "Due date", type: "date" },
        { name: "description", label: "Description", type: "textarea" },
      ]} />
  );
}

export function FindingUpdateForm({ finding, meta, close }: { finding: Finding; meta: ModelMeta; close: () => void }) {
  const m = useModelMutation(finding.model_id, (b) =>
    api(`/api/findings/${finding.finding_id}`, { method: "PATCH", json: { ...b, row_version: finding.row_version } }), close);
  return (
    <ActionForm title={`Update ${finding.finding_id}`} submitLabel="Save" pending={m.isPending} error={m.error}
      initial={{ status: finding.status, due_date: finding.due_date, management_response: finding.management_response ?? "",
                 remediation_action: finding.remediation_action ?? "", reason: "" }}
      onCancel={close} onSubmit={(v) => m.mutate(clean(v))}
      fields={[
        { name: "status", label: "Status", type: "select", options: meta.finding_statuses },
        { name: "due_date", label: "Due date", type: "date" },
        { name: "management_response", label: "Management response", type: "textarea" },
        { name: "remediation_action", label: "Remediation action", type: "textarea" },
        { name: "reason", label: "Reason for change" },
      ]} />
  );
}

export function ApprovalForm({ model, meta, close }: { model: ModelRecord; meta: ModelMeta; close: () => void }) {
  const m = useModelMutation(model.model_id, (b) => api("/api/approvals", { method: "POST", json: { ...b, model_id: model.model_id } }), close);
  return (
    <ActionForm title="Record MRC / approval decision" submitLabel="Save decision" pending={m.isPending} error={m.error}
      initial={{ decision_date: "", forum: "", decision_type: "", decision: "", conditions: "", condition_due_date: "", condition_status: "" }}
      onCancel={close} onSubmit={(v) => m.mutate(clean(v))}
      fields={[
        { name: "decision_date", label: "Decision date", type: "date" },
        { name: "forum", label: "Forum", type: "select", options: meta.approval_forums },
        { name: "decision_type", label: "Decision type", type: "select", options: meta.approval_decision_types },
        { name: "decision", label: "Decision", type: "select", options: meta.approval_decisions },
        { name: "condition_due_date", label: "Condition due date", type: "date" },
        { name: "condition_status", label: "Condition status", type: "select", options: ["Open", "Met"] },
        { name: "conditions", label: "Conditions", type: "textarea" },
      ]} />
  );
}

export function MarkConditionMet({ approval }: { approval: Approval }) {
  const m = useModelMutation(approval.model_id, () =>
    api(`/api/approvals/${approval.approval_id}`, { method: "PATCH",
      json: { condition_status: "Met", row_version: approval.row_version, reason: "Conditions met" } }));
  return (
    <>
      <button className="btn sm" disabled={m.isPending} onClick={() => m.mutate({})}>Mark conditions met</button>
      {m.isError && <div className="errline">{(m.error as Error).message}</div>}
    </>
  );
}
