from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.api.deps import CurrentPrincipal, DbSession, require
from app.auth.roles import Permission
from app.auth.security import Principal
from app.schemas.core import UserCreate, UserOut
from app.services import user_service

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("", response_model=list[UserOut])
def list_users(db: DbSession, _: CurrentPrincipal):
    return user_service.list_users(db)


@router.get("/{user_id}", response_model=UserOut)
def get_user(user_id: str, db: DbSession, _: CurrentPrincipal):
    return user_service.get_user(db, user_id)


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(
    body: UserCreate, db: DbSession,
    principal: Annotated[Principal, Depends(require(Permission.USER_MANAGE))],
):
    return user_service.create_user(db, principal, **body.model_dump())
