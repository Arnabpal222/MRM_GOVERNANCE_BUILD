import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "../api/client";
import type { DevUser } from "../api/types";
import { useAuth } from "../auth/AuthContext";

/** Dev-mode identity picker: one option per (user, role) pair. Replaced by OIDC sign-in in production. */
export function RoleSwitcher({ compact = false }: { compact?: boolean }) {
  const { me, signIn } = useAuth();
  const [error, setError] = useState<string | null>(null);
  const users = useQuery({ queryKey: ["dev-users"], queryFn: () => api<DevUser[]>("/api/auth/dev-users") });

  const options = (users.data ?? []).flatMap((u) =>
    u.roles.map((r) => ({ value: `${u.user_id}|${r}`, label: `${r} — ${u.full_name} (${u.user_id})` })),
  );
  const current = me ? `${me.user_id}|${me.role}` : "";

  async function onChange(value: string) {
    if (!value) return;
    const [userId, role] = value.split("|");
    setError(null);
    try {
      await signIn(userId, role);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  if (users.isError) return <span className="pill p-bad">Users unavailable: {(users.error as Error).message}</span>;

  return (
    <>
      <select
        className="select"
        aria-label="Act as user and role"
        value={current}
        onChange={(e) => onChange(e.target.value)}
        disabled={users.isLoading}
        style={compact ? { maxWidth: 320 } : { width: "100%" }}
      >
        {!me && <option value="">{users.isLoading ? "Loading users…" : "Choose user and role…"}</option>}
        {options.map((o) => (
          <option key={o.value} value={o.value}>{o.label}</option>
        ))}
      </select>
      {error && <div className="errline">{error}</div>}
    </>
  );
}
