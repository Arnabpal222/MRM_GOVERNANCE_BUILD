"""Template registry — the single source of truth for structured ingestion (BRD §71).

Blank template downloads, import validation and the seed generator all read these specs.
Allowed values that are configurable point at a policy setting ("policy:<key>") instead of
being listed here.
"""
from dataclasses import dataclass, field

from app.auth.roles import Role
from app.rules.policy_values import VALUE_TYPES


@dataclass(frozen=True)
class Column:
    name: str
    type: str = "text"  # text | int | decimal | date | yn | list
    required: bool = False
    condition: str | None = None  # human-readable conditional requirement, enforced by the service rules
    allowed: tuple[str, ...] | str | None = None  # static values or "policy:<key>"
    fk: str | None = None  # app_user | model | validation
    same_file_ok: bool = False  # the reference may point at a key defined elsewhere in the same file
    pattern: str | None = None
    max_length: int | None = None
    description: str = ""
    example: str = ""


@dataclass(frozen=True)
class Template:
    template_id: str
    name: str
    format: str  # xlsx | csv
    target: str
    key: str
    order: int  # load order; lower loads first (REQ-IMP-04)
    columns: tuple[Column, ...] = ()
    depends_on: tuple[str, ...] = ()
    available: bool = True
    phase: str | None = None  # when not yet available
    description: str = ""
    channel: str = "import"  # import: Import Centre | documents: manifest used inside a Document Centre upload

    @property
    def required_columns(self) -> list[str]:
        return [c.name for c in self.columns if c.required]

    def column(self, name: str) -> Column | None:
        return next((c for c in self.columns if c.name == name), None)


_Q = dict(type="int", required=True, allowed=("1", "2", "3"))

