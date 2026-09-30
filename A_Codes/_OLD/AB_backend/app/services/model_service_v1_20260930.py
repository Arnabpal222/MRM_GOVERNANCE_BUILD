"""Model inventory service: registration, editing, tiering, overrides, lifecycle, versions, relationships.

Every write validates against policy-driven rules, writes an audit event in the same
transaction and commits (unless commit=False for batch loaders).
"""
from datetime import UTC, date, datetime

from sqlalchemy import or_, select
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy.orm.exc import StaleDataError

from app.audit import service as audit
from app.auth.security import Principal
from app.clock import today
from app.models import (
    AppUser,
    Model,
    ModelPhaseHistory,
    ModelRelationship,
    ModelVersion,
    TieringAnswer,
    TierOverride,
)
from app.rules import model_rules, tiering
from app.services import access
from app.services.errors import ConflictError, NotFoundError, ValidationFailedError
from app.services.ids import next_id
from app.services.policy_access import Policy

ENTITY = "model"
MODEL_FIELDS = (
    "model_name", "model_type", "model_subtype", "purpose", "business_line", "model_family", "owner_id",
    "developer_id", "validator_id", "lifecycle_phase", "version", "go_live_date", "revalidation_frequency",
    "last_validation_date",
)


def snapshot(m: Model) -> dict:
    data = {f: getattr(m, f) for f in ("model_id", *MODEL_FIELDS)}
    data.update(tier_score=m.tier_score, calculated_tier=m.calculated_tier, effective_tier=m.effective_tier)
    if m.tiering is not None:
        data.update({q: getattr(m.tiering, q) for q in tiering.TIERING_QUESTIONS})
        data["override_tier"] = m.tiering.override_tier
    return data


def _fail(model_id: str, errors: list[tuple[str, str]]) -> None:
    if errors:
        summary = " ".join(msg for _, msg in errors)
        raise ValidationFailedError(f"Model {model_id} could not be saved. {summary}",
                                    [{"field": f, "message": m} for f, m in errors])


def get_model(db: Session, model_id: str) -> Model:
    model = db.get(Model, model_id)
    if model is None:
        raise NotFoundError(f"Model {model_id} does not exist.")
    return model


def _validate(db: Session, policy: Policy, model_id: str, fields: dict, answers: dict, legacy_sod: bool) -> None:
    errors: list[tuple[str, str]] = []
    for f in ("model_name", "model_type", "model_subtype", "purpose", "business_line", "owner_id",
              "developer_id", "lifecycle_phase", "version"):
        if not fields.get(f):
            errors.append((f, f"{f} is required."))
    name = fields.get("model_name") or ""
    if name and not 3 <= len(name) <= 100:
        errors.append(("model_name", "Model name must be 3–100 characters."))
    if fields.get("model_type") and fields["model_type"] not in policy.list("model_types"):
        errors.append(("model_type", f"'{fields['model_type']}' is not an allowed model type. "
                                     f"Allowed: {', '.join(policy.list('model_types'))}."))
    freq = fields.get("revalidation_frequency")
    if freq and freq not in policy.frequency_months:
        errors.append(("revalidation_frequency", f"'{freq}' is not an allowed frequency. "
                                                 f"Allowed: {', '.join(policy.frequency_months)}."))
    for f in ("owner_id", "developer_id", "validator_id"):
        uid = fields.get(f)
        if uid:
            user = db.get(AppUser, uid)
            if user is None:
                errors.append((f, f"User {uid} does not exist."))
            elif not user.active:
                errors.append((f, f"User {uid} is not active."))
    errors += [("tiering", m) for m in tiering.validate_answers(answers)]
    errors += model_rules.field_errors(fields, policy.phase_requirements, today())
    if not legacy_sod:
        sod = model_rules.sod_violation(model_id, fields.get("owner_id"), fields.get("developer_id"),
                                        fields.get("validator_id"))
        if sod:
            errors.append(("validator_id", sod))
    _fail(model_id, errors)


def _apply_tier(model: Model, policy: Policy) -> None:
    answers = {q: getattr(model.tiering, q) for q in tiering.TIERING_QUESTIONS}
    result = tiering.calculate_tier(answers, policy.int("tier_high_min"), policy.int("tier_medium_min"))
    model.tier_score, model.calculated_tier = result.score, result.tier
    model.effective_tier = tiering.effective_tier(result.tier, model.tiering.override_tier)


def tier_preview(policy: Policy, answers: dict) -> dict:
    errors = tiering.validate_answers(answers)
    if errors:
        raise ValidationFailedError(" ".join(errors))
    r = tiering.calculate_tier(answers, policy.int("tier_high_min"), policy.int("tier_medium_min"))
    return {"tier_score": r.score, "tier": r.tier,
            "thresholds": {"high_min": policy.int("tier_high_min"), "medium_min": policy.int("tier_medium_min")}}


