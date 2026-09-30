"""R9 Governance insights (BRD §56): generated from current data by rules, never a fixed list. Pure functions.

Each insight carries a severity, a message, the model, the source record and a link to the screen
that shows it, so the Command Center can drill down.
"""
from dataclasses import dataclass
from datetime import date

SEVERITY_ORDER = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}


@dataclass(frozen=True)
class Insight:
    severity: str
    rule: str
    message: str
    model_id: str | None
    source: str  # e.g. "finding F-0001", "model M-0078"
    link: str  # frontend route
    as_of: date


@dataclass(frozen=True)
class ModelFacts:
    model_id: str
    model_name: str
    tier: str
    phase: str
    days_to_due: int | None
    revalidation_status: str | None
    sod_breach: str | None
    missing_documents: list[str]
    open_conditions_overdue: list[tuple[str, int]]  # (approval id, days overdue)
    validation_in_progress_days: int | None
    validation_sla_days: int | None


@dataclass(frozen=True)
class FindingFacts:
    finding_id: str
    model_id: str
    title: str
    severity: str
    days_overdue: int
    model_tier: str


def generate(models: list[ModelFacts], findings: list[FindingFacts], today: date,
             critical_severity: str = "Critical") -> list[Insight]:
    out: list[Insight] = []
    for m in models:
        link = f"/models/{m.model_id}"
        if m.sod_breach:
            out.append(Insight("Critical", "sod_breach", f"{m.model_id} {m.model_name}: {m.sod_breach}",
                               m.model_id, f"model {m.model_id}", link, today))
        if m.revalidation_status == "Overdue" and m.days_to_due is not None:
            sev = "Critical" if m.tier == "High" else "High" if m.tier == "Medium" else "Medium"
            out.append(Insight(sev, "revalidation_overdue",
                               f"{m.tier}-tier {m.model_id} {m.model_name} is {-m.days_to_due} days overdue for revalidation.",
                               m.model_id, f"model {m.model_id}", link, today))
        if m.validation_in_progress_days is not None and m.validation_sla_days is not None \
                and m.validation_in_progress_days > m.validation_sla_days:
            out.append(Insight("High" if m.tier == "High" else "Medium", "validation_sla",
                               f"Validation of {m.model_id} has run {m.validation_in_progress_days} days, beyond the "
                               f"{m.validation_sla_days}-day SLA for {m.tier}-tier models.",
                               m.model_id, f"model {m.model_id}", link, today))
        if m.missing_documents and m.tier == "High":
            out.append(Insight("High", "missing_documents",
                               f"High-tier {m.model_id} is missing required documents: {', '.join(m.missing_documents)}.",
                               m.model_id, f"model {m.model_id}", link, today))
        for approval_id, days in m.open_conditions_overdue:
            out.append(Insight("High" if m.tier == "High" else "Medium", "conditions_overdue",
                               f"MRC conditions on {m.model_id} ({approval_id}) are {days} days past their due date.",
                               m.model_id, f"approval {approval_id}", link, today))
    for f in findings:
        if f.severity == critical_severity and f.days_overdue > 0:
            out.append(Insight("Critical" if f.model_tier == "High" else "High", "critical_finding_overdue",
                               f"Critical finding {f.finding_id} on {f.model_id} ({f.title}) is {f.days_overdue} days past due.",
                               f.model_id, f"finding {f.finding_id}", f"/models/{f.model_id}", today))
    # Most severe first, then by rule and model id, so the list is stable and reproducible.
    rule_rank = {r: i for i, r in enumerate(("sod_breach", "critical_finding_overdue", "revalidation_overdue",
                                             "conditions_overdue", "validation_sla", "missing_documents"))}
    return sorted(out, key=lambda i: (SEVERITY_ORDER.get(i.severity, 9), rule_rank.get(i.rule, 9), i.model_id or ""))
