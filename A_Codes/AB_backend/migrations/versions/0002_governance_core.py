"""Phase 2 governance core: model inventory, tiering, lifecycle, versions, relationships,
validations, findings and approvals.

Revision ID: 0002_governance_core
Revises: 0001_foundation
Create Date: 2026-09-30
"""
import sqlalchemy as sa
from alembic import op

revision = "0002_governance_core"
down_revision = "0001_foundation"
branch_labels = None
depends_on = None

USER = "app_user.user_id"
MODEL = "model.model_id"


def _ts() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    ]


def _fk(table: str, col: str, ref: str) -> sa.ForeignKeyConstraint:
    ref_table = ref.split(".")[0]
    return sa.ForeignKeyConstraint([col], [ref], name=f"fk_{table}_{col}_{ref_table}")


def upgrade() -> None:
    op.create_table(
        "model",
        sa.Column("model_id", sa.String(20), nullable=False),
        sa.Column("model_name", sa.String(100), nullable=False),
        sa.Column("model_type", sa.String(60), nullable=False),
        sa.Column("model_subtype", sa.String(60), nullable=False),
        sa.Column("purpose", sa.Text, nullable=False),
        sa.Column("business_line", sa.String(120), nullable=False),
        sa.Column("model_family", sa.String(120)),
        sa.Column("owner_id", sa.String(20), nullable=False),
        sa.Column("developer_id", sa.String(20), nullable=False),
        sa.Column("validator_id", sa.String(20)),
        sa.Column("lifecycle_phase", sa.String(40), nullable=False),
        sa.Column("version", sa.String(40), nullable=False),
        sa.Column("go_live_date", sa.Date),
        sa.Column("revalidation_frequency", sa.String(40)),
        sa.Column("last_validation_date", sa.Date),
        sa.Column("tier_score", sa.SmallInteger, nullable=False),
        sa.Column("calculated_tier", sa.String(10), nullable=False),
        sa.Column("effective_tier", sa.String(10), nullable=False),
        sa.Column("legacy_sod_exception", sa.Boolean, nullable=False),
        sa.Column("row_version", sa.Integer, nullable=False),
        *_ts(),
        sa.PrimaryKeyConstraint("model_id", name="pk_model"),
        _fk("model", "owner_id", USER), _fk("model", "developer_id", USER), _fk("model", "validator_id", USER),
    )
    for col in ("model_type", "business_line", "owner_id", "validator_id", "lifecycle_phase",
                "last_validation_date", "effective_tier"):
        op.create_index(f"ix_model_{col}", "model", [col])
    op.create_index("ix_model_phase_tier", "model", ["lifecycle_phase", "effective_tier"])

    op.create_table(
        "tiering_answer",
        sa.Column("model_id", sa.String(20), nullable=False),
        sa.Column("q_materiality", sa.SmallInteger, nullable=False),
        sa.Column("q_complexity", sa.SmallInteger, nullable=False),
        sa.Column("q_reliance", sa.SmallInteger, nullable=False),
        sa.Column("q_regulatory_use", sa.SmallInteger, nullable=False),
        sa.Column("override_tier", sa.String(10)),
        sa.Column("override_reason", sa.Text),
        sa.Column("override_by", sa.String(20)),
        sa.Column("override_at", sa.DateTime(timezone=True)),
        *_ts(),
        sa.PrimaryKeyConstraint("model_id", name="pk_tiering_answer"),
        _fk("tiering_answer", "model_id", MODEL), _fk("tiering_answer", "override_by", USER),
        sa.CheckConstraint("q_materiality BETWEEN 1 AND 3 AND q_complexity BETWEEN 1 AND 3 AND "
                           "q_reliance BETWEEN 1 AND 3 AND q_regulatory_use BETWEEN 1 AND 3",
                           name="ck_tiering_answer_answers_1_to_3"),
    )

    op.create_table(
        "tier_override",
        sa.Column("override_id", sa.BigInteger, sa.Identity(always=False), nullable=False),
        sa.Column("model_id", sa.String(20), nullable=False),
        sa.Column("calculated_tier", sa.String(10), nullable=False),
        sa.Column("previous_tier", sa.String(10), nullable=False),
        sa.Column("new_tier", sa.String(10), nullable=False),
        sa.Column("reason", sa.Text, nullable=False),
        sa.Column("user_id", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("override_id", name="pk_tier_override"),
        _fk("tier_override", "model_id", MODEL), _fk("tier_override", "user_id", USER),
    )
    op.create_index("ix_tier_override_model_id", "tier_override", ["model_id"])

    op.create_table(
        "model_phase_history",
        sa.Column("transition_id", sa.BigInteger, sa.Identity(always=False), nullable=False),
        sa.Column("model_id", sa.String(20), nullable=False),
        sa.Column("from_phase", sa.String(40)),
        sa.Column("to_phase", sa.String(40), nullable=False),
        sa.Column("reason", sa.Text),
        sa.Column("user_id", sa.String(20)),
        sa.Column("changed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("transition_id", name="pk_model_phase_history"),
        _fk("model_phase_history", "model_id", MODEL), _fk("model_phase_history", "user_id", USER),
    )
    op.create_index("ix_model_phase_history_model_id", "model_phase_history", ["model_id"])

    op.create_table(
        "model_version",
        sa.Column("model_id", sa.String(20), nullable=False),
        sa.Column("version", sa.String(40), nullable=False),
        sa.Column("change_reason", sa.Text),
        sa.Column("user_id", sa.String(20)),
        sa.Column("recorded_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("model_id", "version", name="pk_model_version"),
        _fk("model_version", "model_id", MODEL), _fk("model_version", "user_id", USER),
    )

    op.create_table(
        "model_relationship",
        sa.Column("model_id", sa.String(20), nullable=False),
        sa.Column("related_model_id", sa.String(20), nullable=False),
        sa.Column("relationship_type", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("model_id", "related_model_id", "relationship_type", name="pk_model_relationship"),
        _fk("model_relationship", "model_id", MODEL), _fk("model_relationship", "related_model_id", MODEL),
    )
    op.create_index("ix_model_relationship_related_model_id", "model_relationship", ["related_model_id"])

    op.create_table(
        "validation",
        sa.Column("validation_id", sa.String(20), nullable=False),
        sa.Column("model_id", sa.String(20), nullable=False),
        sa.Column("validation_type", sa.String(40), nullable=False),
        sa.Column("validator_id", sa.String(20), nullable=False),
        sa.Column("start_date", sa.Date, nullable=False),
        sa.Column("completion_date", sa.Date),
        sa.Column("outcome", sa.String(40), nullable=False),
        sa.Column("summary", sa.Text),
        sa.Column("recommendations", sa.Text),
        sa.Column("report_document_id", sa.String(40)),
        sa.Column("source", sa.String(20), nullable=False),
        sa.Column("row_version", sa.Integer, nullable=False),
        *_ts(),
        sa.PrimaryKeyConstraint("validation_id", name="pk_validation"),
        _fk("validation", "model_id", MODEL), _fk("validation", "validator_id", USER),
    )
    for col in ("model_id", "validator_id", "outcome"):
        op.create_index(f"ix_validation_{col}", "validation", [col])

    op.create_table(
        "finding",
        sa.Column("finding_id", sa.String(20), nullable=False),
        sa.Column("model_id", sa.String(20), nullable=False),
        sa.Column("validation_id", sa.String(20)),
        sa.Column("title", sa.String(120), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column("category", sa.String(40), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("owner_id", sa.String(20), nullable=False),
        sa.Column("raised_date", sa.Date, nullable=False),
        sa.Column("due_date", sa.Date, nullable=False),
        sa.Column("closed_date", sa.Date),
        sa.Column("source", sa.String(20), nullable=False),
        sa.Column("evidence", sa.Text),
        sa.Column("root_cause", sa.Text),
        sa.Column("management_response", sa.Text),
        sa.Column("remediation_action", sa.Text),
        sa.Column("row_version", sa.Integer, nullable=False),
        *_ts(),
        sa.PrimaryKeyConstraint("finding_id", name="pk_finding"),
        _fk("finding", "model_id", MODEL), _fk("finding", "owner_id", USER),
        sa.ForeignKeyConstraint(["validation_id"], ["validation.validation_id"],
                                name="fk_finding_validation_id_validation"),
    )
    for col in ("validation_id", "severity", "status", "owner_id", "due_date"):
        op.create_index(f"ix_finding_{col}", "finding", [col])
    op.create_index("ix_finding_model_status", "finding", ["model_id", "status"])

    op.create_table(
        "approval",
        sa.Column("approval_id", sa.String(20), nullable=False),
        sa.Column("model_id", sa.String(20), nullable=False),
        sa.Column("decision_date", sa.Date, nullable=False),
        sa.Column("forum", sa.String(60), nullable=False),
        sa.Column("decision_type", sa.String(60), nullable=False),
        sa.Column("decision", sa.String(20), nullable=False),
        sa.Column("conditions", sa.Text),
        sa.Column("condition_due_date", sa.Date),
        sa.Column("condition_status", sa.String(10)),
        sa.Column("supporting_document_id", sa.String(40)),
        sa.Column("recorded_by", sa.String(20)),
        sa.Column("row_version", sa.Integer, nullable=False),
        *_ts(),
        sa.PrimaryKeyConstraint("approval_id", name="pk_approval"),
        _fk("approval", "model_id", MODEL), _fk("approval", "recorded_by", USER),
    )
    for col in ("model_id", "decision_date", "decision"):
        op.create_index(f"ix_approval_{col}", "approval", [col])


def downgrade() -> None:
    for table in ("approval", "finding", "validation", "model_relationship", "model_version",
                  "model_phase_history", "tier_override", "tiering_answer", "model"):
        op.drop_table(table)