def create_model(
    db: Session, principal: Principal | None, data: dict, *, legacy_sod: bool = False,
    import_batch_id: str | None = None, reason: str | None = None, commit: bool = True,
) -> Model:
    policy = Policy.load(db)
    model_id = data.get("model_id") or next_id(db, Model.model_id, "M")
    if db.get(Model, model_id) is not None:
        raise ConflictError(f"Model {model_id} already exists.")
    if principal:
        access.ensure_can_create_model(principal, data.get("owner_id"))
    fields = {f: data.get(f) for f in MODEL_FIELDS}
    answers = {q: data.get(q) for q in tiering.TIERING_QUESTIONS}
    _validate(db, policy, model_id, fields, answers, legacy_sod)

    model = Model(model_id=model_id, legacy_sod_exception=legacy_sod, **fields)
    model.tiering = TieringAnswer(**answers)
    _apply_tier(model, policy)
    db.add(model)
    db.add(ModelPhaseHistory(model_id=model_id, from_phase=None, to_phase=model.lifecycle_phase,
                             reason=reason or "Model registered", user_id=principal.user_id if principal else None))
    db.add(ModelVersion(model_id=model_id, version=model.version, change_reason="Initial version",
                        user_id=principal.user_id if principal else None))
    audit.record(db, principal, action="create", entity=ENTITY, entity_id=model_id, model_id=model_id,
                 after=snapshot(model), import_batch_id=import_batch_id,
                 reason="Legacy segregation-of-duties exception loaded" if legacy_sod else reason)
    if commit:
        db.commit()
        db.refresh(model)
    return model


def update_model(
    db: Session, principal: Principal | None, model_id: str, data: dict, expected_version: int | None,
    *, reason: str | None = None, import_batch_id: str | None = None, commit: bool = True,
) -> Model:
    policy = Policy.load(db)
    model = get_model(db, model_id)
    if principal:
        access.ensure_can_edit_model(principal, model)
    if expected_version is not None and model.row_version != expected_version:
        raise ConflictError(f"Model {model_id} was changed by someone else (version {model.row_version}); reload and retry.")

    before = snapshot(model)
    fields = {f: data.get(f, getattr(model, f)) for f in MODEL_FIELDS}
    answers = {q: data.get(q, getattr(model.tiering, q)) for q in tiering.TIERING_QUESTIONS}
    _validate(db, policy, model_id, fields, answers, model.legacy_sod_exception and
              fields["validator_id"] == model.validator_id)

    old_phase, old_version = model.lifecycle_phase, model.version
    for f, v in fields.items():
        setattr(model, f, v)
    for q, v in answers.items():
        setattr(model.tiering, q, v)
    _apply_tier(model, policy)
    if model.legacy_sod_exception and not model_rules.sod_violation(
            model_id, model.owner_id, model.developer_id, model.validator_id):
        model.legacy_sod_exception = False  # conflict resolved by reassignment

    user_id = principal.user_id if principal else None
    if model.lifecycle_phase != old_phase:
        db.add(ModelPhaseHistory(model_id=model_id, from_phase=old_phase, to_phase=model.lifecycle_phase,
                                 reason=reason, user_id=user_id))
    if model.version != old_version and db.get(ModelVersion, (model_id, model.version)) is None:
        db.add(ModelVersion(model_id=model_id, version=model.version, change_reason=reason, user_id=user_id))

    after = snapshot(model)
    if after == before:
        db.rollback()
        return model
    audit.record(db, principal, action="update", entity=ENTITY, entity_id=model_id, model_id=model_id,
                 before=before, after=after, reason=reason, import_batch_id=import_batch_id)
    if commit:
        _commit(db, model_id)
        db.refresh(model)
    return model


def transition_phase(db: Session, principal: Principal, model_id: str, to_phase: str, reason: str | None,
                     expected_version: int) -> Model:
    model = get_model(db, model_id)
    if to_phase == model.lifecycle_phase:
        raise ValidationFailedError(f"Model {model_id} is already in {to_phase}.")
    return update_model(db, principal, model_id, {"lifecycle_phase": to_phase}, expected_version, reason=reason)


