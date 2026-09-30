"""Record-level authorization (BRD §59): role permission plus assignment to the model.

Role permissions alone say *what* a role may do; these checks say *on which records*.
"""
from app.auth.roles import Permission, Role, has_permission
from app.auth.security import Principal
from app.models import Model
from app.services.errors import ForbiddenError

_ALL_MODELS_ROLES = {Role.ADMIN.value}


def _require(principal: Principal, permission: Permission) -> None:
    if not has_permission(principal.role, permission):
        raise ForbiddenError(f"Role '{principal.role}' is not permitted to perform this action ({permission.value}).")


def ensure_can_edit_model(principal: Principal, model: Model) -> None:
    _require(principal, Permission.MODEL_EDIT)
    if principal.role in _ALL_MODELS_ROLES:
        return
    if principal.role == Role.MODEL_OWNER and model.owner_id == principal.user_id:
        return
    raise ForbiddenError(f"{principal.user_id} ({principal.role}) can only edit models they own; "
                         f"{model.model_id} is owned by {model.owner_id}.")


def ensure_can_create_model(principal: Principal, owner_id: str) -> None:
    _require(principal, Permission.MODEL_EDIT)
    if principal.role in _ALL_MODELS_ROLES:
        return
    if principal.role == Role.MODEL_OWNER and owner_id == principal.user_id:
        return
    raise ForbiddenError(f"A {principal.role} can only register models they own themselves.")


def ensure_can_override_tier(principal: Principal) -> None:
    _require(principal, Permission.TIER_OVERRIDE)


def ensure_can_create_validation(principal: Principal, model: Model) -> None:
    """A Validator may open validations only on models they are the assigned validator for."""
    _require(principal, Permission.VALIDATION_EDIT)
    if principal.role in _ALL_MODELS_ROLES:
        return
    if principal.role == Role.VALIDATOR and model.validator_id == principal.user_id:
        return
    raise ForbiddenError(f"{principal.user_id} can only record validations on models assigned to them; "
                         f"{model.model_id} is validated by {model.validator_id or 'nobody yet'}.")


def ensure_can_update_validation(principal: Principal, model: Model, validation_validator_id: str) -> None:
    """A Validator may update a validation they perform, or any validation on a model assigned to them."""
    _require(principal, Permission.VALIDATION_EDIT)
    if principal.role in _ALL_MODELS_ROLES:
        return
    if principal.role == Role.VALIDATOR and principal.user_id in (validation_validator_id, model.validator_id):
        return
    raise ForbiddenError(f"{principal.user_id} is not the validator of this exercise or of model {model.model_id}.")


def ensure_can_edit_finding(principal: Principal, model: Model) -> None:
    _require(principal, Permission.FINDING_EDIT)
    if principal.role in _ALL_MODELS_ROLES:
        return
    if principal.role == Role.MODEL_OWNER and model.owner_id == principal.user_id:
        return
    if principal.role == Role.VALIDATOR and model.validator_id == principal.user_id:
        return
    raise ForbiddenError(f"{principal.user_id} ({principal.role}) is not assigned to model {model.model_id}.")


def ensure_can_record_approval(principal: Principal) -> None:
    _require(principal, Permission.APPROVAL_RECORD)
