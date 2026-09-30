"""Phase 3 import engine: import_batch, import_file, import_issue.

Revision ID: 0003_import_engine
Revises: 0002_governance_core
Create Date: 2026-09-30
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0003_import_engine"
down_revision = "0002_governance_core"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "import_batch",
        sa.Column("batch_id", sa.String(40), nullable=False),
        sa.Column("batch_type", sa.String(20), nullable=False),
        sa.Column("source", sa.String(40), nullable=False),
        sa.Column("uploaded_by", sa.String(20)),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("options", postgresql.JSONB, nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("validated_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("total_files", sa.Integer, nullable=False),
        sa.Column("successful_files", sa.Integer, nullable=False),
        sa.Column("failed_files", sa.Integer, nullable=False),
        sa.Column("total_records", sa.Integer, nullable=False),
        sa.Column("successful_records", sa.Integer, nullable=False),
        sa.Column("failed_records", sa.Integer, nullable=False),
        sa.Column("warning_count", sa.Integer, nullable=False),
        sa.Column("error_message", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("batch_id", name="pk_import_batch"),
    )
    op.create_index("ix_import_batch_uploaded_by", "import_batch", ["uploaded_by"])
    op.create_index("ix_import_batch_status", "import_batch", ["status"])

    op.create_table(
        "import_file",
        sa.Column("import_file_id", sa.BigInteger, sa.Identity(always=False), nullable=False),
        sa.Column("batch_id", sa.String(40), nullable=False),
        sa.Column("file_name", sa.String(255), nullable=False),
        sa.Column("relative_path", sa.String(1024), nullable=False),
        sa.Column("checksum", sa.String(64), nullable=False),
        sa.Column("file_type", sa.String(10), nullable=False),
        sa.Column("size_bytes", sa.BigInteger, nullable=False),
        sa.Column("storage_key", sa.String(1024), nullable=False),
        sa.Column("template_id", sa.String(10)),
        sa.Column("template_source", sa.String(20)),
        sa.Column("sheet_name", sa.String(100)),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("file_error", sa.Text),
        *[sa.Column(c, sa.Integer, nullable=False) for c in (
            "rows_total", "rows_valid", "rows_invalid", "rows_new", "rows_update", "rows_unchanged", "rows_loaded",
            "error_count", "warning_count")],
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("import_file_id", name="pk_import_file"),
        sa.ForeignKeyConstraint(["batch_id"], ["import_batch.batch_id"], name="fk_import_file_batch_id_import_batch"),
    )
    op.create_index("ix_import_file_batch_id", "import_file", ["batch_id"])
    op.create_index("ix_import_file_checksum", "import_file", ["checksum"])

    op.create_table(
        "import_issue",
        sa.Column("issue_id", sa.BigInteger, sa.Identity(always=False), nullable=False),
        sa.Column("batch_id", sa.String(40), nullable=False),
        sa.Column("import_file_id", sa.BigInteger, nullable=False),
        sa.Column("stage", sa.String(10), nullable=False),
        sa.Column("severity", sa.String(10), nullable=False),
        sa.Column("sheet", sa.String(100)),
        sa.Column("row_number", sa.Integer),
        sa.Column("column_name", sa.String(100)),
        sa.Column("error_type", sa.String(30), nullable=False),
        sa.Column("message", sa.Text, nullable=False),
        sa.Column("original_value", sa.Text),
        sa.PrimaryKeyConstraint("issue_id", name="pk_import_issue"),
        sa.ForeignKeyConstraint(["batch_id"], ["import_batch.batch_id"], name="fk_import_issue_batch_id_import_batch"),
        sa.ForeignKeyConstraint(["import_file_id"], ["import_file.import_file_id"],
                                name="fk_import_issue_import_file_id_import_file"),
    )
    op.create_index("ix_import_issue_batch_file", "import_issue", ["batch_id", "import_file_id"])


def downgrade() -> None:
    op.drop_table("import_issue")
    op.drop_table("import_file")
    op.drop_table("import_batch")
