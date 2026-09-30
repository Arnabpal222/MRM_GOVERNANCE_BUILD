// Presentation-only colour mapping for status values. No business rules here:
// every status shown is calculated by the server.

const TONES: Record<string, string> = {
  High: "p-bad", Medium: "p-warn", Low: "p-good",
  Critical: "p-bad",
  Overdue: "p-bad", "Due Soon": "p-warn", Scheduled: "p-info",
  Approved: "p-good", Conditional: "p-warn", Rejected: "p-bad", "In Progress": "p-info",
  Open: "p-warn", Closed: "p-mute", Deferred: "p-mute", "Accepted Risk": "p-mute", Met: "p-good",
};

export function Pill({ value, tone }: { value: string | null | undefined; tone?: string }) {
  if (!value) return <span style={{ color: "var(--faint)" }}>—</span>;
  return <span className={`pill ${tone ?? TONES[value] ?? "p-mute"}`}>{value}</span>;
}

export function SeverityPill({ value }: { value: string }) {
  return <Pill value={value} tone={value === "Low" ? "p-info" : undefined} />;
}

export function ScoreValue({ value }: { value: string | null }) {
  if (value === null) return <span style={{ color: "var(--faint)" }}>n/a</span>;
  const n = Number(value);
  const colour = n >= 80 ? "var(--good)" : n >= 60 ? "var(--warn)" : "var(--bad)";
  return <span className="mono" style={{ color: colour, fontWeight: 600 }}>{Number(value).toFixed(1)}</span>;
}

export function DaysToDue({ days }: { days: number | null }) {
  if (days === null) return <span style={{ color: "var(--faint)" }}>—</span>;
  if (days < 0) return <span className="mono" style={{ color: "var(--bad)" }}>{-days}d overdue</span>;
  return <span className="mono">{days}d</span>;
}
