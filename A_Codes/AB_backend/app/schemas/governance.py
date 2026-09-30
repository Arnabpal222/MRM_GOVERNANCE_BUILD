"""API schemas for model inventory and governance records (Phase 2)."""
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --- models -----------------------------------------------------------------------------

class TieringAnswers(BaseModel):
    q_materiality: int = Field(ge=1, le=3)
    q_complexity: int = Field(ge=1, le=3)
    q_reliance: int = Field(ge=1, le=3)
    q_regulatory_use: int = Field(ge=1, le=3)


class ModelWrite(BaseModel):
    model_name: str
    model_type: str
    model_subtype: str
    purpose: str
    business_line: str
    model_family: str | None = None
    owner_id: str
    developer_id: str
    validator_id: str | None = None
    lifecycle_phase: str
    version: str
    go_live_date: date | None = None
    revalidation_frequency: str | None = None
    last_validation_date: date | None = None
    q_materiality: int
    q_complexity: int
    q_reliance: int
    q_regulatory_use: int


class ModelCreate(ModelWrite):
    model_id: str | None = Field(default=None, pattern=r"^M-\d{4,}$")
    reason: str | None = None


class ModelUpdate(ModelWrite):
    row_version: int
    reason: str | None = None


class TransitionRequest(BaseModel):
    to_phase: str
    reason: str | None = None
    row_version: int


class TierOverrideRequest(BaseModel):
    tier: str | None  # None removes the override
    reason: str
    row_version: int


class RelationshipCreate(BaseModel):
    related_model_id: str
    relationship_type: str


class ScoreComponentOut(BaseModel):
    key: str
    label: str
    weight: Decimal
    effective_weight: Decimal | None
    score: Decimal | None
    explanation: str
    inputs: dict[str, Any]
    missing: list[str]


class ScoreOut(BaseModel):
    overall: Decimal | None
    reason: str | None
    components: list[ScoreComponentOut]
    calculated_at: datetime


class ModelStateOut(BaseModel):
    next_due: date | None
    days_to_due: int | None
    revalidation_status: str | None
    displayed_column: str
    open_findings: int
    open_by_severity: dict[str, int]
    overdue_findings: int
    critical_overdue: int
    latest_decision: str | None
    latest_decision_date: date | None
    open_conditions: int
    sod_breach: str | None
    score: Decimal | None


class ModelSummaryOut(ORMModel):
    model_id: str
    model_name: str
    model_type: str
    model_subtype: str
    business_line: str
    owner_id: str
    validator_id: str | None
    lifecycle_phase: str
    version: str
    effective_tier: str
    calculated_tier: str
    tier_score: int
    last_validation_date: date | None
    state: ModelStateOut


class TieringOut(ORMModel):
    q_materiality: int
    q_complexity: int
    q_reliance: int
    q_regulatory_use: int
    override_tier: str | None
    override_reason: str | None
    override_by: str | None
    override_at: datetime | None


class ModelOut(ORMModel):
    model_id: str
    model_name: str
    model_type: str
    model_subtype: str
    purpose: str
    business_line: str
    model_family: str | None
    owner_id: str
    developer_id: str
    validator_id: str | None
    lifecycle_phase: str
    version: str
    go_live_date: date | None
    revalidation_frequency: str | None
    last_validation_date: date | None
    tier_score: int
    calculated_tier: str
    effective_tier: str
    legacy_sod_exception: bool
    tiering: TieringOut
    row_version: int
    created_at: datetime | None
    updated_at: datetime | None


class PhaseHistoryOut(ORMModel):
    from_phase: str | None
    to_phase: str
    reason: str | None
    user_id: str | None
    changed_at: datetime


class TierOverrideOut(ORMModel):
    calculated_tier: str
    previous_tier: str
    new_tier: str
    reason: str
    user_id: str
    created_at: datetime


class VersionOut(ORMModel):
    version: str
    change_reason: str | None
    user_id: str | None
    recorded_at: datetime


class RelationshipOut(BaseModel):
    relationship: str
    model_id: str
    model_name: str | None = None


# --- validations ----------------------------------------------------------------------------

class ValidationWrite(BaseModel):
    validation_type: str
    validator_id: str
    start_date: date
    completion_date: date | None = None
    outcome: str
    summary: str | None = None
    recommendations: str | None = None
    report_document_id: str | None = None


