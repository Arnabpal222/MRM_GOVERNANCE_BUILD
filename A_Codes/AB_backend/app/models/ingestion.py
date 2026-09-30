"""Import batches, files and row-level issues (BRD §42–§47)."""
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BigIntId, Base, JsonType, TimestampMixin

BATCH_STATUSES = ("Uploaded", "Validating", "Validation Failed", "Ready", "Processing", "Partially Completed",
                  "Completed", "Failed", "Cancelled")


class ImportBatch(TimestampMixin, Base):
    __tablename__ = "import_batch"

    batch_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    batch_type: Mapped[str] = mapped_column(String(20))  # structured | seed
    source: Mapped[str] = mapped_column(String(40))  # upload | reset | cli
    # Plain user id (no FK): batch history must survive a demo reset that reloads users.
    uploaded_by: Mapped[str | None] = mapped_column(String(20), index=True)
    status: Mapped[str] = mapped_column(String(30), index=True)
    options: Mapped[dict] = mapped_column(JsonType, default=dict)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    total_files: Mapped[int] = mapped_column(Integer, default=0)
    successful_files: Mapped[int] = mapped_column(Integer, default=0)
    failed_files: Mapped[int] = mapped_column(Integer, default=0)
    total_records: Mapped[int] = mapped_column(Integer, default=0)
    successful_records: Mapped[int] = mapped_column(Integer, default=0)
    failed_records: Mapped[int] = mapped_column(Integer, default=0)
    warning_count: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text)

    files: Mapped[list["ImportFile"]] = relationship(back_populates="batch", order_by="ImportFile.import_file_id",
                                                     cascade="all, delete-orphan")


class ImportFile(Base):
    __tablename__ = "import_file"

    import_file_id: Mapped[int] = mapped_column(BigIntId, primary_key=True, autoincrement=True)
    batch_id: Mapped[str] = mapped_column(ForeignKey("import_batch.batch_id"), index=True)
    file_name: Mapped[str] = mapped_column(String(255))
    relative_path: Mapped[str] = mapped_column(String(1024))
    checksum: Mapped[str] = mapped_column(String(64), index=True)  # SHA-256
    file_type: Mapped[str] = mapped_column(String(10))
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    storage_key: Mapped[str] = mapped_column(String(1024))
    template_id: Mapped[str | None] = mapped_column(String(10))
    template_source: Mapped[str | None] = mapped_column(String(20))  # filename | header | user
    sheet_name: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(30))
    file_error: Mapped[str | None] = mapped_column(Text)
    rows_total: Mapped[int] = mapped_column(Integer, default=0)
    rows_valid: Mapped[int] = mapped_column(Integer, default=0)
    rows_invalid: Mapped[int] = mapped_column(Integer, default=0)
    rows_new: Mapped[int] = mapped_column(Integer, default=0)
    rows_update: Mapped[int] = mapped_column(Integer, default=0)
    rows_unchanged: Mapped[int] = mapped_column(Integer, default=0)
    rows_loaded: Mapped[int] = mapped_column(Integer, default=0)
    error_count: Mapped[int] = mapped_column(Integer, default=0)
    warning_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    batch: Mapped[ImportBatch] = relationship(back_populates="files")


class ImportIssue(Base):
    """Row-level (or file-level when row_number is null) error or warning."""

    __tablename__ = "import_issue"
    __table_args__ = (Index("ix_import_issue_batch_file", "batch_id", "import_file_id"),)

    issue_id: Mapped[int] = mapped_column(BigIntId, primary_key=True, autoincrement=True)
    batch_id: Mapped[str] = mapped_column(ForeignKey("import_batch.batch_id"))
    import_file_id: Mapped[int] = mapped_column(ForeignKey("import_file.import_file_id"))
    stage: Mapped[str] = mapped_column(String(10))  # validate | load
    severity: Mapped[str] = mapped_column(String(10))  # error | warning
    sheet: Mapped[str | None] = mapped_column(String(100))
    row_number: Mapped[int | None] = mapped_column(Integer)
    column_name: Mapped[str | None] = mapped_column(String(100))
    error_type: Mapped[str] = mapped_column(String(30))
    message: Mapped[str] = mapped_column(Text)
    original_value: Mapped[str | None] = mapped_column(Text)
