"""Phase 4 Document Centre: document_folder, document, document_version, document_link, document_upload_item;
foreign keys from validation.report_document_id and approval.supporting_document_id to document.

Revision ID: 0004_documents
Revises: 0003_import_engine
Create Date: 2026-09-30
"""
import sqlalchemy as sa
from alembic import op

revision = "0004_documents"
down_revision = "0003_import_engine"
branch_labels = None
depends_on = None


def _id(name: str) -> sa.Column:
    return sa.Column(name, sa.BigInteger, sa.Identity(always=False), nullable=False)


def upgrade() -> None:
    op.create_table(
        "document_folder",
        _id("folder_id"),
        sa.Column("parent_folder_id", sa.BigInteger),
        sa.Column("folder_name", sa.String(255), nullable=False),
        sa.Column("relative_path", sa.String(1024), nullable=False),
        sa.Column("model_id", sa.String(20)),
        sa.Column("folder_type", sa.String(60)),
        sa.Column("description", sa.Text),
        sa.Column("created_batch_id", sa.String(40)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("folder_id", name="pk_document_folder"),
        sa.UniqueConstraint("relative_path", name="uq_document_folder_relative_path"),
        sa.ForeignKeyConstraint(["parent_folder_id"], ["document_folder.folder_id"],
                                name="fk_document_folder_parent_folder_id_document_folder"),
        sa.ForeignKeyConstraint(["model_id"], ["model.model_id"], name="fk_document_folder_model_id_model"),
    )
    op.create_index("ix_document_folder_parent_folder_id", "document_folder", ["parent_folder_id"])
    op.create_index("ix_document_folder_model_id", "document_folder", ["model_id"])

    op.create_table(
        "document",
        sa.Column("document_id", sa.String(20), nullable=False),
        sa.Column("model_id", sa.String(20), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("document_type", sa.String(60), nullable=False),
        sa.Column("document_subtype", sa.String(60)),
        sa.Column("current_version", sa.String(20), nullable=False),
        sa.Column("effective_date", sa.Date),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("folder_id", sa.BigInteger),
        sa.Column("source", sa.String(20), nullable=False),
        sa.Column("classification_source", sa.String(20)),
        sa.Column("classification_confidence", sa.Float),
        sa.Column("classification_reason", sa.Text),
        sa.Column("extraction_status", sa.String(20), nullable=False),
        sa.Column("review_status", sa.String(20), nullable=False),
        sa.Column("confidentiality", sa.String(20), nullable=False),
        sa.Column("retention_start", sa.Date),
        sa.Column("retention_end", sa.Date),
        sa.Column("legal_hold", sa.Boolean, nullable=False),
        sa.Column("created_by", sa.String(20)),
        sa.Column("row_version", sa.Integer, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("document_id", name="pk_document"),
        sa.ForeignKeyConstraint(["model_id"], ["model.model_id"], name="fk_document_model_id_model"),
        sa.ForeignKeyConstraint(["folder_id"], ["document_folder.folder_id"], name="fk_document_folder_id_document_folder"),
    )
    op.create_index("ix_document_model_type", "document", ["model_id", "document_type"])
    for col in ("document_type", "status", "folder_id"):
        op.create_index(f"ix_document_{col}", "document", [col])

    op.create_table(
        "document_version",
        _id("version_id"),
        sa.Column("document_id", sa.String(20), nullable=False),
        sa.Column("version", sa.String(20), nullable=False),
        sa.Column("file_name", sa.String(255), nullable=False),
        sa.Column("relative_path", sa.String(1024)),
        sa.Column("file_type", sa.String(10), nullable=False),
        sa.Column("mime_type", sa.String(120), nullable=False),
        sa.Column("size_bytes", sa.BigInteger, nullable=False),
        sa.Column("checksum", sa.String(64), nullable=False),
        sa.Column("storage_key", sa.String(1024), nullable=False),
        sa.Column("scan_status", sa.String(20), nullable=False),
        sa.Column("change_reason", sa.Text),
        sa.Column("import_batch_id", sa.String(40)),
        sa.Column("uploaded_by", sa.String(20)),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("version_id", name="pk_document_version"),
        sa.ForeignKeyConstraint(["document_id"], ["document.document_id"], name="fk_document_version_document_id_document"),
    )
    op.create_index("uq_document_version", "document_version", ["document_id", "version"], unique=True)
    for col in ("document_id", "checksum", "import_batch_id"):
        op.create_index(f"ix_document_version_{col}", "document_version", [col])

    op.create_table(
        "document_link",
        sa.Column("document_id", sa.String(20), nullable=False),
        sa.Column("entity_type", sa.String(30), nullable=False),
        sa.Column("entity_id", sa.String(40), nullable=False),
        sa.Column("created_by", sa.String(20)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("document_id", "entity_type", "entity_id", name="pk_document_link"),
        sa.ForeignKeyConstraint(["document_id"], ["document.document_id"], name="fk_document_link_document_id_document"),
    )
    op.create_index("ix_document_link_entity_id", "document_link", ["entity_id"])

    op.create_table(
        "document_upload_item",
        _id("item_id"),
        sa.Column("batch_id", sa.String(40), nullable=False),
        sa.Column("relative_path", sa.String(1024), nullable=False),
        sa.Column("file_name", sa.String(255), nullable=False),
        sa.Column("file_type", sa.String(10), nullable=False),
        sa.Column("mime_type", sa.String(120)),
        sa.Column("size_bytes", sa.BigInteger, nullable=False),
        sa.Column("checksum", sa.String(64), nullable=False),
        sa.Column("staging_key", sa.String(1024), nullable=False),
        sa.Column("model_id", sa.String(20)),
        sa.Column("model_source", sa.String(20)),
        sa.Column("document_type", sa.String(60)),
        sa.Column("type_source", sa.String(20)),
        sa.Column("type_confidence", sa.Float),
        sa.Column("type_reason", sa.Text),
        sa.Column("version", sa.String(20)),
        sa.Column("effective_date", sa.Date),
        sa.Column("title", sa.String(255)),
        sa.Column("action", sa.String(20), nullable=False),
        sa.Column("target_document_id", sa.String(20)),
        sa.Column("duplicate_kind", sa.String(30)),
        sa.Column("duplicate_of", sa.String(60)),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("error", sa.Text),
        sa.Column("document_id", sa.String(20)),
        sa.Column("stored_version", sa.String(20)),
        sa.Column("row_order", sa.Integer, nullable=False),
        sa.PrimaryKeyConstraint("item_id", name="pk_document_upload_item"),
        sa.ForeignKeyConstraint(["batch_id"], ["import_batch.batch_id"], name="fk_document_upload_item_batch_id_import_batch"),
    )
    op.create_index("ix_document_upload_item_batch_id", "document_upload_item", ["batch_id"])
    op.create_index("ix_document_upload_item_checksum", "document_upload_item", ["checksum"])

    op.create_foreign_key("fk_validation_report_document_id_document", "validation", "document",
                          ["report_document_id"], ["document_id"])
    op.create_foreign_key("fk_approval_supporting_document_id_document", "approval", "document",
                          ["supporting_document_id"], ["document_id"])


def downgrade() -> None:
    op.drop_constraint("fk_approval_supporting_document_id_document", "approval", type_="foreignkey")
    op.drop_constraint("fk_validation_report_document_id_document", "validation", type_="foreignkey")
    for table in ("document_upload_item", "document_link", "document_version", "document", "document_folder"):
        op.drop_table(table)
