const TOKEN_KEY = "mrm.token";

export function getToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setToken(token: string | null): void {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token);
    else localStorage.removeItem(TOKEN_KEY);
  } catch {
    /* storage unavailable: session lasts for this page only */
  }
}

export class ApiError extends Error {
  status: number;
  details: unknown[];
  constructor(status: number, message: string, details: unknown[] = []) {
    super(message);
    this.status = status;
    this.details = details;
  }
}

export function messageFrom(body: unknown, status: number): string {
  if (body && typeof body === "object" && "detail" in body) {
    const detail = (body as { detail: unknown }).detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      // FastAPI request-validation errors
      return detail.map((d: { loc?: unknown[]; msg?: string }) => `${(d.loc ?? []).slice(1).join(".")}: ${d.msg}`).join("; ");
    }
  }
  return `Request failed (HTTP ${status}).`;
}

export async function api<T>(path: string, init: RequestInit & { json?: unknown } = {}): Promise<T> {
  const headers = new Headers(init.headers);
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  let body = init.body;
  if (init.json !== undefined) {
    headers.set("Content-Type", "application/json");
    body = JSON.stringify(init.json);
  }
  const resp = await fetch(path, { ...init, headers, body });
  const text = await resp.text();
  const parsed = text ? JSON.parse(text) : null;
  if (!resp.ok) {
    if (resp.status === 401) setToken(null);
    throw new ApiError(resp.status, messageFrom(parsed, resp.status), parsed?.errors ?? []);
  }
  return parsed as T;
}

/** Download a file from an authenticated endpoint (templates, error reports). */
export async function downloadFile(path: string, fallbackName: string): Promise<void> {
  const token = getToken();
  const resp = await fetch(path, { headers: token ? { Authorization: `Bearer ${token}` } : {} });
  if (!resp.ok) {
    const text = await resp.text();
    throw new ApiError(resp.status, messageFrom(text ? JSON.parse(text) : null, resp.status));
  }
  const disposition = resp.headers.get("Content-Disposition") ?? "";
  const name = /filename="([^"]+)"/.exec(disposition)?.[1] ?? fallbackName;
  const url = URL.createObjectURL(await resp.blob());
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  URL.revokeObjectURL(url);
}

/** Fetch an authenticated file as a blob URL (for inline previews). Caller revokes it. */
export async function blobUrl(path: string): Promise<string> {
  const token = getToken();
  const resp = await fetch(path, { headers: token ? { Authorization: `Bearer ${token}` } : {} });
  if (!resp.ok) throw new ApiError(resp.status, `Could not load the file (HTTP ${resp.status}).`);
  return URL.createObjectURL(await resp.blob());
}
