from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.deps import DbSession, require
from app.audit import service as audit
from app.auth.roles import Permission
from app.auth.security import Principal
from app.schemas.core import AuditEventOut

# Read-only by design: no create/update/delete routes exist for audit events (BRD §58).
router = APIRouter(prefix="/api/audit", tags=["audit"])


@router.get("", response_model=list[AuditEventOut])
def list_audit_events(
    db: DbSession,
    _: Annotated[Principal, Depends(require(Permission.AUDIT_READ))],
    user_id: str | None = None,
    model_id: str | None = None,
    entity: str | None = None,
    action: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    batch_id: str | None = None,
    document_id: str | None = None,
    limit: Annotated[int, Query(ge=1, le=1000)] = 200,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    return audit.list_events(
        db, user_id=user_id, model_id=model_id, entity=entity, action=action, date_from=date_from,
        date_to=date_to, batch_id=batch_id, document_id=document_id, limit=limit, offset=offset,
    )
