"""Per-template adapters: apply one checked row through the business services (never directly to tables).

Each returns an outcome — "new", "updated", "unchanged" or "skipped" — plus any warnings.
Re-importing an existing key updates the record (REQ-IMP-05) unless the batch says otherwise.
"""
from collections.abc import Callable

from sqlalchemy.orm import Session

from app.auth.security import Principal
from app.models import AppUser, Approval, Finding, Model, ModelRelationship, PolicySetting, Validation
from app.services import (
    approval_service,
    finding_service,
    model_service,
    policy_service,
    user_service,
    validation_service,
)
from app.services.errors import ConflictError, ValidationFailedError

Outcome = tuple[str, list[str]]
ON_EXISTING = ("update", "skip", "reject")


def _existing(db: Session, orm, key: str, on_existing: str, label: str):
    obj = db.get(orm, key)
    if obj is not None and on_existing == "reject":
        raise ConflictError(f"{label} {key} already exists and this batch is set to reject existing records.")
    return obj


def _outcome(before: dict, after: dict) -> str:
    return "unchanged" if before == after else "updated"


def apply_t12(db: Session, principal: Principal | None, row: dict, batch_id: str, on_existing: str) -> Outcome:
    key = row["setting_key"]
    existing = _existing(db, PolicySetting, key, on_existing, "Policy setting")
    if existing is not None and on_existing == "skip":
        return "skipped", []
    before = (existing.value, existing.value_type, existing.category, existing.description) if existing else None
    s = policy_service.upsert_setting(db, principal, key=key, value=row["value"], value_type=row["value_type"],
                                      category=row.get("category"), description=row.get("description"),
                                      import_batch_id=batch_id)
    after = (s.value, s.value_type, s.category, s.description)
    if key in policy_service.TIER_KEYS and (before is None or before[0] != s.value) \
            and db.query(Model).first() is not None:
        db.flush()
        model_service.recalculate_tiers(db, principal)
    if before is None:
        return "new", []
    return _outcome({"v": before}, {"v": after}), []


def apply_t01(db: Session, principal: Principal | None, row: dict, batch_id: str, on_existing: str) -> Outcome:
    uid = row["user_id"]
    existing = _existing(db, AppUser, uid, on_existing, "User")
    if existing is not None and on_existing == "skip":
        return "skipped", []
    before = user_service._snapshot(existing) if existing else None
    u = user_service.upsert_user(db, principal, user_id=uid, full_name=row["full_name"], email=row["email"],
                                 business_line=row.get("business_line"), roles=row["role"],
                                 active=row["active"], import_batch_id=batch_id)
    db.flush()  # surfaces a duplicate email as a row error now, not at commit
    return ("new" if before is None else _outcome(before, user_service._snapshot(u))), []


def apply_t02(db: Session, principal: Principal | None, row: dict, batch_id: str, on_existing: str) -> Outcome:
    warnings: list[str] = []
    mid = row["model_id"]
    row = {k: v for k, v in row.items() if k != "successor_model_id"}
    legacy = bool(row.pop("legacy_sod_exception", False))
    if legacy and principal is not None:
        warnings.append("legacy_sod_exception is only honoured for the system seed; it was ignored.")
        legacy = False
    existing = _existing(db, Model, mid, on_existing, "Model")
    if existing is not None and on_existing == "skip":
        return "skipped", warnings
    if existing is None:
        model_service.create_model(db, principal, row, legacy_sod=legacy, import_batch_id=batch_id,
                                   reason="Imported", commit=False)
        outcome = "new"
    else:
        before = model_service.snapshot(existing)
        data = {k: v for k, v in row.items() if k != "model_id"}
        m = model_service.update_model(db, principal, mid, data, None, reason="Imported",
                                       import_batch_id=batch_id, commit=False)
        outcome = _outcome(before, model_service.snapshot(m))
    return outcome, warnings


def link_t02(db: Session, principal: Principal | None, row: dict, batch_id: str) -> bool:
    """Post-pass after every T02 row: successor links may point at models later in the same file."""
    mid, successor = row["model_id"], row.get("successor_model_id")
    if not successor or db.get(ModelRelationship, (mid, successor, "successor")) is not None:
        return False
    model_service.add_relationship(db, principal, mid, successor, "successor", commit=False)
    return True


def _record_adapter(orm, label: str, key: str, create: Callable, update: Callable, snapshot: Callable):
    def apply(db: Session, principal: Principal | None, row: dict, batch_id: str, on_existing: str) -> Outcome:
        rid = row[key]
        existing = _existing(db, orm, rid, on_existing, label)
        if existing is not None and on_existing == "skip":
            return "skipped", []
        if existing is None:
            create(db, principal, {**row, "source": "Import"}, import_batch_id=batch_id, commit=False)
            return "new", []
        if existing.model_id != row["model_id"]:
            raise ValidationFailedError(f"{label} {rid} belongs to {existing.model_id}; it cannot be moved to "
                                        f"{row['model_id']} by import.")
        before = snapshot(existing)
        data = {k: v for k, v in row.items() if k not in (key, "model_id")}
        updated = update(db, principal, rid, data, None, import_batch_id=batch_id, commit=False)
        return _outcome(before, snapshot(updated)), []

    return apply


# Applied after all rows of the file, for rows that carry a value in the deferred column.
POST_PASS = {"T02": ("successor_model_id", link_t02)}

ADAPTERS = {
    "T12": apply_t12,
    "T01": apply_t01,
    "T02": apply_t02,
    "T03": _record_adapter(Validation, "Validation", "validation_id", validation_service.create_validation,
                           validation_service.update_validation, validation_service.snapshot),
    "T04": _record_adapter(Finding, "Finding", "finding_id", finding_service.create_finding,
                           finding_service.update_finding, finding_service.snapshot),
    "T05": _record_adapter(Approval, "Approval", "approval_id", approval_service.create_approval,
                           approval_service.update_approval, approval_service.snapshot),
}
