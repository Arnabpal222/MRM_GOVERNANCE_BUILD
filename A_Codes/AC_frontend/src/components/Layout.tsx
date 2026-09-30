import { useQuery } from "@tanstack/react-query";
import { NavLink, Outlet } from "react-router-dom";
import { api } from "../api/client";
import type { Health } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { NAV_GROUPS } from "../navigation";
import { RoleSwitcher } from "./RoleSwitcher";

const HEALTH_TONE: Record<string, string> = { ok: "p-good", degraded: "p-warn", down: "p-bad" };

function HealthPill() {
  const health = useQuery({
    queryKey: ["health"],
    queryFn: () => api<Health>("/api/health"),
    refetchInterval: 30_000,
  });
  if (health.isError) return <span className="pill p-bad" title="Backend unreachable">API down</span>;
  if (!health.data) return <span className="pill p-mute">checking…</span>;
  const title = Object.entries(health.data.components)
    .map(([k, v]) => `${k}: ${v.status}${v.detail ? ` (${v.detail})` : ""}`)
    .join("\n");
  return (
    <span className={`pill ${HEALTH_TONE[health.data.status]}`} title={title}>
      system {health.data.status}
    </span>
  );
}

export function Layout() {
  const { can, signOut } = useAuth();
  return (
    <>
      <header className="topbar">
        <div className="brand">
          <b>MRM Governance MIS</b>
          <span>Model risk inventory, validation &amp; monitoring</span>
        </div>
        <div className="spacer" />
        <div className="controls">
          <HealthPill />
          <RoleSwitcher compact />
          <button className="btn sm" onClick={signOut}>Sign out</button>
        </div>
      </header>
      <div className="layout">
        <nav className="rail" aria-label="Main">
          {NAV_GROUPS.map((group) => {
            const items = group.items.filter((i) => !i.permission || can(i.permission));
            if (!items.length) return null;
            return (
              <div key={group.label}>
                <div className="group-label">{group.label}</div>
                {items.map((item) => (
                  <NavLink key={item.path} to={item.path} end={item.path === "/"}>
                    {item.label}
                  </NavLink>
                ))}
              </div>
            );
          })}
        </nav>
        <main className="stage">
          <Outlet />
        </main>
      </div>
    </>
  );
}
