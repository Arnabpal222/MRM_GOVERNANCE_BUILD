"""Model inventory rules: R5 segregation of duties and phase-dependent field requirements."""
from dataclasses import dataclass
from datetime import date


def sod_violation(model_id: str, owner_id: str | None, developer_id: str | None, validator_id: str | None) -> str | None:
    """R5 (BRD REQ-INV-03): the validator must differ from the owner and the developer."""
    if not validator_id:
        return None
    if validator_id == owner_id:
        return f"Validator {validator_id} cannot validate model {model_id} because {validator_id} is also the model owner."
    if validator_id == developer_id:
        return f"Validator {validator_id} cannot validate model {model_id} because {validator_id} is also the model developer."
    return None


def phase_index(phases: list[str], phase: str) -> int:
    return phases.index(phase) if phase in phases else -1


def at_or_after(phases: list[str], phase: str, reference: str) -> bool:
    return phase_index(phases, phase) >= phase_index(phases, reference) >= 0


@dataclass(frozen=True)
class PhaseRequirements:
    phases: list[str]
    validator_from: str
    validation_data_from: str
    retirement_phase: str = "Retirement"


def field_errors(fields: dict, req: PhaseRequirements, today: date) -> list[tuple[str, str]]:
    """Phase-dependent requirements from template T02. Returns (field, message) pairs."""
    errors: list[tuple[str, str]] = []
    phase = fields.get("lifecycle_phase")
    if phase not in req.phases:
        errors.append(("lifecycle_phase", f"'{phase}' is not a lifecycle phase. Allowed: {', '.join(req.phases)}."))
        return errors
    if at_or_after(req.phases, phase, req.validator_from) and not fields.get("validator_id") \
            and phase != req.retirement_phase:
        errors.append(("validator_id", f"A validator is required from the {req.validator_from} phase onwards."))
    if at_or_after(req.phases, phase, req.validation_data_from) and phase != req.retirement_phase:
        for f, label in (("go_live_date", "Go-live date"), ("revalidation_frequency", "Revalidation frequency"),
                         ("last_validation_date", "Last validation date")):
            if not fields.get(f):
                errors.append((f, f"{label} is required from the {req.validation_data_from} phase onwards."))
    last = fields.get("last_validation_date")
    if last and last > today:
        errors.append(("last_validation_date", "Last validation date cannot be in the future."))
    return errors


RELATIONSHIP_TYPES = ("successor", "related", "parent")
INVERSE_LABEL = {"successor": "predecessor", "parent": "child", "related": "related"}


def relationship_error(model_id: str, related_id: str, rel_type: str, model_phase: str,
                       retirement_phase: str = "Retirement") -> str | None:
    if rel_type not in RELATIONSHIP_TYPES:
        return f"Unknown relationship type '{rel_type}'. Allowed: {', '.join(RELATIONSHIP_TYPES)}."
    if model_id == related_id:
        return "A model cannot be related to itself."
    if rel_type == "successor" and model_phase != retirement_phase:
        return f"Only a model in {retirement_phase} can have a successor; {model_id} is in {model_phase}."
    return None