TEMPLATES: tuple[Template, ...] = (
    Template("T12", "Policy settings", "xlsx", "policy_setting", "setting_key", 1, description=(
        "Configuration that drives every business rule. Loaded first."), columns=(
        Column("setting_key", required=True, pattern=r"^[a-z][a-z0-9_]*$", max_length=80, example="reval_lead_days"),
        Column("value", required=True, description="Parsed according to value_type", example="60"),
        Column("value_type", required=True, allowed=VALUE_TYPES, example="integer"),
        Column("category", max_length=40, example="Revalidation"),
        Column("description", example="Days before due date a model shows in Revalidation"),
    )),
    Template("T01", "Users and roles", "xlsx", "app_user", "user_id", 2, depends_on=("T12",), columns=(
        Column("user_id", required=True, pattern=r"^U-\d{3,}$", example="U-014"),
        Column("full_name", required=True, max_length=120, example="Sarah Patel"),
        Column("email", required=True, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$", example="s.patel@demo-bank.example"),
        Column("role", type="list", required=True, allowed=tuple(r.value for r in Role),
               description="One or more roles separated by ';'", example="Validator"),
        Column("business_line", max_length=120, example="Enterprise Risk"),
        Column("active", type="yn", required=True, example="Y"),
    )),
    Template("T02", "Model inventory and tiering", "xlsx", "model", "model_id", 3, depends_on=("T01",), columns=(
        Column("model_id", required=True, pattern=r"^M-\d{4,}$", example="M-0012"),
        Column("model_name", required=True, max_length=100, example="Wholesale PD Model"),
        Column("model_type", required=True, allowed="policy:model_types", example="Credit Risk"),
        Column("model_subtype", required=True, max_length=60, example="PD"),
        Column("purpose", required=True, max_length=500, example="12-month PD for wholesale commercial exposures"),
        Column("business_line", required=True, max_length=120, example="Commercial Banking"),
        Column("model_family", max_length=120, example="Wholesale credit"),
        Column("owner_id", required=True, fk="app_user", example="U-003"),
        Column("developer_id", required=True, fk="app_user", example="U-021"),
        Column("validator_id", fk="app_user", condition="Required from the Validation phase on; must differ from owner and developer",
               example="U-014"),
        Column("lifecycle_phase", required=True, allowed="policy:lifecycle_phases", example="Monitoring"),
        Column("version", required=True, max_length=40, example="v3.1"),
        Column("go_live_date", type="date", condition="Required from the Monitoring phase on", example="2024-02-15"),
        Column("revalidation_frequency", allowed="policy:revalidation_frequencies",
               condition="Required from the Monitoring phase on", example="Annual"),
        Column("last_validation_date", type="date", condition="Required from the Monitoring phase on; not in the future",
               example="2025-11-15"),
        Column("q_materiality", **_Q, description="How large is the financial exposure the model drives? 1–3", example="3"),
        Column("q_complexity", **_Q, description="How complex is the method, data or components? 1–3", example="2"),
        Column("q_reliance", **_Q, description="How much do decisions rely on the output? 1–3", example="3"),
        Column("q_regulatory_use", **_Q, description="Is it used in regulatory submissions? 1–3", example="3"),
        Column("successor_model_id", fk="model", same_file_ok=True, condition="Retirement phase only; linked after all rows load",
               example=""),
        Column("legacy_sod_exception", type="yn",
               description="System seed only: loads a pre-existing segregation-of-duties conflict as a flagged exception",
               example="N"),
    )),
    Template("T03", "Validation history", "xlsx", "validation", "validation_id", 4, depends_on=("T02",), columns=(
        Column("validation_id", required=True, pattern=r"^V-\d{4,}$", example="V-0412"),
        Column("model_id", required=True, fk="model", example="M-0012"),
        Column("validation_type", required=True, allowed="policy:validation_types", example="Periodic"),
        Column("validator_id", required=True, fk="app_user", condition="Must differ from the model owner and developer",
               example="U-014"),
        Column("start_date", type="date", required=True, example="2025-10-01"),
        Column("completion_date", type="date", condition="Required unless outcome is In Progress; not before start_date",
               example="2025-11-15"),
        Column("outcome", required=True, allowed="policy:validation_outcomes", example="Conditional"),
        Column("summary", example=""),
        Column("recommendations", example=""),
    )),
    Template("T04", "Findings", "xlsx", "finding", "finding_id", 5, depends_on=("T02",), columns=(
        Column("finding_id", required=True, pattern=r"^F-\d{4,}$", example="F-0001"),
        Column("model_id", required=True, fk="model", example="M-0012"),
        Column("validation_id", fk="validation", example="V-0412"),
        Column("title", required=True, max_length=120, example="CRE obligor data gap"),
        Column("description", required=True, example="14% of obligor financial statements missing"),
        Column("severity", required=True, allowed="policy:finding_severities", example="Critical"),
        Column("category", required=True, allowed="policy:finding_categories", example="Data"),
        Column("status", required=True, allowed="policy:finding_statuses", example="Open"),
        Column("owner_id", required=True, fk="app_user", example="U-003"),
        Column("raised_date", type="date", required=True, example="2025-11-15"),
        Column("due_date", type="date", required=True, condition="Not before raised_date", example="2026-06-30"),
        Column("closed_date", type="date", condition="Required when the status is closed", example=""),
        Column("root_cause", example=""),
        Column("management_response", example=""),
        Column("remediation_action", example=""),
    )),
    Template("T05", "Approvals and MRC decisions", "xlsx", "approval", "approval_id", 6, depends_on=("T02",), columns=(
        Column("approval_id", required=True, pattern=r"^A-\d{4,}$", example="A-0231"),
        Column("model_id", required=True, fk="model", example="M-0071"),
        Column("decision_date", type="date", required=True, example="2026-02-20"),
        Column("forum", required=True, allowed="policy:approval_forums", example="MRC"),
        Column("decision_type", required=True, allowed="policy:approval_decision_types", example="Pre-implementation"),
        Column("decision", required=True, allowed="policy:approval_decisions", example="Conditional"),
        Column("conditions", condition="Required if decision is Conditional", example="Go-live blocked until F-0017 closes"),
        Column("condition_due_date", type="date", condition="Required if decision is Conditional", example="2026-05-15"),
        Column("condition_status", allowed=("Open", "Met"), condition="Required if decision is Conditional", example="Open"),
    )),
    # Registered for completeness; they become available with the phase that adds their tables.
    Template("T06", "CDEs and DQ rules", "xlsx", "cde, dq_rule", "dq_rule_id", 7, available=False, phase="Phase 7"),
    Template("T07", "KPI definitions", "xlsx", "kpi", "kpi_id", 8, available=False, phase="Phase 6"),
    Template("T08", "KPI and backtesting results", "csv", "kpi_result", "kpi_id", 9, available=False, phase="Phase 6"),
    Template("T09", "Performance curves", "csv", "performance_point", "model_id", 10, available=False, phase="Phase 6"),
    Template("T10", "DQ rule results", "csv", "dq_result", "run_id", 11, available=False, phase="Phase 7"),
    Template("T11", "Documents", "upload", "document", "document_id", 12, available=False, phase="Phase 4 (Document Centre)"),
    Template("T13", "Monitoring plan", "xlsx", "monitoring_plan", "monitoring_plan_id", 13, available=False, phase="Phase 6"),
    Template("T14", "Monitoring metrics", "xlsx", "monitoring_metric", "metric_id", 14, available=False, phase="Phase 6"),
    Template("T15", "Monitoring results", "csv", "monitoring_result", "monitoring_run_id", 15, available=False, phase="Phase 6"),
    Template("T16", "Monitoring breaches", "xlsx", "monitoring_breach", "breach_id", 16, available=False, phase="Phase 6"),
    Template("T17", "Document manifest", "xlsx", "document", "relative_path", 17, channel="documents", description=(
        "Include in a Document Centre upload (named manifest.xlsx/.csv or T17_*). Overrides folder and file-name "
        "classification (BRD §33 Method D)."), columns=(
        Column("relative_path", required=True, description="Path of the file inside the upload, e.g. M-0012/Validation/VR.pdf",
               example="M-0012/Validation/Validation_Report_2026.pdf"),
        Column("model_id", required=True, fk="model", example="M-0012"),
        Column("document_type", required=True, allowed="policy:document_types", example="Validation Report"),
        Column("version", pattern=r"^\d+(\.\d+)?$", example="1.0"),
        Column("effective_date", type="date", example="2026-09-15"),
        Column("title", max_length=255, example="Validation Report 2026"),
        Column("confidentiality", allowed="policy:document_confidentiality_levels", example="Confidential"),
    )),
    Template("T18", "Folder / package manifest", "xlsx", "document_folder", "relative_path", 18, channel="documents",
             description="Maps folders of an upload to models (BRD §33 Method B/D).", columns=(
        Column("relative_path", required=True, example="Credit_Risk/M-0012"),
        Column("model_id", fk="model", example="M-0012"),
        Column("folder_type", max_length=60, example="Model evidence"),
        Column("description", example="All governance evidence for the Wholesale PD Model"),
    )),
)

_BY_ID = {t.template_id: t for t in TEMPLATES}


def get_template(template_id: str) -> Template | None:
    return _BY_ID.get(template_id)


def available_templates(channel: str = "import") -> list[Template]:
    return sorted((t for t in TEMPLATES if t.available and t.channel == channel), key=lambda t: t.order)
