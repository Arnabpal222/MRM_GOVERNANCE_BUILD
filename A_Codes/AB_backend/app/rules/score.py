"""R8 Governance score (BRD §57). Explainable: every component returns its inputs and any
missing information, and not-applicable components are dropped with weights rescaled to 100%."""
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal


@dataclass
class Component:
    key: str
    label: str
    weight: Decimal  # configured weight, before rescaling
    score: Decimal | None  # None = not applicable
    inputs: dict = field(default_factory=dict)
    explanation: str = ""
    missing: list[str] = field(default_factory=list)
    effective_weight: Decimal | None = None


@dataclass
class ScoreResult:
    overall: Decimal | None
    components: list[Component]
    reason: str | None = None  # why there is no score at all


def _clamp(v: Decimal) -> Decimal:
    return max(Decimal(0), min(Decimal(100), v))


def _q(v: Decimal) -> Decimal:
    return v.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)


def validation_currency(has_validation: bool, days_overdue: int, penalty_per_day: Decimal, weight: Decimal) -> Component:
    c = Component("validation_currency", "Validation currency", weight, None,
                  inputs={"days_overdue": days_overdue, "penalty_per_day": str(penalty_per_day)})
    if not has_validation:
        c.explanation = "Not applicable before the first validation."
        return c
    c.score = _clamp(Decimal(100) - penalty_per_day * max(0, days_overdue))
    c.explanation = ("Revalidation not overdue." if days_overdue <= 0
                     else f"100 − {penalty_per_day} × {days_overdue} days overdue.")
    return c


def issue_remediation(open_by_severity: dict[str, int], past_due: int, penalties: dict[str, Decimal],
                      past_due_penalty: Decimal, weight: Decimal) -> Component:
    deduction = sum(penalties.get(sev, Decimal(0)) * n for sev, n in open_by_severity.items()) + past_due_penalty * past_due
    parts = [f"{n} open {sev} × {penalties.get(sev, 0)}" for sev, n in open_by_severity.items() if n]
    if past_due:
        parts.append(f"{past_due} past due × {past_due_penalty}")
    return Component("issue_remediation", "Issue remediation", weight, _clamp(Decimal(100) - deduction),
                     inputs={"open_by_severity": open_by_severity, "past_due": past_due},
                     explanation="100 − (" + " + ".join(parts) + ")" if parts else "No open findings.")


def mrc_compliance(latest_decision: str | None, open_conditions: bool, mrc_required: bool,
                   conditional_score: Decimal, weight: Decimal) -> Component:
    c = Component("mrc_compliance", "MRC compliance", weight, None,
                  inputs={"latest_decision": latest_decision, "open_conditions": open_conditions,
                          "mrc_required": mrc_required})
    if latest_decision is None:
        if mrc_required:
            c.score, c.explanation = Decimal(0), "No MRC decision recorded, but one is required at this phase."
        else:
            c.explanation = "Not applicable: no MRC decision is required yet."
        return c
    if latest_decision == "Approved":
        c.score, c.explanation = Decimal(100), "Latest decision Approved."
    elif latest_decision == "Conditional":
        if open_conditions:
            c.score, c.explanation = conditional_score, "Latest decision Conditional with open conditions."
        else:
            c.score, c.explanation = Decimal(100), "Latest decision Conditional; all conditions met."
    else:
        c.score, c.explanation = Decimal(0), f"Latest decision {latest_decision}."
    return c


def not_available(key: str, label: str, weight: Decimal, reason: str, missing: list[str]) -> Component:
    return Component(key, label, weight, None, explanation=reason, missing=missing)


def combine(components: list[Component]) -> ScoreResult:
    """Weighted average of applicable components, weights rescaled to sum to 100%."""
    applicable = [c for c in components if c.score is not None and c.weight > 0]
    total = sum((c.weight for c in applicable), Decimal(0))
    if not applicable or total == 0:
        return ScoreResult(None, components, reason="No score component is applicable yet.")
    overall = Decimal(0)
    for c in applicable:
        c.effective_weight = _q(c.weight / total * 100)
        overall += c.score * c.weight / total
    for c in components:
        if c.score is not None:
            c.score = _q(c.score)
    return ScoreResult(_q(overall), components)
