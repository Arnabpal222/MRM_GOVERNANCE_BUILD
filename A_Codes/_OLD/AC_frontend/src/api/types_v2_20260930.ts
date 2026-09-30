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

// --- Phase 2: model inventory and governance records (mirrors app/schemas/governance.py) ---

export interface ModelState {
  next_due: string | null;
  days_to_due: number | null;
  revalidation_status: string | null;
  displayed_column: string;
  open_findings: number;
  open_by_severity: Record<string, number>;
  overdue_findings: number;
  critical_overdue: number;
  latest_decision: string | null;
  latest_decision_date: string | null;
  open_conditions: number;
  sod_breach: string | null;
  score: string | null;
}

export interface ModelSummary {
  model_id: string;
  model_name: string;
  model_type: string;
  model_subtype: string;
  business_line: string;
  owner_id: string;
  validator_id: string | null;
  lifecycle_phase: string;
  version: string;
  effective_tier: string;
  calculated_tier: string;
  tier_score: number;
  last_validation_date: string | null;
  state: ModelState;
}

export interface Tiering {
  q_materiality: number;
  q_complexity: number;
  q_reliance: number;
  q_regulatory_use: number;
  override_tier: string | null;
  override_reason: string | null;
  override_by: string | null;
  override_at: string | null;
}

export interface ModelRecord {
  model_id: string;
  model_name: string;
  model_type: string;
  model_subtype: string;
  purpose: string;
  business_line: string;
  model_family: string | null;
  owner_id: string;
  developer_id: string;
  validator_id: string | null;
  lifecycle_phase: string;
  version: string;
  go_live_date: string | null;
  revalidation_frequency: string | null;
  last_validation_date: string | null;
  tier_score: number;
  calculated_tier: string;
  effective_tier: string;
  legacy_sod_exception: boolean;
  tiering: Tiering;
  row_version: number;
}

export interface ScoreComponent {
  key: string;
  label: string;
  weight: string;
  effective_weight: string | null;
  score: string | null;
  explanation: string;
  inputs: Record<string, unknown>;
  missing: string[];
}

export interface Score {
  overall: string | null;
  reason: string | null;
  components: ScoreComponent[];
  calculated_at: string;
}

export interface Validation {
  validation_id: string;
  model_id: string;
  validation_type: string;
  validator_id: string;
  start_date: string;
  completion_date: string | null;
  outcome: string;
  summary: string | null;
  recommendations: string | null;
  report_document_id: string | null;
  source: string;
  row_version: number;
}

export interface Finding {
  finding_id: string;
  model_id: string;
  validation_id: string | null;
  title: string;
  description: string;
  severity: string;
  category: string;
  status: string;
  owner_id: string;
  raised_date: string;
  due_date: string;
  closed_date: string | null;
  source: string;
  evidence: string | null;
  root_cause: string | null;
  management_response: string | null;
  remediation_action: string | null;
  row_version: number;
  days_open: number;
  days_overdue: number;
  is_overdue: boolean;
}

export interface Approval {
  approval_id: string;
  model_id: string;
  decision_date: string;
  forum: string;
  decision_type: string;
  decision: string;
  conditions: string | null;
  condition_due_date: string | null;
  condition_status: string | null;
  supporting_document_id: string | null;
  recorded_by: string | null;
  row_version: number;
}

export interface Model360 {
  model: ModelRecord;
  state: ModelState;
  score: Score;
  phase_history: { from_phase: string | null; to_phase: string; reason: string | null; user_id: string | null; changed_at: string }[];
  tier_overrides: { calculated_tier: string; previous_tier: string; new_tier: string; reason: string; user_id: string; created_at: string }[];
  versions: { version: string; change_reason: string | null; user_id: string | null; recorded_at: string }[];
  relationships: { relationship: string; model_id: string; model_name: string | null }[];
  validations: Validation[];
  findings: Finding[];
  approvals: Approval[];
  user_names: Record<string, string>;
}

export interface ModelMeta {
  model_types: string[];
  lifecycle_phases: string[];
  displayed_columns: string[];
  revalidation_frequencies: string[];
  revalidation_statuses: string[];
  tiers: string[];
  business_lines: string[];
  validation_types: string[];
  validation_outcomes: string[];
  finding_severities: string[];
  finding_categories: string[];
  finding_statuses: string[];
  finding_open_statuses: string[];
  approval_forums: string[];
  approval_decision_types: string[];
  approval_decisions: string[];
  relationship_types: string[];
  tiering_questions: Record<string, string>;
  users: { user_id: string; full_name: string; roles: string[]; active: boolean }[];
}
