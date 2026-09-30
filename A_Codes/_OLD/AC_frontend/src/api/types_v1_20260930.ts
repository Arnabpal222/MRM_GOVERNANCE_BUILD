// Mirrors backend app/schemas/core.py.

export interface Me {
  user_id: string;
  full_name: string;
  role: string;
  roles: string[];
  permissions: string[];
}

export interface DevUser {
  user_id: string;
  full_name: string;
  roles: string[];
}

export interface User {
  user_id: string;
  full_name: string;
  email: string;
  business_line: string | null;
  active: boolean;
  roles: string[];
  row_version: number;
}

export interface PolicySetting {
  setting_key: string;
  value: string;
  value_type: string;
  category: string | null;
  description: string | null;
  updated_by: string | null;
  updated_at: string | null;
  row_version: number;
}

export interface AuditEvent {
  event_id: number;
  occurred_at: string;
  user_id: string | null;
  role: string | null;
  action: string;
  entity: string;
  entity_id: string;
  model_id: string | null;
  import_batch_id: string | null;
  document_id: string | null;
  reason: string | null;
  before_json: Record<string, unknown> | null;
  after_json: Record<string, unknown> | null;
}

export interface Health {
  status: "ok" | "degraded" | "down";
  components: Record<string, { status: string; detail: string | null }>;
}
