from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BigIntId, Base, JsonType


class AuditEvent(Base):
    """Immutable record of every material write (BRD §58).

    There is no update/delete path in the application; on PostgreSQL a trigger
    (migration 0001) also rejects UPDATE and DELETE.
    """

    __tablename__ = "audit_event"
    __table_args__ = (
        Index("ix_audit_event_entity", "entity", "entity_id"),
    )

    event_id: Mapped[int] = mapped_column(BigIntId, primary_key=True, autoincrement=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    user_id: Mapped[str | None] = mapped_column(String(20), index=True)  # null = system
    role: Mapped[str | None] = mapped_column(String(40))
    action: Mapped[str] = mapped_column(String(40), index=True)
    entity: Mapped[str] = mapped_column(String(60))
    entity_id: Mapped[str] = mapped_column(String(120))
    model_id: Mapped[str | None] = mapped_column(String(20), index=True)
    import_batch_id: Mapped[str | None] = mapped_column(String(40), index=True)
    document_id: Mapped[str | None] = mapped_column(String(40), index=True)
    reason: Mapped[str | None] = mapped_column(Text)
    before_json: Mapped[dict[str, Any] | None] = mapped_column(JsonType)
    after_json: Mapped[dict[str, Any] | None] = mapped_column(JsonType)
