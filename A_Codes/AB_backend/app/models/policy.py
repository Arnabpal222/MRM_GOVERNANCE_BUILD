from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, VersionedMixin


class PolicySetting(TimestampMixin, VersionedMixin, Base):
    """Configuration-driven business rules (BRD §69). Values are stored as text and parsed by value_type."""

    __tablename__ = "policy_setting"

    setting_key: Mapped[str] = mapped_column(String(80), primary_key=True)
    value: Mapped[str] = mapped_column(Text)
    value_type: Mapped[str] = mapped_column(String(20))
    category: Mapped[str | None] = mapped_column(String(40))
    description: Mapped[str | None] = mapped_column(Text)
    updated_by: Mapped[str | None] = mapped_column(String(20))
