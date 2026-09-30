"""Derived governance state per model: revalidation, displayed pipeline column, finding ageing,
MRC status and the explainable governance score. Computed from the database on every read so
a policy change is reflected immediately (REQ-CFG-02)."""
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.clock import today
from app.models import Approval, Finding, Model
from app.documents import service as doc_service
from app.rules import document_rules, governance_rules, model_rules, revalidation, score
from app.services.errors import ValidationFailedError
from app.services.policy_access import Policy


@dataclass
class Aggregates:
    findings: dict[str, list[Finding]] = field(default_factory=lambda: defaultdict(list))
    approvals: dict[str, list[Approval]] = field(default_factory=lambda: defaultdict(list))  # newest first
    document_types: dict[str, set[str]] = field(default_factory=dict)  # active document types per model

    @classmethod
    def load(cls, db: Session, policy: Policy, model_ids: list[str] | None = None) -> "Aggregates":
        agg = cls()
        fq = select(Finding).where(Finding.status.in_(policy.list("finding_open_statuses")))
        aq = select(Approval).order_by(Approval.decision_date.desc(), Approval.approval_id.desc())
        if model_ids is not None:
            fq = fq.where(Finding.model_id.in_(model_ids))
            aq = aq.where(Approval.model_id.in_(model_ids))
        for f in db.scalars(fq):
            agg.findings[f.model_id].append(f)
        for a in db.scalars(aq):
            agg.approvals[a.model_id].append(a)
        agg.document_types = doc_service.present_types(db, model_ids)
        return agg


@dataclass
class ModelState:
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
    missing_documents: list[str]
    score: score.ScoreResult
    calculated_at: datetime


def derive(model: Model, policy: Policy, agg: Aggregates, on: date | None = None) -> ModelState:
    on = on or today()
    open_statuses = policy.list("finding_open_statuses")
    due = revalidation.next_due_date(model.last_validation_date, model.revalidation_frequency, policy.frequency_months)
    reval = revalidation.revalidation_state(due, on, policy.int("due_soon_days"))
    column = revalidation.displayed_column(model.lifecycle_phase, due, on, policy.int("reval_lead_days"))

    severities = policy.list("finding_severities")
    by_sev = {s: 0 for s in severities}
    overdue = critical_overdue = 0
    for f in agg.findings.get(model.model_id, []):
        by_sev[f.severity] = by_sev.get(f.severity, 0) + 1
        a = governance_rules.finding_age(f.status, f.raised_date, f.due_date, f.closed_date, on, open_statuses)
        if a.is_overdue:
            overdue += 1
            if f.severity == severities[0]:
                critical_overdue += 1

    approvals = agg.approvals.get(model.model_id, [])
    latest = approvals[0] if approvals else None
    open_conditions = sum(1 for a in approvals if a.decision == "Conditional" and a.condition_status == "Open")

    return ModelState(
        next_due=due, days_to_due=reval.days_to_due, revalidation_status=reval.status, displayed_column=column,
        open_findings=sum(by_sev.values()), open_by_severity=by_sev, overdue_findings=overdue,
        critical_overdue=critical_overdue,
        latest_decision=latest.decision if latest else None,
        latest_decision_date=latest.decision_date if latest else None, open_conditions=open_conditions,
        sod_breach=model_rules.sod_violation(model.model_id, model.owner_id, model.developer_id, model.validator_id),
        missing_documents=document_rules.completeness(doc_service.required_for(policy, model.lifecycle_phase),
                                                      agg.document_types.get(model.model_id, set())).missing,
        score=_score(model, policy, reval, by_sev, overdue, latest, agg),
        calculated_at=datetime.now(UTC),
    )


def _documentation(model: Model, policy: Policy, agg: Aggregates, weight) -> score.Component:
    """Share of required documents for the phase on file (R8). MDD section checks need AI extraction (Phase 5)."""
    c = document_rules.completeness(doc_service.required_for(policy, model.lifecycle_phase),
                                    agg.document_types.get(model.model_id, set()))
    comp = score.Component("documentation", "Documentation", weight, None,
                           inputs={"required": c.required, "present": c.present, "missing": c.missing},
                           missing=[f"{t} not on file" for t in c.missing] + (
                               ["MDD section completeness (needs document extraction, Phase 5)"] if c.required else []))
    if c.score is None:
        comp.explanation = "Not applicable: no documents are required in this phase."
    else:
        comp.score = Decimal(str(c.score))
        comp.explanation = f"{len(c.present)} of {len(c.required)} required documents on file."
    return comp