class ValidationCreate(ValidationWrite):
    model_id: str
    validation_id: str | None = Field(default=None, pattern=r"^V-\d{4,}$")


class ValidationUpdate(ValidationWrite):
    row_version: int


class ValidationOut(ORMModel):
    validation_id: str
    model_id: str
    validation_type: str
    validator_id: str
    start_date: date
    completion_date: date | None
    outcome: str
    summary: str | None
    recommendations: str | None
    report_document_id: str | None
    source: str
    row_version: int


# --- findings -------------------------------------------------------------------------------

class FindingWrite(BaseModel):
    validation_id: str | None = None
    title: str
    description: str
    severity: str
    category: str
    status: str = "Open"
    owner_id: str | None = None
    raised_date: date | None = None
    due_date: date
    closed_date: date | None = None
    evidence: str | None = None
    root_cause: str | None = None
    management_response: str | None = None
    remediation_action: str | None = None


class FindingCreate(FindingWrite):
    model_id: str
    finding_id: str | None = Field(default=None, pattern=r"^F-\d{4,}$")


class FindingUpdate(BaseModel):
    """Partial update: only the fields sent are changed."""
    row_version: int
    reason: str | None = None
    title: str | None = None
    description: str | None = None
    severity: str | None = None
    category: str | None = None
    status: str | None = None
    owner_id: str | None = None
    due_date: date | None = None
    closed_date: date | None = None
    evidence: str | None = None
    root_cause: str | None = None
    management_response: str | None = None
    remediation_action: str | None = None


class FindingOut(ORMModel):
    finding_id: str
    model_id: str
    validation_id: str | None
    title: str
    description: str
    severity: str
    category: str
    status: str
    owner_id: str
    raised_date: date
    due_date: date
    closed_date: date | None
    source: str
    evidence: str | None
    root_cause: str | None
    management_response: str | None
    remediation_action: str | None
    row_version: int
    days_open: int = 0
    days_overdue: int = 0
    is_overdue: bool = False


# --- approvals ------------------------------------------------------------------------------

class ApprovalWrite(BaseModel):
    decision_date: date
    forum: str
    decision_type: str
    decision: str
    conditions: str | None = None
    condition_due_date: date | None = None
    condition_status: str | None = None
    supporting_document_id: str | None = None


class ApprovalCreate(ApprovalWrite):
    model_id: str
    approval_id: str | None = Field(default=None, pattern=r"^A-\d{4,}$")


class ApprovalUpdate(BaseModel):
    row_version: int
    reason: str | None = None
    condition_status: str | None = None
    conditions: str | None = None
    condition_due_date: date | None = None


class ApprovalOut(ORMModel):
    approval_id: str
    model_id: str
    decision_date: date
    forum: str
    decision_type: str
    decision: str
    conditions: str | None
    condition_due_date: date | None
    condition_status: str | None
    supporting_document_id: str | None
    recorded_by: str | None
    row_version: int


# --- composite ------------------------------------------------------------------------------

class Model360Out(BaseModel):
    model: ModelOut
    state: ModelStateOut
    score: ScoreOut
    phase_history: list[PhaseHistoryOut]
    tier_overrides: list[TierOverrideOut]
    versions: list[VersionOut]
    relationships: list[RelationshipOut]
    validations: list[ValidationOut]
    findings: list[FindingOut]
    approvals: list[ApprovalOut]
    user_names: dict[str, str]


class TierPreviewOut(BaseModel):
    tier_score: int
    tier: str
    thresholds: dict[str, int]


class ModelMetaOut(BaseModel):
    """Allowed values for forms and filters — all from policy settings."""
    model_types: list[str]
    lifecycle_phases: list[str]
    displayed_columns: list[str]
    revalidation_frequencies: list[str]
    revalidation_statuses: list[str]
    tiers: list[str]
    business_lines: list[str]
    validation_types: list[str]
    validation_outcomes: list[str]
    finding_severities: list[str]
    finding_categories: list[str]
    finding_statuses: list[str]
    finding_open_statuses: list[str]
    approval_forums: list[str]
    approval_decision_types: list[str]
    approval_decisions: list[str]
    relationship_types: list[str]
    tiering_questions: dict[str, str]
    users: list[dict[str, Any]]
