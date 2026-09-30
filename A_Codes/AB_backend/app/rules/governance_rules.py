"""Validation, finding and approval record rules (BRD §9, §11, §12)."""
from dataclasses import dataclass
from datetime import date


def validation_errors(start: date, completion: date | None, outcome: str, in_progress: str = "In Progress") -> list[tuple[str, str]]:
    errors = []
    if outcome != in_progress and completion is None:
        errors.append(("completion_date", f"Completion date is required when the outcome is {outcome}."))
    if completion is not None and completion < start:
        errors.append(("completion_date", "Completion date cannot be before the start date."))
    return errors


def finding_errors(status: str, raised: date, due: date, closed: date | None, open_statuses: list[str]) -> list[tuple[str, str]]:
    errors = []
    if due < raised:
        errors.append(("due_date", "Due date cannot be before the raised date."))
    if status not in open_statuses and closed is None:
        errors.append(("closed_date", f"Closed date is required when the status is {status}."))
    if status in open_statuses and closed is not None:
        errors.append(("closed_date", f"A finding with status {status} cannot have a closed date."))
    if closed is not None and closed < raised:
        errors.append(("closed_date", "Closed date cannot be before the raised date."))
    return errors


@dataclass(frozen=True)
class FindingAge:
    is_open: bool
    days_open: int
    days_overdue: int  # 0 when not overdue
    is_overdue: bool


def finding_age(status: str, raised: date, due: date, closed: date | None, today: date, open_statuses: list[str]) -> FindingAge:
    is_open = status in open_statuses
    end = today if is_open or closed is None else closed
    days_overdue = max(0, (today - due).days) if is_open else 0
    return FindingAge(is_open=is_open, days_open=max(0, (end - raised).days),
                      days_overdue=days_overdue, is_overdue=days_overdue > 0)


def approval_errors(decision: str, conditions: str | None, condition_due: date | None, condition_status: str | None,
                    conditional: str = "Conditional") -> list[tuple[str, str]]:
    errors = []
    if decision == conditional:
        if not (conditions or "").strip():
            errors.append(("conditions", "Conditions are required for a Conditional decision."))
        if condition_due is None:
            errors.append(("condition_due_date", "A condition due date is required for a Conditional decision."))
        if condition_status not in ("Open", "Met"):
            errors.append(("condition_status", "Condition status must be Open or Met for a Conditional decision."))
    return errors
