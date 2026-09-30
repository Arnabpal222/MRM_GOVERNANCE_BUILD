"""Small helpers shared by the governance record services."""
from sqlalchemy.orm import Session

from app.models import AppUser
from app.services.errors import ValidationFailedError


def check_allowed(errors: list[tuple[str, str]], field: str, value, allowed: list[str]) -> None:
    if value not in allowed:
        errors.append((field, f"'{value}' is not allowed for {field}. Allowed: {', '.join(allowed)}."))


def check_user(errors: list[tuple[str, str]], db: Session, field: str, user_id: str | None, required: bool = True) -> None:
    if not user_id:
        if required:
            errors.append((field, f"{field} is required."))
        return
    user = db.get(AppUser, user_id)
    if user is None:
        errors.append((field, f"User {user_id} does not exist."))
    elif not user.active:
        errors.append((field, f"User {user_id} is not active."))


def check_required(errors: list[tuple[str, str]], data: dict, fields: tuple[str, ...]) -> None:
    for f in fields:
        if data.get(f) in (None, ""):
            errors.append((f, f"{f} is required."))


def raise_if(entity_label: str, errors: list[tuple[str, str]]) -> None:
    if errors:
        raise ValidationFailedError(f"{entity_label} could not be saved. " + " ".join(m for _, m in errors),
                                    [{"field": f, "message": m} for f, m in errors])
