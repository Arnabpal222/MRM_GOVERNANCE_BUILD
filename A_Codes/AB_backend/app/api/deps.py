from collections.abc import Callable
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.auth.roles import Permission, has_permission
from app.auth.security import Principal, decode_access_token
from app.db import get_db
from app.models import AppUser

DbSession = Annotated[Session, Depends(get_db)]

_bearer = HTTPBearer(auto_error=False)


def get_principal(
    db: DbSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> Principal:
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Sign in required.")
    try:
        claims = decode_access_token(credentials.credentials)
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session is invalid or has expired; sign in again.") from None
    # Re-check against the database on every request: a deactivated user or a removed role
    # takes effect immediately, whatever the token says.
    user = db.get(AppUser, claims.get("sub"))
    if user is None or not user.active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User is not active.")
    role = claims.get("role")
    if role not in user.role_names:
        raise HTTPException(status.HTTP_403_FORBIDDEN, f"User {user.user_id} no longer holds the role '{role}'.")
    return Principal(user_id=user.user_id, role=role, full_name=user.full_name)


CurrentPrincipal = Annotated[Principal, Depends(get_principal)]


def require(permission: Permission) -> Callable[..., Principal]:
    def dependency(principal: CurrentPrincipal) -> Principal:
        if not has_permission(principal.role, permission):
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                f"Role '{principal.role}' is not permitted to perform this action ({permission.value}).",
            )
        return principal

    return dependency
