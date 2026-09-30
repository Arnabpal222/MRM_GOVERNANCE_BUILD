import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { ApiError, api } from "../api/client";
import { useModel360, useModelMeta } from "../api/queries";
import type { ModelMeta, ModelRecord } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { Pill } from "../components/Pills";
import { ErrorState, Loading, PageHeader } from "../components/States";

type Form = Record<string, string>;

const TEXT_FIELDS = ["model_name", "model_subtype", "business_line", "model_family", "version"] as const;
const QUESTIONS = ["q_materiality", "q_complexity", "q_reliance", "q_regulatory_use"] as const;

const EMPTY: Form = {
  model_id: "", model_name: "", model_type: "", model_subtype: "", purpose: "", business_line: "", model_family: "",
  owner_id: "", developer_id: "", validator_id: "", lifecycle_phase: "", version: "v1.0", go_live_date: "",
  revalidation_frequency: "", last_validation_date: "", q_materiality: "2", q_complexity: "2", q_reliance: "2",
  q_regulatory_use: "2", reason: "",
};

function fromRecord(m: ModelRecord): Form {
  const f: Form = { ...EMPTY };
  for (const k of Object.keys(EMPTY)) {
    const v = (m as unknown as Record<string, unknown>)[k];
    if (v !== undefined && v !== null) f[k] = String(v);
  }
  for (const q of QUESTIONS) f[q] = String(m.tiering[q]);
  f.reason = "";
  return f;
}

function usersWithRole(meta: ModelMeta | undefined, role: string) {
  return (meta?.users ?? []).filter((u) => u.active && u.roles.includes(role));
}

function TierPreview({ answers }: { answers: Record<string, number> }) {
  const preview = useQuery({
    queryKey: ["tier-preview", answers],
    queryFn: () => api<{ tier_score: number; tier: string; thresholds: Record<string, number> }>(
      "/api/models/tier-preview", { method: "POST", json: answers }),
  });
  if (!preview.data) return <span className="pill p-mute">calculating…</span>;
  const t = preview.data.thresholds;
  return (
    <span title={`High ≥ ${t.high_min}, Medium ≥ ${t.medium_min}`}>
      Score <b className="mono">{preview.data.tier_score}</b> → <Pill value={preview.data.tier} />
    </span>
  );
}

