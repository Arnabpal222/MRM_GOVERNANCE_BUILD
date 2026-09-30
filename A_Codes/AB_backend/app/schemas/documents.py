from datetime import date, datetime

from pydantic import BaseModel, ConfigDict

from app.schemas.ingestion import ImportBatchOut


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class DocumentVersionOut(ORMModel):
    version_id: int
    version: str
    file_name: str
    relative_path: str | None
    file_type: str
    mime_type: str
    size_bytes: int
    checksum: str
    scan_status: str
    change_reason: str | None
    import_batch_id: str | None
    uploaded_by: str | None
    uploaded_at: datetime


class DocumentOut(ORMModel):
    document_id: str
    model_id: str
    title: str
    document_type: str
    document_subtype: str | None
    current_version: str
    effective_date: date | None
    status: str
    folder_id: int | None
    source: str
    classification_source: str | None
    classification_confidence: float | None
    classification_reason: str | None
    extraction_status: str
    review_status: str
    confidentiality: str
    retention_start: date | None
    retention_end: date | None
    legal_hold: bool
    created_by: str | None
    created_at: datetime | None
    updated_at: datetime | None
    row_version: int


class DocumentSummaryOut(DocumentOut):
    file_name: str
    size_bytes: int
    uploaded_at: datetime
    folder_path: str | None = None


class DocumentLinkOut(ORMModel):
    entity_type: str
    entity_id: str
    created_by: str | None
    created_at: datetime


class DocumentDetailOut(DocumentOut):
    versions: list[DocumentVersionOut]
    links: list[DocumentLinkOut]
    folder_path: str | None


class FolderOut(ORMModel):
    folder_id: int
    parent_folder_id: int | None
    folder_name: str
    relative_path: str
    model_id: str | None
    folder_type: str | None
    document_count: int = 0


class CompletenessOut(BaseModel):
    model_id: str
    model_name: str
    lifecycle_phase: str
    required: list[str]
    present: list[str]
    missing: list[str]
    score: float | None


class DocumentMetaOut(BaseModel):
    document_types: list[str]
    confidentiality_levels: list[str]
    default_confidentiality: str
    extensions: list[str]
    max_document_mb: int
    max_zip_mb: int
    max_files: int


class UploadItemOut(ORMModel):
    item_id: int
    relative_path: str
    file_name: str
    file_type: str
    size_bytes: int
    checksum: str
    model_id: str | None
    model_source: str | None
    document_type: str | None
    type_source: str | None
    type_confidence: float | None
    type_reason: str | None
    version: str | None
    effective_date: date | None
    title: str | None
    action: str
    target_document_id: str | None
    duplicate_kind: str | None
    duplicate_of: str | None
    status: str
    error: str | None
    document_id: str | None
    stored_version: str | None


class DocumentBatchOut(ImportBatchOut):
    items: list[UploadItemOut]
    progress: dict | None
    manifest_errors: list[str]
    manifest_files: list[str]


class ItemUpdate(BaseModel):
    item_ids: list[int]
    model_id: str | None = None
    document_type: str | None = None
    version: str | None = None
    effective_date: date | None = None
    title: str | None = None
    action: str | None = None


class ArchiveRequest(BaseModel):
    reason: str


class LegalHoldRequest(BaseModel):
    hold: bool
    reason: str


class LinkCreate(BaseModel):
    entity_type: str
    entity_id: str
