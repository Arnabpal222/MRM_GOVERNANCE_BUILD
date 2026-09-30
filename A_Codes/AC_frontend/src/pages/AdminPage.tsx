import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import type { ImportBatch, PolicySetting, User } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { EmptyState, ErrorState, Loading, PageHeader } from "../components/States";

function PolicyRow({ setting, editable }: { setting: PolicySetting; editable: boolean }) {
  const qc = useQueryClient();
  const [draft, setDraft] = useState<string | null>(null);
  const save = useMutation({
    mutationFn: (value: string) =>
      api<PolicySetting>(`/api/admin/policy/${setting.setting_key}`, {
        method: "PUT",
        json: { value, row_version: setting.row_version },
      }),
    onSuccess: () => {
      setDraft(null);
      qc.invalidateQueries({ queryKey: ["policy"] });
    },
  });

  return (
    <tr>
      <td className="mono">{setting.setting_key}</td>
      <td>
        {draft === null ? (
          <span className="mono">{setting.value}</span>
        ) : (
          <input
            className="input"
            style={{ width: "100%", minWidth: 160 }}
            value={draft}
            autoFocus
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") save.mutate(draft);
              if (e.key === "Escape") setDraft(null);
            }}
          />
        )}
        {save.isError && <div className="errline" style={{ marginTop: 6 }}>{(save.error as Error).message}</div>}
      </td>
      <td><span className="pill p-mute">{setting.value_type}</span></td>
      <td style={{ color: "var(--muted)" }}>{setting.description}</td>
      <td className="mono" style={{ color: "var(--faint)" }}>{setting.updated_by ?? "system"}</td>
      <td>
        {editable &&
          (draft === null ? (
            <button className="btn sm" onClick={() => setDraft(setting.value)}>Edit</button>
          ) : (
            <span style={{ display: "flex", gap: 6 }}>
              <button className="btn sm primary" disabled={save.isPending} onClick={() => save.mutate(draft)}>Save</button>
              <button className="btn sm" onClick={() => { setDraft(null); save.reset(); }}>Cancel</button>
            </span>
          ))}
      </td>
    </tr>
  );
}

function PolicyPanel() {
  const { can } = useAuth();
  const policy = useQuery({ queryKey: ["policy"], queryFn: () => api<PolicySetting[]>("/api/admin/policy") });
  if (policy.isLoading) return <Loading />;
  if (policy.isError) return <ErrorState error={policy.error} />;
  if (!policy.data?.length) return <EmptyState title="No policy settings loaded">Run the bootstrap load.</EmptyState>;

  const byCategory = new Map<string, PolicySetting[]>();
  for (const s of policy.data) {
    const key = s.category ?? "Other";
    byCategory.set(key, [...(byCategory.get(key) ?? []), s]);
  }
  const editable = can("policy:edit");

  return (
    <section className="panel">
      <h4>
        Policy settings
        <small>{editable ? "Every change is versioned and audited" : "Read-only for your role"}</small>
      </h4>
      <div className="tablewrap">
        <table>
          <thead>
            <tr><th>Key</th><th>Value</th><th>Type</th><th>Description</th><th>Updated by</th><th /></tr>
          </thead>
          {[...byCategory.entries()].map(([category, rows]) => (
            <tbody key={category}>
              <tr><td colSpan={6} className="eyebrow" style={{ background: "var(--sunk)" }}>{category}</td></tr>
              {rows.map((s) => <PolicyRow key={s.setting_key} setting={s} editable={editable} />)}
            </tbody>
          ))}
        </table>
      </div>
    </section>
  );
}

function UsersPanel() {
  const users = useQuery({ queryKey: ["users"], queryFn: () => api<User[]>("/api/users") });
  if (users.isLoading) return <Loading />;
  if (users.isError) return <ErrorState error={users.error} />;
  if (!users.data?.length) return <EmptyState title="No users loaded" />;
  return (
    <section className="panel">
      <h4>Users and roles <small>{users.data.length} users</small></h4>
      <div className="tablewrap">
        <table>
          <thead><tr><th>User</th><th>Name</th><th>Email</th><th>Roles</th><th>Business line</th><th>Status</th></tr></thead>
          <tbody>
            {users.data.map((u) => (
              <tr key={u.user_id}>
                <td className="mono">{u.user_id}</td>
                <td>{u.full_name}</td>
                <td className="mono">{u.email}</td>
                <td>{u.roles.map((r) => <span key={r} className="pill p-acc" style={{ marginRight: 4 }}>{r}</span>)}</td>
                <td>{u.business_line}</td>
                <td><span className={`pill ${u.active ? "p-good" : "p-mute"}`}>{u.active ? "Active" : "Inactive"}</span></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function ResetPanel() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [confirm, setConfirm] = useState("");
  const reset = useMutation({
    mutationFn: () => api<ImportBatch>("/api/admin/reset", { method: "POST" }),
    onSuccess: (b) => {
      qc.clear();
      navigate(`/imports/${b.batch_id}`);
    },
  });
  return (
    <section className="panel" style={{ borderColor: "var(--bad)" }}>
      <h4>Reset to seed <small>demo and development environments only</small></h4>
      <p className="note">
        Deletes all models, validations, findings, approvals, users and policy settings, then reloads the seed
        (256 models) through the import engine for today's date. The audit trail and import history are kept, and the
        reset itself is recorded.
      </p>
      <div className="filters" style={{ marginTop: 10 }}>
        <input className="input" placeholder="Type RESET to confirm" value={confirm} onChange={(e) => setConfirm(e.target.value)} />
        <button className="btn" style={{ borderColor: "var(--bad)", color: "var(--bad)" }}
                disabled={confirm !== "RESET" || reset.isPending} onClick={() => reset.mutate()}>
          {reset.isPending ? "Resetting…" : "Reset to seed"}
        </button>
      </div>
      {reset.isError && <div className="errline" style={{ marginTop: 8 }}>{(reset.error as Error).message}</div>}
    </section>
  );
}

export function AdminPage() {
  const { can } = useAuth();
  return (
    <div className="stack">
      <PageHeader
        eyebrow="Control"
        title="Admin"
        lede="Configuration that drives every business rule: tier thresholds, score weights, revalidation, documents, monitoring and file limits."
      />
      <PolicyPanel />
      <UsersPanel />
      {can("policy:edit") && <ResetPanel />}
    </div>
  );
}
