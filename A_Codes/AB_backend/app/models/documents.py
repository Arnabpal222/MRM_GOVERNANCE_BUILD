"""Document management tables (BRD §27–§40, §48).

PostgreSQL holds all metadata and the logical folder hierarchy; object storage holds only bytes.
"""
from datetime import date, datetime

from sqlalchemy import BigInteger, Boolean, Date, DateTime, Float, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BigIntId, Base, TimestampMixin, VersionedMixin


class DocumentFolder(Base):
    """Logical folder from an uploaded folder/ZIP, preserving hierarchy (BRD §31)."""

    __tablename__ = "document_folder"

    folder_id: Mapped[int] = mapped_column(BigIntId, primary_key=True, autoincrement=True)
    parent_folder_id: Mapped[int | None] = mapped_column(ForeignKey("document_folder.folder_id"), index=True)
    folder_name: Mapped[str] = mapped_column(String(255))
    relative_path: Mapped[str] = mapped_column(String(1024), unique=True)
    model_id: Mapped[str | None] = mapped_column(ForeignKey("model.model_id"), index=True)
    folder_type: Mapped[str | None] = mapped_column(String(60))
    description: Mapped[str | None] = mapped_column(Text)
    created_batch_id: Mapped[str | None] = mapped_column(String(40))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Document(TimestampMixin, VersionedMixin, Base):
    __tablename__ = "document"
    __table_args__ = (Index("ix_document_model_type", "model_id", "document_type"),)

    document_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    model_id: Mapped[str] = mapped_column(ForeignKey("model.model_id"))
    title: Mapped[str] = mapped_column(String(255))
    document_type: Mapped[str] = mapped_column(String(60), index=True)
    document_subtype: Mapped[str | None] = mapped_column(String(60))
    current_version: Mapped[str] = mapped_column(String(20))
    effective_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20), default="Active", index=True)  # Active | Archived
    folder_id: Mapped[int | None] = mapped_column(ForeignKey("document_folder.folder_id"), index=True)
    source: Mapped[str] = mapped_column(String(20))  # single | batch | folder | zip | seed
    classification_source: Mapped[str | None] = mapped_column(String(20))  # user | manifest | filename | folder
    classification_confidence: Mapped[float | None] = mapped_column(Float)
    classification_reason: Mapped[str | None] = mapped_column(Text)
    extraction_status: Mapped[str] = mapped_column(String(20), default="Not started")  # AI extraction: Phase 5
    review_status: Mapped[str] = mapped_column(String(20), default="Not required")
    confidentiality: Mapped[str] = mapped_column(String(20))
    retention_start: Mapped[date | None] = mapped_column(Date)
    retention_end: Mapped[date | None] = mapped_column(Date)
    legal_hold: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by: Mapped[str | None] = mapped_column(String(20))

    versions: Mapped[list["DocumentVersion"]] = relationship(
        back_populates="document", order_by="DocumentVersion.version_id.desc()", lazy="selectin")


class DocumentVersion(Base):
    """Every uploaded file is an immutable version; versions are never overwritten (BRD §36)."""

    __tablename__ = "document_version"
    __table_args__ = (Index("uq_document_version", "document_id", "version", unique=True),)

    version_id: Mapped[int] = mapped_column(BigIntId, primary_key=True, autoincrement=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("document.document_id"), index=True)
    version: Mapped[str] = mapped_column(String(20))
    file_name: Mapped[str] = mapped_column(String(255))
    relative_path: Mapped[str | None] = mapped_column(String(1024))
    file_type: Mapped[str] = mapped_column(String(10))
    mime_type: Mapped[str] = mapped_column(String(120))
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    checksum: Mapped[str] = mapped_column(String(64), index=True)  # SHA-256
    storage_key: Mapped[str] = mapped_column(String(1024))
    scan_status: Mapped[str] = mapped_column(String(20), default="Not scanned")
    change_reason: Mapped[str | None] = mapped_column(Text)
    import_batch_id: Mapped[str | None] = mapped_column(String(40), index=True)  # lineage
    uploaded_by: Mapped[str | None] = mapped_column(String(20))
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    document: Mapped[Document] = relationship(back_populates="versions")


class DocumentLink(Base):
    """Generic association between a document and a governance record (BRD §48 document_link)."""

    __tablename__ = "document_link"

    document_id: Mapped[str] = mapped_column(ForeignKey("document.document_id"), primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(30), primary_key=True)  # validation | finding | approval | …
    entity_id: Mapped[str] = mapped_column(String(40), primary_key=True, index=True)
    created_by: Mapped[str | None] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DocumentUploadItem(Base):
    """One file of a document batch, staged for classification review before it is stored (BRD §30, §33)."""

    __tablename__ = "document_upload_item"

    item_id: Mapped[int] = mapped_column(BigIntId, primary_key=True, autoincrement=True)
    batch_id: Mapped[str] = mapped_column(ForeignKey("import_batch.batch_id"), index=True)
    relative_path: Mapped[str] = mapped_column(String(1024))
    file_name: Mapped[str] = mapped_column(String(255))
    file_type: Mapped[str] = mapped_column(String(10))
    mime_type: Mapped[str | None] = mapped_column(String(120))
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    checksum: Mapped[str] = mapped_column(String(64), index=True)
    staging_key: Mapped[str] = mapped_column(String(1024))
    model_id: Mapped[str | None] = mapped_column(String(20))
    model_source: Mapped[str | None] = mapped_column(String(20))  # manifest | folder | filename | user
    document_type: Mapped[str | None] = mapped_column(String(60))
    type_source: Mapped[str | None] = mapped_column(String(20))
    type_confidence: Mapped[float | None] = mapped_column(Float)
    type_reason: Mapped[str | None] = mapped_column(Text)
    version: Mapped[str | None] = mapped_column(String(20))
    effective_date: Mapped[date | None] = mapped_column(Date)
    title: Mapped[str | None] = mapped_column(String(255))
    action: Mapped[str] = mapped_column(String(20), default="create")  # create | new_version | skip
    target_document_id: Mapped[str | None] = mapped_column(String(20))  # for new_version
    duplicate_kind: Mapped[str | None] = mapped_column(String(30))  # exact | in_batch | same_name
    duplicate_of: Mapped[str | None] = mapped_column(String(60))
    status: Mapped[str] = mapped_column(String(20), default="Uploaded")
    # Uploaded | Invalid | Needs mapping | Ready | Skipped | Stored | Failed
    error: Mapped[str | None] = mapped_column(Text)
    document_id: Mapped[str | None] = mapped_column(String(20))
    stored_version: Mapped[str | None] = mapped_column(String(20))
    row_order: Mapped[int] = mapped_column(Integer, default=0)
