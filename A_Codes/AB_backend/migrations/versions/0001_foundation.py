"""Phase 1 foundation: app_user, user_role, policy_setting, audit_event.

Revision ID: 0001_foundation
Revises:
Create Date: 2026-09-30
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001_foundation"
down_revision = None
branch_labels = None
depends_on = None


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "app_user",
        sa.Column("user_id", sa.String(20), nullable=False),
        sa.Column("full_name", sa.String(120), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("business_line", sa.String(120)),
        sa.Column("active", sa.Boolean, nullable=False),
        sa.Column("row_version", sa.Integer, nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("user_id", name="pk_app_user"),
        sa.UniqueConstraint("email", name="uq_app_user_email"),
    )
    op.create_index("ix_app_user_active", "app_user", ["active"])

    op.create_table(
        "user_role",
        sa.Column("user_id", sa.String(20), nullable=False),
        sa.Column("role", sa.String(40), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["app_user.user_id"], name="fk_user_role_user_id_app_user"),
        sa.PrimaryKeyConstraint("user_id", "role", name="pk_user_role"),
    )

    op.create_table(
        "policy_setting",
        sa.Column("setting_key", sa.String(80), nullable=False),
        sa.Column("value", sa.Text, nullable=False),
        sa.Column("value_type", sa.String(20), nullable=False),
        sa.Column("category", sa.String(40)),
        sa.Column("description", sa.Text),
        sa.Column("updated_by", sa.String(20)),
        sa.Column("row_version", sa.Integer, nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("setting_key", name="pk_policy_setting"),
    )

    op.create_table(
        "audit_event",
        sa.Column("event_id", sa.BigInteger, sa.Identity(always=False), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("user_id", sa.String(20)),
        sa.Column("role", sa.String(40)),
        sa.Column("action", sa.String(40), nullable=False),
        sa.Column("entity", sa.String(60), nullable=False),
        sa.Column("entity_id", sa.String(120), nullable=False),
        sa.Column("model_id", sa.String(20)),
        sa.Column("import_batch_id", sa.String(40)),
        sa.Column("document_id", sa.String(40)),
        sa.Column("reason", sa.Text),
        sa.Column("before_json", postgresql.JSONB),
        sa.Column("after_json", postgresql.JSONB),
        sa.PrimaryKeyConstraint("event_id", name="pk_audit_event"),
    )
    for col in ("occurred_at", "user_id", "action", "model_id", "import_batch_id", "document_id"):
        op.create_index(f"ix_audit_event_{col}", "audit_event", [col])
    op.create_index("ix_audit_event_entity", "audit_event", ["entity", "entity_id"])

    # Audit records are immutable (BRD §58): reject UPDATE and DELETE at the database level.
    op.execute("""
        CREATE FUNCTION audit_event_immutable() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'audit_event is append-only; % is not allowed', TG_OP;
        END;
        $$ LANGUAGE plpgsql;
    """)
    op.execute("""
        CREATE TRIGGER trg_audit_event_immutable
        BEFORE UPDATE OR DELETE ON audit_event
        FOR EACH ROW EXECUTE FUNCTION audit_event_immutable();
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_audit_event_immutable ON audit_event")
    op.execute("DROP FUNCTION IF EXISTS audit_event_immutable()")
    op.drop_table("audit_event")
    op.drop_table("policy_setting")
    op.drop_table("user_role")
    op.drop_table("app_user")
