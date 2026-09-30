from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import CurrentPrincipal, DbSession, require
from app.auth.roles import Permission
from app.auth.security import Principal
from app.schemas.core import PolicySettingOut, PolicySettingUpdate
from app.services import policy_service

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/policy", response_model=list[PolicySettingOut])
def list_policy(db: DbSession, _: CurrentPrincipal):
    return policy_service.list_settings(db)


@router.put("/policy/{key}", response_model=PolicySettingOut)
def update_policy(
    key: str, body: PolicySettingUpdate, db: DbSession,
    principal: Annotated[Principal, Depends(require(Permission.POLICY_EDIT))],
):
    return policy_service.update_setting(db, principal, key, body.value, body.row_version, body.reason)
