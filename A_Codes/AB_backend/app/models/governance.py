"""Model inventory and governance history tables (BRD §6–§12, §48)."""
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, SmallInteger, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BigIntId, Base, TimestampMixin, VersionedMixin

USER_FK = "app_user.user_id"
MODEL_FK = "model.model_id"


class Model(TimestampMixin, VersionedMixin, Base):
    __tablename__ = "model"
    __table_args__ = (
        Index("ix_model_phase_tier", "lifecycle_phase", "effective_tier"),
    )

    model_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    model_name: Mapped[str] = mapped_column(String(100))
    model_type: Mapped[str] = mapped_column(String(60), index=True)
    model_subtype: Mapped[str] = mapped_column(String(60))
    purpose: Mapped[str] = mapped_column(Text)
    business_line: Mapped[str] = mapped_column(String(120), index=True)
    model_family: Mapped[str | None] = mapped_column(String(120))
    owner_id: Mapped[str] = mapped_column(ForeignKey(USER_FK), index=True)
    developer_id: Mapped[str] = mapped_column(ForeignKey(USER_FK))
    validator_id: Mapped[str | None] = mapped_column(ForeignKey(USER_FK), index=True)
    lifecycle_phase: Mapped[str] = mapped_column(String(40), index=True)
    version: Mapped[str] = mapped_column(String(40))
    go_live_date: Mapped[date | None] = mapped_column(Date)
    revalidation_frequency: Mapped[str | None] = mapped_column(String(40))
    last_validation_date: Mapped[date | None] = mapped_column(Date, index=True)
    # Derived and persisted so portfolio queries can filter/index on them; recalculated by
    # model_service whenever answers, overrides or tier policy change.
    tier_score: Mapped[int] = mapped_column(SmallInteger)
    calculated_tier: Mapped[str] = mapped_column(String(10))
    effective_tier: Mapped[str] = mapped_column(String(10), index=True)
    # Pre-existing SoD conflicts loaded from legacy inventories are kept visible, not silently fixed.
    legacy_sod_exception: Mapped[bool] = mapped_column(Boolean, default=False)

    tiering: Mapped["TieringAnswer"] = relationship(back_populates="model", uselist=False, lazy="joined",
                                                    cascade="all, delete-orphan")


class TieringAnswer(TimestampMixin, Base):
    __tablename__ = "tiering_answer"

    model_id: Mapped[str] = mapped_column(ForeignKey(MODEL_FK), primary_key=True)
    q_materiality: Mapped[int] = mapped_column(SmallInteger)
    q_complexity: Mapped[int] = mapped_column(SmallInteger)
    q_reliance: Mapped[int] = mapped_column(SmallInteger)
    q_regulatory_use: Mapped[int] = mapped_column(SmallInteger)
    override_tier: Mapped[str | None] = mapped_column(String(10))
    override_reason: Mapped[str | None] = mapped_column(Text)
    override_by: Mapped[str | None] = mapped_column(ForeignKey(USER_FK))
    override_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    model: Mapped[Model] = relationship(back_populates="tiering")