def override_tier(db: Session, principal: Principal, model_id: str, tier: str | None, reason: str,
                  expected_version: int) -> Model:
    """Set (tier) or remove (tier=None) an override. The calculated tier is always kept."""
    access.ensure_can_override_tier(principal)
    model = get_model(db, model_id)
    if model.row_version != expected_version:
        raise ConflictError(f"Model {model_id} was changed by someone else; reload and retry.")
    if not (reason or "").strip():
        raise ValidationFailedError("A reason is required to override or remove a risk tier override.")
    if tier is not None and tier not in tiering.TIERS:
        raise ValidationFailedError(f"'{tier}' is not a tier. Allowed: {', '.join(tiering.TIERS)}.")
    if tier == model.tiering.override_tier:
        raise ValidationFailedError(f"Model {model_id} already has override tier {tier or 'none'}.")

    before = snapshot(model)
    previous = model.effective_tier
    t = model.tiering
    t.override_tier = tier
    t.override_reason = reason if tier else None
    t.override_by = principal.user_id if tier else None
    t.override_at = datetime.now(UTC) if tier else None
    _apply_tier(model, Policy.load(db))
    flag_modified(model, "effective_tier")  # always bump the model's row_version, even if the tier is unchanged
    db.add(TierOverride(model_id=model_id, calculated_tier=model.calculated_tier, previous_tier=previous,
                        new_tier=model.effective_tier, reason=reason, user_id=principal.user_id))
    audit.record(db, principal, action="tier_override", entity=ENTITY, entity_id=model_id, model_id=model_id,
                 before=before, after=snapshot(model), reason=reason)
    _commit(db, model_id)
    db.refresh(model)
    return model


def add_relationship(db: Session, principal: Principal | None, model_id: str, related_model_id: str,
                     relationship_type: str, *, commit: bool = True) -> ModelRelationship:
    model = get_model(db, model_id)
    get_model(db, related_model_id)
    if principal:
        access.ensure_can_edit_model(principal, model)
    error = model_rules.relationship_error(model_id, related_model_id, relationship_type, model.lifecycle_phase,
                                           Policy.load(db).retirement_phase)
    if error:
        raise ValidationFailedError(error)
    key = (model_id, related_model_id, relationship_type)
    if db.get(ModelRelationship, key) is not None:
        raise ConflictError(f"{model_id} already has {relationship_type} {related_model_id}.")
    rel = ModelRelationship(model_id=model_id, related_model_id=related_model_id, relationship_type=relationship_type)
    db.add(rel)
    audit.record(db, principal, action="create", entity="model_relationship",
                 entity_id=f"{model_id}:{relationship_type}:{related_model_id}", model_id=model_id,
                 after={"model_id": model_id, "related_model_id": related_model_id,
                        "relationship_type": relationship_type})
    if commit:
        db.commit()
    return rel


def relationships_for(db: Session, model_id: str) -> list[dict]:
    rows = db.scalars(select(ModelRelationship).where(
        or_(ModelRelationship.model_id == model_id, ModelRelationship.related_model_id == model_id)))
    out = []
    for r in rows:
        if r.model_id == model_id:
            out.append({"relationship": r.relationship_type, "model_id": r.related_model_id})
        else:
            out.append({"relationship": model_rules.INVERSE_LABEL[r.relationship_type], "model_id": r.model_id})
    return out


def recalculate_tiers(db: Session, principal: Principal | None) -> int:
    """Re-derive every model's tier after tier thresholds change. Caller commits."""
    policy = Policy.load(db)
    changed = 0
    for model in db.scalars(select(Model)):
        before = (model.tier_score, model.calculated_tier, model.effective_tier)
        _apply_tier(model, policy)
        if before != (model.tier_score, model.calculated_tier, model.effective_tier):
            changed += 1
            audit.record(db, principal, action="recalculate", entity=ENTITY, entity_id=model.model_id,
                         model_id=model.model_id,
                         before={"calculated_tier": before[1], "effective_tier": before[2]},
                         after={"calculated_tier": model.calculated_tier, "effective_tier": model.effective_tier},
                         reason="Tier thresholds changed")
    return changed


def record_validation_date(db: Session, principal: Principal | None, model: Model, completion: date,
                           validation_id: str) -> None:
    """A completed validation with a currency outcome moves last_validation_date forward. Caller commits."""
    if model.last_validation_date is not None and model.last_validation_date >= completion:
        return
    before = {"last_validation_date": model.last_validation_date}
    model.last_validation_date = completion
    audit.record(db, principal, action="update", entity=ENTITY, entity_id=model.model_id, model_id=model.model_id,
                 before=before, after={"last_validation_date": completion},
                 reason=f"Validation {validation_id} completed")


def _commit(db: Session, model_id: str) -> None:
    try:
        db.commit()
    except StaleDataError:
        db.rollback()
        raise ConflictError(f"Model {model_id} was changed by someone else; reload and retry.") from None
