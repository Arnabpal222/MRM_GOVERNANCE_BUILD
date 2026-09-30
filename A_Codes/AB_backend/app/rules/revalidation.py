"""R2–R4 Revalidation (BRD §10). Pure date arithmetic; policy values are parameters."""
import calendar
from dataclasses import dataclass
from datetime import date

SCHEDULED, DUE_SOON, OVERDUE = "Scheduled", "Due Soon", "Overdue"
REVALIDATION_COLUMN = "Revalidation"


def add_months(d: date, months: int) -> date:
    """Calendar month addition; month-end dates clamp to the last day of the target month."""
    month_index = d.month - 1 + months
    year, month = d.year + month_index // 12, month_index % 12 + 1
    last_day = calendar.monthrange(year, month)[1]
    # A date on the last day of its month stays on the last day (2025-08-31 + 6 → 2026-02-28).
    day = last_day if d.day == calendar.monthrange(d.year, d.month)[1] else min(d.day, last_day)
    return date(year, month, day)


def next_due_date(last_validation: date | None, frequency: str | None, frequency_months: dict[str, int]) -> date | None:
    """R2: last validation date + frequency. No last validation (or no frequency) means no due date."""
    if last_validation is None or not frequency or frequency not in frequency_months:
        return None
    return add_months(last_validation, frequency_months[frequency])


@dataclass(frozen=True)
class RevalidationState:
    due_date: date | None
    days_to_due: int | None
    status: str | None  # Scheduled | Due Soon | Overdue | None when no due date


def revalidation_state(due: date | None, today: date, due_soon_days: int) -> RevalidationState:
    """R4: Overdue if days to due < 0; Due Soon if 0..due_soon_days; else Scheduled."""
    if due is None:
        return RevalidationState(None, None, None)
    days = (due - today).days
    if days < 0:
        status = OVERDUE
    elif days <= due_soon_days:
        status = DUE_SOON
    else:
        status = SCHEDULED
    return RevalidationState(due, days, status)


def displayed_column(phase: str, due: date | None, today: date, lead_days: int, monitoring_phase: str = "Monitoring") -> str:
    """R3: a Monitoring model within the lead time of (or past) its due date shows in Revalidation.

    Revalidation is a governance work state, not a stored lifecycle phase (BRD §8).
    """
    if phase == monitoring_phase and due is not None and (due - today).days <= lead_days:
        return REVALIDATION_COLUMN
    return phase