def _score(model: Model, policy: Policy, reval: revalidation.RevalidationState, by_sev: dict[str, int],
           overdue: int, latest: Approval | None, agg: Aggregates) -> score.ScoreResult:
    phases = policy.phases
    if model.lifecycle_phase == policy.retirement_phase:
        return score.ScoreResult(None, [], reason="Retired models are not scored.")
    w = policy.score_weights()
    severities = policy.list("finding_severities")
    penalty_keys = {severities[i]: k for i, k in enumerate(("critical", "medium", "low")) if i < len(severities)}
    penalties = {sev: policy.decimal(f"score_penalty_open_{k}") for sev, k in penalty_keys.items()}
    mrc_required = model_rules.at_or_after(phases, model.lifecycle_phase, policy.text("mrc_required_from_phase"))
    latest_open = latest is not None and latest.decision == "Conditional" and latest.condition_status == "Open"
    components = [
        _documentation(model, policy, agg, w["documentation"]),
        score.validation_currency(model.last_validation_date is not None, -(reval.days_to_due or 0),
                                  policy.decimal("score_validation_overdue_penalty_per_day"), w["validation_currency"]),
        score.issue_remediation(by_sev, overdue, penalties, policy.decimal("score_penalty_past_due"),
                                w["issue_remediation"]),
        score.mrc_compliance(latest.decision if latest else None, latest_open, mrc_required,
                             policy.decimal("score_mrc_conditional"), w["mrc_compliance"]),
        score.not_available("monitoring", "Monitoring", w["monitoring"],
                            "Not yet scored: monitoring results arrive with Model Monitoring (Phase 6).",
                            ["Latest KPI results against thresholds"]),
    ]
    return score.combine(components)


# Drill-down filters used by Command Center tiles and insights (Operations Board ?flag=...).
FLAGS = {
    "open_findings": lambda m, s, prod: s.open_findings > 0,
    "overdue_findings": lambda m, s, prod: s.overdue_findings > 0,
    "critical_overdue": lambda m, s, prod: s.critical_overdue > 0,
    "sod_breach": lambda m, s, prod: s.sod_breach is not None,
    "doc_gaps": lambda m, s, prod: bool(s.missing_documents),
    "open_conditions": lambda m, s, prod: s.open_conditions > 0,
    "in_production": lambda m, s, prod: m.lifecycle_phase in prod,
    "scored_below_60": lambda m, s, prod: s.score.overall is not None and s.score.overall < 60,
    "scored_60_80": lambda m, s, prod: s.score.overall is not None and 60 <= s.score.overall < 80,
    "scored_80_plus": lambda m, s, prod: s.score.overall is not None and s.score.overall >= 80,
}


def portfolio(db: Session, *, model_type: str | None = None, tier: str | None = None, phase: str | None = None,
              business_line: str | None = None, column: str | None = None, revalidation_status: str | None = None,
              search: str | None = None, owner_id: str | None = None,
              flag: str | None = None) -> list[tuple[Model, ModelState]]:
    policy = Policy.load(db)
    q = select(Model).order_by(Model.model_id)
    if model_type:
        q = q.where(Model.model_type == model_type)
    if tier:
        q = q.where(Model.effective_tier == tier)
    if phase:
        q = q.where(Model.lifecycle_phase == phase)
    if business_line:
        q = q.where(Model.business_line == business_line)
    if owner_id:
        q = q.where(Model.owner_id == owner_id)
    if search:
        like = f"%{search.strip()}%"
        q = q.where(Model.model_id.ilike(like) | Model.model_name.ilike(like) | Model.model_subtype.ilike(like))
    models = list(db.scalars(q))
    agg = Aggregates.load(db, policy, [m.model_id for m in models] if len(models) < 1000 else None)
    rows = [(m, derive(m, policy, agg)) for m in models]
    if column:
        rows = [r for r in rows if r[1].displayed_column == column]
    if revalidation_status:
        rows = [r for r in rows if r[1].revalidation_status == revalidation_status]
    if flag:
        test = FLAGS.get(flag)
        if test is None:
            raise ValidationFailedError(f"Unknown filter '{flag}'. Allowed: {', '.join(FLAGS)}.")
        production = set(policy.list("production_phases"))
        rows = [r for r in rows if test(r[0], r[1], production)]
    return rows


def model_state(db: Session, model: Model) -> ModelState:
    policy = Policy.load(db)
    return derive(model, policy, Aggregates.load(db, policy, [model.model_id]))
