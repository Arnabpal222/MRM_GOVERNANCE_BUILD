"""Import Centre service: batches, files, status transitions, error reports (BRD §42–§47)."""
import csv
import hashlib
import io
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import PurePosixPath

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.audit import service as audit
from app.auth.roles import Permission, has_permission
from app.auth.security import Principal
from app.clock import today
from app.ingestion import checks, engine, fileio
from app.ingestion.adapters import ON_EXISTING
from app.ingestion.registry import get_template
from app.models import ImportBatch, ImportFile, ImportIssue
from app.services.errors import ConflictError, ForbiddenError, NotFoundError, ValidationFailedError
from app.services.policy_access import Policy
from app.storage import get_store
from app.workers import runner

ALLOWED_EXT = (".xlsx", ".csv")
EDITABLE = ("Uploaded", "Ready", "Validation Failed", "Failed")
RUNNING = ("Validating", "Processing")


def _require_import(principal: Principal | None) -> None:
    if principal and not has_permission(principal.role, Permission.IMPORT_RUN):
        raise ForbiddenError(f"Role '{principal.role}' is not permitted to import data (import:run).")


def _new_batch_id(db: Session) -> str:
    prefix = f"B-{today():%Y%m%d}-"
    current = db.scalar(select(func.max(ImportBatch.batch_id)).where(ImportBatch.batch_id.like(f"{prefix}%")))
    n = int(current.rsplit("-", 1)[1]) + 1 if current else 1
    return f"{prefix}{n:03d}"


def safe_relative_path(name: str) -> str:
    """Normalise a client-supplied (relative) path; reject traversal."""
    p = PurePosixPath(name.replace("\\", "/"))
    parts = [x for x in p.parts if x not in ("", ".")]
    if not parts or p.is_absolute() or ".." in parts:
        raise ValidationFailedError(f"'{name}' is not an acceptable file path.")
    return "/".join(parts)


def get_batch(db: Session, batch_id: str) -> ImportBatch:
    b = db.get(ImportBatch, batch_id)
    if b is None or b.batch_type == "documents":
        raise NotFoundError(f"Import batch {batch_id} does not exist.")
    return b


def list_batches(db: Session, limit: int = 100) -> list[ImportBatch]:
    """Structured import batches (document batches are listed in the Document Centre)."""
    return list(db.scalars(select(ImportBatch).where(ImportBatch.batch_type != "documents")
                           .order_by(ImportBatch.created_at.desc(), ImportBatch.batch_id.desc()).limit(limit)))


