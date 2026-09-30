"""Audit trail writer. Every service that performs a material write calls record() inside
the same transaction, so the business change and its audit event commit or roll back together."""
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.security import Principal
from app.models import AuditEvent

SYSTEM_USER = None
SYSTEM_ROLE = "System"


def _jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(v) for v in value]
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    return value


def record(
    db: Session,
    principal: Principal | None,
    *,
    action: str,
    entity: str,
    entity_id: str,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    model_id: str | None = None,
    import_batch_id: str | None = None,
    document_id: str | None = None,
    reason: str | None = None,
) -> AuditEvent:
    event = AuditEvent(
        user_id=principal.user_id if principal else SYSTEM_USER,
        role=principal.role if principal else SYSTEM_ROLE,
        action=action,
        entity=entity,
        entity_id=entity_id,
        model_id=model_id,
        import_batch_id=import_batch_id,
        document_id=document_id,
        reason=reason,
        before_json=_jsonable(before) if before is not None else None,
        after_json=_jsonable(after) if after is not None else None,
    )
    db.add(event)
    return event


def list_events(
    db: Session,
    *,
    user_id: str | None = None,
    model_id: str | None = None,
    entity: str | None = None,
    action: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    batch_id: str | None = None,
    document_id: str | None = None,
    limit: int = 200,
    offset: int = 0,
) -> list[AuditEvent]:
    q = select(AuditEvent)
    if user_id:
        q = q.where(AuditEvent.user_id == user_id)
    if model_id:
        q = q.where(AuditEvent.model_id == model_id)
    if entity:
        q = q.where(AuditEvent.entity == entity)
    if action:
        q = q.where(AuditEvent.action == action)
    if date_from:
        q = q.where(AuditEvent.occurred_at >= datetime.combine(date_from, datetime.min.time()))
    if date_to:
        q = q.where(AuditEvent.occurred_at < datetime.combine(date_to, datetime.max.time()))
    if batch_id:
        q = q.where(AuditEvent.import_batch_id == batch_id)
    if document_id:
        q = q.where(AuditEvent.document_id == document_id)
    q = q.order_by(AuditEvent.occurred_at.desc(), AuditEvent.event_id.desc()).limit(limit).offset(offset)
    return list(db.scalars(q))
