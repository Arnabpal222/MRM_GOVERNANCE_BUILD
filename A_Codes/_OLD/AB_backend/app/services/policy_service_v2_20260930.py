from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

from app.audit import service as audit
from app.auth.security import Principal
from app.models import PolicySetting
from app.rules.policy_values import (
    PolicyValueError,
    check_key_specific,
    normalise_policy_value,
    parse_policy_value,
)
from app.services.errors import ConflictError, NotFoundError, ValidationFailedError

ENTITY = "policy_setting"
TIER_KEYS = ("tier_high_min", "tier_medium_min")


def _snapshot(s: PolicySetting) -> dict:
    return {"setting_key": s.setting_key, "value": s.value, "value_type": s.value_type, "category": s.category}


def list_settings(db: Session) -> list[PolicySetting]:
    return list(db.scalars(select(PolicySetting).order_by(PolicySetting.category, PolicySetting.setting_key)))


def get_setting(db: Session, key: str) -> PolicySetting:
    setting = db.get(PolicySetting, key)
    if setting is None:
        raise NotFoundError(f"Policy setting '{key}' does not exist.")
    return setting


def _normalise(db: Session, key: str, value: str, value_type: str) -> str:
    try:
        normalised = normalise_policy_value(value, value_type)
        others = {s.setting_key: parse_policy_value(s.value, s.value_type)
                  for s in db.scalars(select(PolicySetting).where(PolicySetting.setting_key.in_(TIER_KEYS)))}
        check_key_specific(key, parse_policy_value(normalised, value_type), others)
    except PolicyValueError as exc:
        raise ValidationFailedError(f"Invalid value for '{key}': {exc}") from None
    return normalised


def update_setting(
    db: Session, principal: Principal, key: str, value: str, expected_version: int, reason: str | None = None
) -> PolicySetting:
    setting = get_setting(db, key)
    if setting.row_version != expected_version:
        raise ConflictError(
            f"Policy setting '{key}' was changed by someone else (version {setting.row_version}); reload and retry."
        )
    new_value = _normalise(db, key, value, setting.value_type)
    if new_value == setting.value:
        return setting

    before = _snapshot(setting)
    setting.value = new_value
    setting.updated_by = principal.user_id
    audit.record(db, principal, action="update", entity=ENTITY, entity_id=key, before=before,
                 after=_snapshot(setting), reason=reason)
    if key in TIER_KEYS:
        from app.services import model_service  # local import: model_service depends on policy access

        db.flush()
        model_service.recalculate_tiers(db, principal)
    try:
        db.commit()
    except StaleDataError:
        db.rollback()
        raise ConflictError(f"Policy setting '{key}' was changed by someone else; reload and retry.") from None
    db.refresh(setting)
    return setting


def upsert_setting(
    db: Session, principal: Principal | None, *, key: str, value: str, value_type: str,
    category: str | None, description: str | None, import_batch_id: str | None = None,
) -> PolicySetting:
    """Create or update from a load (bootstrap / T12 import). Caller commits."""
    try:
        new_value = normalise_policy_value(value, value_type)
        check_key_specific(key, parse_policy_value(new_value, value_type), {})
    except PolicyValueError as exc:
        raise ValidationFailedError(f"Invalid value for '{key}': {exc}") from None
    setting = db.get(PolicySetting, key)
    if setting is None:
        setting = PolicySetting(setting_key=key, value=new_value, value_type=value_type,
                                category=category, description=description)
        db.add(setting)
        audit.record(db, principal, action="create", entity=ENTITY, entity_id=key,
                     after=_snapshot(setting), import_batch_id=import_batch_id)
        return setting
    before = _snapshot(setting)
    setting.value, setting.value_type = new_value, value_type
    setting.category, setting.description = category, description
    if _snapshot(setting) != before:
        audit.record(db, principal, action="update", entity=ENTITY, entity_id=key, before=before,
                     after=_snapshot(setting), import_batch_id=import_batch_id)
    return setting
