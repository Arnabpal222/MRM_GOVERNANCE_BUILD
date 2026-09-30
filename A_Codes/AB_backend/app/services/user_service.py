from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit import service as audit
from app.auth.roles import Role
from app.auth.security import Principal
from app.models import AppUser, UserRole
from app.services.errors import ConflictError, NotFoundError, ValidationFailedError

ENTITY = "app_user"


def _snapshot(u: AppUser) -> dict:
    return {
        "user_id": u.user_id, "full_name": u.full_name, "email": u.email,
        "business_line": u.business_line, "active": u.active, "roles": sorted(u.role_names),
    }


def _validate_roles(roles: list[str]) -> list[str]:
    allowed = [r.value for r in Role]
    cleaned = sorted({r.strip() for r in roles if r.strip()})
    if not cleaned:
        raise ValidationFailedError("A user needs at least one role.")
    unknown = [r for r in cleaned if r not in allowed]
    if unknown:
        raise ValidationFailedError(f"Unknown role(s): {', '.join(unknown)}. Allowed roles: {', '.join(allowed)}.")
    return cleaned


def list_users(db: Session, active_only: bool = False) -> list[AppUser]:
    q = select(AppUser).order_by(AppUser.user_id)
    if active_only:
        q = q.where(AppUser.active.is_(True))
    return list(db.scalars(q))


def get_user(db: Session, user_id: str) -> AppUser:
    user = db.get(AppUser, user_id)
    if user is None:
        raise NotFoundError(f"User {user_id} does not exist.")
    return user


def create_user(
    db: Session, principal: Principal, *, user_id: str, full_name: str, email: str,
    business_line: str | None, roles: list[str], active: bool = True,
) -> AppUser:
    roles = _validate_roles(roles)
    if db.get(AppUser, user_id) is not None:
        raise ConflictError(f"User {user_id} already exists.")
    if db.scalar(select(AppUser).where(AppUser.email == email)) is not None:
        raise ConflictError(f"Email {email} is already used by another user.")
    user = AppUser(user_id=user_id, full_name=full_name, email=email, business_line=business_line,
                   active=active, roles=[UserRole(role=r) for r in roles])
    db.add(user)
    audit.record(db, principal, action="create", entity=ENTITY, entity_id=user_id, after=_snapshot(user))
    db.commit()
    db.refresh(user)
    return user


def upsert_user(
    db: Session, principal: Principal | None, *, user_id: str, full_name: str, email: str,
    business_line: str | None, roles: list[str], active: bool, import_batch_id: str | None = None,
) -> AppUser:
    """Create or update from a load (bootstrap / T01 import). Caller commits."""
    roles = _validate_roles(roles)
    user = db.get(AppUser, user_id)
    if user is None:
        user = AppUser(user_id=user_id, full_name=full_name, email=email, business_line=business_line,
                       active=active, roles=[UserRole(role=r) for r in roles])
        db.add(user)
        audit.record(db, principal, action="create", entity=ENTITY, entity_id=user_id,
                     after=_snapshot(user), import_batch_id=import_batch_id)
        return user
    before = _snapshot(user)
    user.full_name, user.email, user.business_line, user.active = full_name, email, business_line, active
    if sorted(user.role_names) != roles:
        user.roles = [UserRole(role=r) for r in roles]
    if _snapshot(user) != before:
        audit.record(db, principal, action="update", entity=ENTITY, entity_id=user_id, before=before,
                     after=_snapshot(user), import_batch_id=import_batch_id)
    return user