def create_batch(db: Session, principal: Principal | None, uploads: list[tuple[str, bytes]], *,
                 on_existing: str = "update", source: str = "upload", batch_type: str = "structured") -> ImportBatch:
    """uploads: (file name or relative path, bytes). Stores files, detects templates, records the batch."""
    _require_import(principal)
    if on_existing not in ON_EXISTING:
        raise ValidationFailedError(f"on_existing must be one of {', '.join(ON_EXISTING)}.")
    if not uploads:
        raise ValidationFailedError("Choose at least one file to import.")
    # User uploads are limited by policy. System seed batches run while policy itself is being (re)loaded.
    limits = None
    if source == "upload":
        policy = Policy.load(db)
        limits = (policy.int("import_max_files"), policy.int("import_max_file_mb"), policy.int("import_max_rows"))
        if len(uploads) > limits[0]:
            raise ValidationFailedError(f"A batch can contain at most {limits[0]} files.")
    for name, data in uploads:
        if not name.lower().endswith(ALLOWED_EXT):
            raise ValidationFailedError(f"{name}: only .xlsx and .csv files can be imported here. "
                                        "Documents go to the Document Centre.")
        if limits and len(data) > limits[1] * 1024 * 1024:
            raise ValidationFailedError(f"{name} is larger than the {limits[1]} MB limit.")

    batch_id = _new_batch_id(db)
    batch = ImportBatch(batch_id=batch_id, batch_type=batch_type, source=source, status="Uploaded",
                        uploaded_by=principal.user_id if principal else None,
                        options={"on_existing": on_existing, "role": principal.role if principal else None},
                        started_at=datetime.now(UTC), total_files=len(uploads))
    db.add(batch)
    store = get_store()
    for name, data in uploads:
        rel = safe_relative_path(name)
        file_name = PurePosixPath(rel).name
        checksum = hashlib.sha256(data).hexdigest()
        key = f"imports/{batch_id}/{rel}"
        store.put(key, data, "text/csv" if file_name.lower().endswith(".csv") else
                  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        template_id = source_ = sheet = None
        try:
            parsed = fileio.parse(file_name, data)
            template_id, source_ = checks.detect_template(file_name, parsed.headers)
            sheet = parsed.sheet
            if limits and len(parsed.rows) > limits[2]:
                raise ValidationFailedError(f"{file_name} has more than {limits[2]} rows.")
        except fileio.FileFormatError:
            pass  # reported as a file error when the batch is validated
        batch.files.append(ImportFile(file_name=file_name, relative_path=rel, checksum=checksum,
                                      file_type=PurePosixPath(file_name).suffix.lstrip(".").lower(),
                                      size_bytes=len(data), storage_key=key, template_id=template_id,
                                      template_source=source_, sheet_name=sheet, status="Uploaded"))
    audit.record(db, principal, action="upload", entity="import_batch", entity_id=batch_id, import_batch_id=batch_id,
                 after={"files": [n for n, _ in uploads], "on_existing": on_existing, "source": source})
    db.commit()
    return batch


def set_file_template(db: Session, principal: Principal, file_id: int, template_id: str | None) -> ImportFile:
    _require_import(principal)
    f = db.get(ImportFile, file_id)
    if f is None:
        raise NotFoundError(f"Import file {file_id} does not exist.")
    batch = f.batch
    if batch.status not in EDITABLE:
        raise ConflictError(f"Batch {batch.batch_id} is {batch.status}; its files can no longer be remapped.")
    if template_id is not None:
        t = get_template(template_id)
        if t is None or not t.available or t.channel != "import":
            raise ValidationFailedError(f"Template {template_id} is not available in the Import Centre.")
    before = f.template_id
    f.template_id, f.template_source, f.status = template_id, "user", "Uploaded"
    batch.status = "Uploaded"
    audit.record(db, principal, action="update", entity="import_file", entity_id=str(file_id),
                 import_batch_id=batch.batch_id, before={"template_id": before}, after={"template_id": template_id})
    db.commit()
    return f


def start(db: Session, session_factory: Callable[[], Session], principal: Principal | None, batch_id: str,
          mode: str) -> ImportBatch:
    """Queue validation or load. Loading requires a validated batch and re-checks every row."""
    _require_import(principal)
    batch = get_batch(db, batch_id)
    if batch.status in RUNNING:
        raise ConflictError(f"Batch {batch_id} is already {batch.status.lower()}.")
    if mode == "validate":
        if batch.status not in EDITABLE:
            raise ConflictError(f"Batch {batch_id} is {batch.status}; it cannot be validated again.")
        batch.status = "Validating"
    else:
        if batch.status not in ("Ready", "Failed") and not (batch.source != "upload" and batch.status == "Uploaded"):
            raise ConflictError(f"Batch {batch_id} is {batch.status}. Validate it and review the preview before loading.")
        batch.status = "Processing"
        audit.record(db, principal, action="import", entity="import_batch", entity_id=batch_id,
                     import_batch_id=batch_id, after={"status": "Processing"})
    db.commit()
    runner.submit(engine.run, session_factory, batch_id, mode, principal)
    db.expire_all()
    return get_batch(db, batch_id)


def cancel(db: Session, principal: Principal, batch_id: str) -> ImportBatch:
    _require_import(principal)
    batch = get_batch(db, batch_id)
    if batch.status not in EDITABLE:
        raise ConflictError(f"Batch {batch_id} is {batch.status} and cannot be cancelled.")
    batch.status = "Cancelled"
    audit.record(db, principal, action="cancel", entity="import_batch", entity_id=batch_id, import_batch_id=batch_id)
    db.commit()
    return batch


def issues(db: Session, batch_id: str, file_id: int | None = None, limit: int = 500) -> list[ImportIssue]:
    q = select(ImportIssue).where(ImportIssue.batch_id == batch_id)
    if file_id:
        q = q.where(ImportIssue.import_file_id == file_id)
    q = q.order_by(ImportIssue.import_file_id, ImportIssue.row_number.nulls_first(), ImportIssue.issue_id).limit(limit)
    return list(db.scalars(q))


def error_report_csv(db: Session, batch_id: str) -> bytes:
    """BRD §44: file, sheet, row, column, error type, message, original value."""
    get_batch(db, batch_id)
    names = {f.import_file_id: f.file_name for f in get_batch(db, batch_id).files}
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["file", "sheet", "row", "column", "severity", "error_type", "message", "original_value"])
    for i in issues(db, batch_id, limit=1_000_000):
        w.writerow([names.get(i.import_file_id, ""), i.sheet or "", i.row_number or "", i.column_name or "",
                    i.severity, i.error_type, i.message, i.original_value or ""])
    return buf.getvalue().encode("utf-8-sig")


def duplicate_of(db: Session, f: ImportFile) -> str | None:
    """An identical file (same SHA-256) already loaded in another batch, if any."""
    return db.scalar(select(ImportFile.batch_id).where(
        ImportFile.checksum == f.checksum, ImportFile.batch_id != f.batch_id,
        ImportFile.status.in_(("Loaded", "Partially loaded"))).limit(1))
