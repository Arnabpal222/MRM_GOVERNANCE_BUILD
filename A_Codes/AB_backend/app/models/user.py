from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, VersionedMixin


class AppUser(TimestampMixin, VersionedMixin, Base):
    __tablename__ = "app_user"

    user_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    full_name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(255), unique=True)
    business_line: Mapped[str | None] = mapped_column(String(120))
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)

    roles: Mapped[list["UserRole"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", lazy="selectin", order_by="UserRole.role"
    )

    @property
    def role_names(self) -> list[str]:
        return [r.role for r in self.roles]


class UserRole(Base):
    """A user may hold one or more functional roles (BRD §5)."""

    __tablename__ = "user_role"

    user_id: Mapped[str] = mapped_column(ForeignKey("app_user.user_id"), primary_key=True)
    role: Mapped[str] = mapped_column(String(40), primary_key=True)

    user: Mapped[AppUser] = relationship(back_populates="roles")
