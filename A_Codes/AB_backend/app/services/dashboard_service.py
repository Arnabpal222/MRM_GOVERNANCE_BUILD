"""Command Center (BRD §55.1, §56): portfolio tiles, distributions and generated insights.

Every figure comes from the same portfolio calculation the Operations Board and Model 360 use
(governance_view), so tiles tie out to the lists they drill into. Nothing is hard-coded.
"""
from collections import Counter
from dataclasses import asdict
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.clock import today
from app.models import Approval, Finding, Validation
from app.rules import governance_rules, insights, revalidation, tiering
from app.documents import service as doc_service
from app.services import governance_view
from app.services.policy_access import Policy


def _pct(part: int, whole: int) -> float:
    return round(100 * part / whole, 1) if whole else 0.0


def summary(db: Session) -> dict:
    policy = Policy.load(db)
    on = today()
    rows = governance_view.portfolio(db)
    models = {m.model_id: m for m, _ in rows}
    retired = policy.retirement_phase
    active = [(m, s) for m, s in rows if m.lifecycle_phase != retired]
    production = set(policy.list("production_phases"))

    # --- tiles --------------------------------------------------------------------------------
    scored = [s.score.overall for _, s in rows if s.score.overall is not None]
    # completeness among active models that have required documents in their phase
    doc_required = [(m, s) for m, s in active if doc_service.required_for(policy, m.lifecycle_phase)]
    doc_complete = sum(1 for _, s in doc_required if not s.missing_documents)
    tiles = {
        "total_models": len(rows),
        "active_models": len(active),
        "in_production": sum(1 for m, _ in rows if m.lifecycle_phase in production),
        "high_tier": sum(1 for m, _ in rows if m.effective_tier == "High"),
        "revalidation_queue": sum(1 for _, s in rows if s.displayed_column == revalidation.REVALIDATION_COLUMN),
        "revalidation_overdue": sum(1 for _, s in rows if s.revalidation_status == revalidation.OVERDUE),
        "open_findings": sum(s.open_findings for _, s in rows),
        "overdue_findings": sum(s.overdue_findings for _, s in rows),
        "critical_overdue_findings": sum(s.critical_overdue for _, s in rows),
        "models_with_open_conditions": sum(1 for _, s in rows if s.open_conditions),
        "sod_breaches": sum(1 for _, s in rows if s.sod_breach),
        "document_completeness_pct": _pct(doc_complete, len(doc_required)),
        "models_with_document_gaps": sum(1 for _, s in rows if s.missing_documents),
        "portfolio_score": float(round(sum(scored, Decimal(0)) / len(scored), 1)) if scored else None,
        "scored_models": len(scored),
    }

    # --- distributions (ordered by policy, so charts are stable) ---------------------------------
    def dist(values: list[str], order: list[str]) -> list[dict]:
        c = Counter(values)
        keys = [k for k in order if k in c] + sorted(k for k in c if k not in order)
        return [{"key": k, "count": c[k], "pct": _pct(c[k], len(values))} for k in keys]

    meta_columns = [*policy.phases[: policy.phases.index("Monitoring") + 1], revalidation.REVALIDATION_COLUMN,
                    *policy.phases[policy.phases.index("Monitoring") + 1:]]
    severities = policy.list("finding_severities")
    open_by_sev = Counter()
    for _, s in rows:
        open_by_sev.update({k: v for k, v in s.open_by_severity.items() if v})
    bands = Counter("below_60" if v < 60 else "60_80" if v < 80 else "80_plus" for v in scored)
    distributions = {
        "tier": dist([m.effective_tier for m, _ in rows], list(tiering.TIERS)),
        "model_type": dist([m.model_type for m, _ in rows], policy.list("model_types")),
        "stage": dist([s.displayed_column for _, s in rows], meta_columns),
        "business_line": dist([m.business_line for m, _ in rows], []),
        "revalidation_status": dist([s.revalidation_status for _, s in rows if s.revalidation_status],
                                    [revalidation.OVERDUE, revalidation.DUE_SOON, revalidation.SCHEDULED]),
        "open_findings_by_severity": [{"key": k, "count": open_by_sev.get(k, 0),
                                       "pct": _pct(open_by_sev.get(k, 0), tiles["open_findings"])} for k in severities],
        "score_band": [{"key": k, "count": bands.get(k, 0), "pct": _pct(bands.get(k, 0), len(scored))}
                       for k in ("below_60", "60_80", "80_plus")],
    }

    # --- revalidation timeline: the models in the Revalidation column, most urgent first ----------
    timeline = sorted(
        ({"model_id": m.model_id, "model_name": m.model_name, "tier": m.effective_tier, "owner_id": m.owner_id,
          "next_due": s.next_due.isoformat() if s.next_due else None, "days_to_due": s.days_to_due,
          "status": s.revalidation_status, "last_validation_date": m.last_validation_date.isoformat()
          if m.last_validation_date else None, "latest_decision": s.latest_decision}
         for m, s in rows if s.displayed_column == revalidation.REVALIDATION_COLUMN),
        key=lambda x: x["days_to_due"] if x["days_to_due"] is not None else 10**6)

    # --- insights --------------------------------------------------------------------------------
    open_statuses = policy.list("finding_open_statuses")
    in_progress = {v.model_id: (on - v.start_date).days for v in db.scalars(
        select(Validation).where(Validation.outcome == "In Progress"))}
    conditions: dict[str, list[tuple[str, int]]] = {}
    for a in db.scalars(select(Approval).where(Approval.decision == "Conditional", Approval.condition_status == "Open")):
        if a.condition_due_date and a.condition_due_date < on:
            conditions.setdefault(a.model_id, []).append((a.approval_id, (on - a.condition_due_date).days))
    sla = {t: policy.int(f"validation_sla_days_{t.lower()}") for t in tiering.TIERS}
    facts = [insights.ModelFacts(
        model_id=m.model_id, model_name=m.model_name, tier=m.effective_tier, phase=m.lifecycle_phase,
        days_to_due=s.days_to_due, revalidation_status=s.revalidation_status, sod_breach=s.sod_breach,
        missing_documents=s.missing_documents if m.lifecycle_phase != retired else [],
        open_conditions_overdue=conditions.get(m.model_id, []),
        validation_in_progress_days=in_progress.get(m.model_id), validation_sla_days=sla.get(m.effective_tier),
    ) for m, s in rows]
    finding_facts = []
    for f in db.scalars(select(Finding).where(Finding.status.in_(open_statuses))):
        age = governance_rules.finding_age(f.status, f.raised_date, f.due_date, f.closed_date, on, open_statuses)
        if f.model_id in models:
            finding_facts.append(insights.FindingFacts(f.finding_id, f.model_id, f.title, f.severity,
                                                       age.days_overdue, models[f.model_id].effective_tier))
    all_insights = insights.generate(facts, finding_facts, on, critical_severity=severities[0])
    by_rule = Counter(i.rule for i in all_insights)

    return {
        "as_of": on.isoformat(),
        "calculated_at": datetime.now(UTC).isoformat(),
        "tiles": tiles,
        "distributions": distributions,
        "revalidation_timeline": timeline,
        "insights": [{**asdict(i), "as_of": i.as_of.isoformat()} for i in
                     all_insights[: policy.int("insights_display_limit")]],
        "insight_count": len(all_insights),
        "insight_counts_by_rule": dict(by_rule),
        "pending": {  # shown honestly as not-yet-available instead of invented numbers
            "monitoring": "Monitoring runs, KPI results and breaches arrive with Model Monitoring (Phase 6).",
            "data_quality": "CDE and data-quality health arrive with Data Audit (Phase 7).",
        },
    }