export function ModelForm() {
  const { modelId } = useParams();
  const editing = !!modelId;
  const navigate = useNavigate();
  const qc = useQueryClient();
  const { can } = useAuth();
  const meta = useModelMeta();
  const existing = useModel360(modelId);
  const [form, setForm] = useState<Form>(EMPTY);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});

  useEffect(() => {
    if (existing.data) setForm(fromRecord(existing.data.model));
  }, [existing.data]);

  const save = useMutation({
    mutationFn: () => {
      const body: Record<string, unknown> = {};
      for (const [k, v] of Object.entries(form)) body[k] = v === "" ? null : v;
      for (const q of QUESTIONS) body[q] = Number(form[q]);
      if (editing) {
        delete body.model_id;
        body.row_version = existing.data!.model.row_version;
        return api<ModelRecord>(`/api/models/${modelId}`, { method: "PUT", json: body });
      }
      return api<ModelRecord>("/api/models", { method: "POST", json: body });
    },
    onSuccess: (m) => {
      qc.invalidateQueries({ queryKey: ["models"] });
      qc.invalidateQueries({ queryKey: ["model", m.model_id] });
      qc.invalidateQueries({ queryKey: ["model-meta"] });
      navigate(`/models/${m.model_id}`);
    },
    onError: (e) => {
      const errs: Record<string, string> = {};
      if (e instanceof ApiError) {
        for (const d of e.details as { field?: string; message?: string }[]) {
          if (d.field) errs[d.field] = errs[d.field] ? `${errs[d.field]} ${d.message}` : d.message ?? "";
        }
      }
      setFieldErrors(errs);
    },
  });

  if (!can("model:edit")) return <ErrorState title="Not permitted" error="Your role cannot register or edit models." />;
  if (meta.isLoading || (editing && existing.isLoading)) return <Loading />;
  if (meta.isError) return <ErrorState error={meta.error} />;
  if (existing.isError) return <ErrorState error={existing.error} />;

  const set = (k: string) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) =>
    setForm({ ...form, [k]: e.target.value });

  const field = (k: string, label: string, control: React.ReactNode, hint?: string) => (
    <label className="field" key={k}>
      {label}
      {control}
      {hint && <small style={{ color: "var(--faint)" }}>{hint}</small>}
      {fieldErrors[k] && <span className="field-error">{fieldErrors[k]}</span>}
    </label>
  );
  const sel = (k: string, options: { value: string; label: string }[], allowBlank = true) => (
    <select className="select" value={form[k]} onChange={set(k)}>
      {allowBlank && <option value="">—</option>}
      {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
    </select>
  );
  const opts = (xs: string[] | undefined) => (xs ?? []).map((x) => ({ value: x, label: x }));
  const userOpts = (role: string) => usersWithRole(meta.data, role).map((u) => ({ value: u.user_id, label: `${u.full_name} (${u.user_id})` }));
  const answers = Object.fromEntries(QUESTIONS.map((q) => [q, Number(form[q])]));

  return (
    <div className="stack">
      <PageHeader eyebrow="Model inventory" title={editing ? `Edit ${modelId}` : "Register model"}
                  lede="The risk tier is calculated on the server from the tiering answers. Segregation of duties and phase requirements are checked when you save." />
      <form className="stack" onSubmit={(e) => { e.preventDefault(); setFieldErrors({}); save.mutate(); }}>
        <section className="panel">
          <h4>Profile</h4>
          <div className="form-grid">
            {!editing && field("model_id", "Model ID", <input className="input" value={form.model_id} onChange={set("model_id")} placeholder="auto (M-####)" />)}
            {TEXT_FIELDS.map((k) => field(k, k.replace("_", " ").replace(/^\w/, (c) => c.toUpperCase()),
              <input className="input" value={form[k]} onChange={set(k)} />))}
            {field("model_type", "Model type", sel("model_type", opts(meta.data?.model_types)))}
            {field("lifecycle_phase", "Lifecycle phase", sel("lifecycle_phase", opts(meta.data?.lifecycle_phases)),
              editing ? "Changing the phase records a lifecycle transition." : undefined)}
          </div>
          {field("purpose", "Purpose", <textarea className="input" rows={3} value={form.purpose} onChange={set("purpose")} />)}
        </section>

        <section className="panel">
          <h4>Ownership <small>Validator must be independent of owner and developer</small></h4>
          <div className="form-grid">
            {field("owner_id", "Owner", sel("owner_id", userOpts("Model Owner")))}
            {field("developer_id", "Developer", sel("developer_id", userOpts("Model Developer")))}
            {field("validator_id", "Validator", sel("validator_id", userOpts("Validator")))}
          </div>
        </section>

        <section className="panel">
          <h4>Validation schedule</h4>
          <div className="form-grid">
            {field("go_live_date", "Go-live date", <input className="input" type="date" value={form.go_live_date} onChange={set("go_live_date")} />)}
            {field("revalidation_frequency", "Revalidation frequency", sel("revalidation_frequency", opts(meta.data?.revalidation_frequencies)))}
            {field("last_validation_date", "Last validation date", <input className="input" type="date" value={form.last_validation_date} onChange={set("last_validation_date")} />)}
          </div>
        </section>

        <section className="panel">
          <h4>Risk tiering <small><TierPreview answers={answers} /></small></h4>
          <div className="form-grid">
            {QUESTIONS.map((q) => field(q, meta.data?.tiering_questions[q] ?? q,
              sel(q, [{ value: "1", label: "1 — Low" }, { value: "2", label: "2 — Medium" }, { value: "3", label: "3 — High" }], false)))}
          </div>
          {fieldErrors.tiering && <span className="field-error">{fieldErrors.tiering}</span>}
        </section>

        {editing && field("reason", "Reason for change (recorded in the audit trail)",
          <input className="input" value={form.reason} onChange={set("reason")} />)}

        {save.isError && <div className="errline">{(save.error as Error).message}</div>}
        <div style={{ display: "flex", gap: 8 }}>
          <button className="btn primary" type="submit" disabled={save.isPending}>{save.isPending ? "Saving…" : "Save"}</button>
          <button className="btn" type="button" onClick={() => navigate(editing ? `/models/${modelId}` : "/operations")}>Cancel</button>
        </div>
      </form>
    </div>
  );
}
