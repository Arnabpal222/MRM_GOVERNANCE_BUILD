"""Validation exercises (BRD §9)."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit import service as audit
from app.auth.security import Principal
from app.models import Validation
from app.rules import governance_rules, model_rules
from app.services import access, model_service
from app.services.errors import ConflictError, NotFoundError
from app.services.ids import next_id
from app.services.policy_access import Policy
from app.services.record_helpers import check_allowed, check_required, check_user, raise_if

ENTITY = "validation"
FIELDS = ("validation_type", "validator_id", "start_date", "completion_date", "outcome", "summary",
          "recommendations", "report_document_id")


def snapshot(v: Validation) -> dict:
    return {f: getattr(v, f) for f in ("validation_id", "model_id", *FIELDS)}


def list_validations(db: Session, model_id: str | None = None) -> list[Validation]:
    q = select(Validation).order_by(Validation.start_date.desc(), Validation.validation_id.desc())
    if model_id:
        q = q.where(Validation.model_id == model_id)
    return list(db.scalars(q))


def get_validation(db: Session, validation_id: str) -> Validation:
    v = db.get(Validation, validation_id)
    if v is None:
        raise NotFoundError(f"Validation {validation_id} does not exist.")
    return v


def _validate(db: Session, policy: Policy, model, data: dict) -> None:
    errors: list[tuple[str, str]] = []
    check_required(errors, data, ("validation_type", "start_date", "outcome"))
    if data.get("validation_type"):
        check_allowed(errors, "validation_type", data["validation_type"], policy.list("validation_types"))
    if data.get("outcome"):
        check_allowed(errors, "outcome", data["outcome"], policy.list("validation_outcomes"))
    check_user(errors, db, "validator_id", data.get("validator_id"))
    sod = model_rules.sod_violation(model.model_id, model.owner_id, model.developer_id, data.get("validator_id"))
    if sod:
        errors.append(("validator_id", sod))
    if data.get("start_date") and data.get("outcome"):
        errors += governance_rules.validation_errors(data["start_date"], data.get("completion_date"), data["outcome"])
    raise_if(f"Validation for {model.model_id}", errors)


def _apply_currency(db, principal, policy: Policy, model, v: Validation) -> None:
    if v.completion_date and v.outcome in policy.list("validation_currency_outcomes"):
        model_service.record_validation_date(db, principal, model, v.completion_date, v.validation_id)


def create_validation(db: Session, principal: Principal | None, data: dict, *,
                      import_batch_id: str | None = None, commit: bool = True) -> Validation:
    policy = Policy.load(db)
    model = model_service.get_model(db, data.get("model_id"))
    if principal:
        access.ensure_can_create_validation(principal, model)
    validation_id = data.get("validation_id") or next_id(db, Validation.validation_id, "V")
    if db.get(Validation, validation_id) is not None:
        raise ConflictError(f"Validation {validation_id} already exists.")
    _validate(db, policy, model, data)
    v = Validation(validation_id=validation_id, model_id=model.model_id,
                   source=data.get("source") or "Manual", **{f: data.get(f) for f in FIELDS})
    db.add(v)
    audit.record(db, principal, action="create", entity=ENTITY, entity_id=validation_id, model_id=model.model_id,
                 after=snapshot(v), import_batch_id=import_batch_id)
    _apply_currency(db, principal, policy, model, v)
    if commit:
        db.commit()
        db.refresh(v)
    return v


def update_validation(db: Session, principal: Principal, validation_id: str, data: dict, expected_version: int) -> Validation:
    policy = Policy.load(db)
    v = get_validation(db, validation_id)
    model = model_service.get_model(db, v.model_id)
    access.ensure_can_update_validation(principal, model, v.validator_id)
    if v.row_version != expected_version:
        raise ConflictError(f"Validation {validation_id} was changed by someone else; reload and retry.")
    merged = {f: data.get(f, getattr(v, f)) for f in FIELDS}
    _validate(db, policy, model, merged)
    before = snapshot(v)
    for f, val in merged.items():
        setattr(v, f, val)
    if snapshot(v) == before:
        return v
    audit.record(db, principal, action="update", entity=ENTITY, entity_id=validation_id, model_id=model.model_id,
                 before=before, after=snapshot(v))
    _apply_currency(db, principal, policy, model, v)
    db.commit()
    db.refresh(v)
    return v