class TierOverride(Base):
    """History of tier overrides (BRD §7). The calculated tier is never deleted."""

    __tablename__ = "tier_override"

    override_id: Mapped[int] = mapped_column(BigIntId, primary_key=True, autoincrement=True)
    model_id: Mapped[str] = mapped_column(ForeignKey(MODEL_FK), index=True)
    calculated_tier: Mapped[str] = mapped_column(String(10))
    previous_tier: Mapped[str] = mapped_column(String(10))
    new_tier: Mapped[str] = mapped_column(String(10))
    reason: Mapped[str] = mapped_column(Text)
    user_id: Mapped[str] = mapped_column(ForeignKey(USER_FK))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ModelPhaseHistory(Base):
    """Lifecycle transitions (BRD §8)."""

    __tablename__ = "model_phase_history"

    transition_id: Mapped[int] = mapped_column(BigIntId, primary_key=True, autoincrement=True)
    model_id: Mapped[str] = mapped_column(ForeignKey(MODEL_FK), index=True)
    from_phase: Mapped[str | None] = mapped_column(String(40))
    to_phase: Mapped[str] = mapped_column(String(40))
    reason: Mapped[str | None] = mapped_column(Text)
    user_id: Mapped[str | None] = mapped_column(ForeignKey(USER_FK))
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ModelVersion(Base):
    """Model version history, tracked independently of the model ID (REQ-INV-04)."""

    __tablename__ = "model_version"

    model_id: Mapped[str] = mapped_column(ForeignKey(MODEL_FK), primary_key=True)
    version: Mapped[str] = mapped_column(String(40), primary_key=True)
    change_reason: Mapped[str | None] = mapped_column(Text)
    user_id: Mapped[str | None] = mapped_column(ForeignKey(USER_FK))
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ModelRelationship(Base):
    """successor / parent / related links (REQ-INV-05). Predecessor and child are the inverse view."""

    __tablename__ = "model_relationship"

    model_id: Mapped[str] = mapped_column(ForeignKey(MODEL_FK), primary_key=True)
    related_model_id: Mapped[str] = mapped_column(ForeignKey(MODEL_FK), primary_key=True, index=True)
    relationship_type: Mapped[str] = mapped_column(String(20), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Validation(TimestampMixin, VersionedMixin, Base):
    __tablename__ = "validation"

    validation_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    model_id: Mapped[str] = mapped_column(ForeignKey(MODEL_FK), index=True)
    validation_type: Mapped[str] = mapped_column(String(40))
    validator_id: Mapped[str] = mapped_column(ForeignKey(USER_FK), index=True)
    start_date: Mapped[date] = mapped_column(Date)
    completion_date: Mapped[date | None] = mapped_column(Date)
    outcome: Mapped[str] = mapped_column(String(40), index=True)
    summary: Mapped[str | None] = mapped_column(Text)
    recommendations: Mapped[str | None] = mapped_column(Text)
    report_document_id: Mapped[str | None] = mapped_column(ForeignKey("document.document_id"))
    source: Mapped[str] = mapped_column(String(20), default="Manual")


class Finding(TimestampMixin, VersionedMixin, Base):
    __tablename__ = "finding"
    __table_args__ = (
        Index("ix_finding_model_status", "model_id", "status"),
    )

    finding_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    model_id: Mapped[str] = mapped_column(ForeignKey(MODEL_FK))
    validation_id: Mapped[str | None] = mapped_column(ForeignKey("validation.validation_id"), index=True)
    title: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text)
    severity: Mapped[str] = mapped_column(String(20), index=True)
    category: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(20), index=True)
    owner_id: Mapped[str] = mapped_column(ForeignKey(USER_FK), index=True)
    raised_date: Mapped[date] = mapped_column(Date)
    due_date: Mapped[date] = mapped_column(Date, index=True)
    closed_date: Mapped[date | None] = mapped_column(Date)
    source: Mapped[str] = mapped_column(String(20), default="Manual")
    evidence: Mapped[str | None] = mapped_column(Text)
    root_cause: Mapped[str | None] = mapped_column(Text)
    management_response: Mapped[str | None] = mapped_column(Text)
    remediation_action: Mapped[str | None] = mapped_column(Text)


class Approval(TimestampMixin, VersionedMixin, Base):
    __tablename__ = "approval"

    approval_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    model_id: Mapped[str] = mapped_column(ForeignKey(MODEL_FK), index=True)
    decision_date: Mapped[date] = mapped_column(Date, index=True)
    forum: Mapped[str] = mapped_column(String(60))
    decision_type: Mapped[str] = mapped_column(String(60))
    decision: Mapped[str] = mapped_column(String(20), index=True)
    conditions: Mapped[str | None] = mapped_column(Text)
    condition_due_date: Mapped[date | None] = mapped_column(Date)
    condition_status: Mapped[str | None] = mapped_column(String(10))
    supporting_document_id: Mapped[str | None] = mapped_column(ForeignKey("document.document_id"))
    recorded_by: Mapped[str | None] = mapped_column(ForeignKey(USER_FK))
