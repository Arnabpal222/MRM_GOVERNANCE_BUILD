from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentPrincipal, DbSession
from app.auth.roles import permissions_for
from app.auth.security import create_access_token
from app.config import get_settings
from app.schemas.core import DevUser, LoginRequest, MeResponse, TokenResponse
from app.services import user_service

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _require_dev_mode() -> None:
    if get_settings().auth_mode != "dev":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Dev login is disabled.")


@router.get("/dev-users", response_model=list[DevUser])
def dev_users(db: DbSession):
    """Users available in the header role switcher (dev mode only)."""
    _require_dev_mode()
    return [DevUser(user_id=u.user_id, full_name=u.full_name, roles=u.role_names)
            for u in user_service.list_users(db, active_only=True)]


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: DbSession):
    """Dev login: choose a user and one of their roles. Replaced by OIDC in production."""
    _require_dev_mode()
    user = user_service.get_user(db, body.user_id)
    if not user.active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, f"User {user.user_id} is not active.")
    if body.role not in user.role_names:
        raise HTTPException(status.HTTP_403_FORBIDDEN, f"User {user.user_id} does not hold the role '{body.role}'.")
    return TokenResponse(access_token=create_access_token(user.user_id, body.role))


@router.get("/me", response_model=MeResponse)
def me(principal: CurrentPrincipal, db: DbSession):
    user = user_service.get_user(db, principal.user_id)
    return MeResponse(user_id=user.user_id, full_name=user.full_name, role=principal.role,
                      roles=user.role_names, permissions=permissions_for(principal.role))
