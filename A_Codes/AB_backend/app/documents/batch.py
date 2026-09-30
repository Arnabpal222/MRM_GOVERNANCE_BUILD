"""Batch, folder and ZIP document uploads (BRD §30–§35, §74–§75).

Upload → stage bytes → analyse in the background (validate, checksum, detect model and type, find
duplicates and versions) → user reviews and corrects the mapping → Confirm → store in the background.
Nothing becomes a governance document before Confirm. A failing file never stops the others (DOC-10).
"""
import csv
import hashlib
import io
import re
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import PurePosixPath

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.audit import service as audit
from app.auth.roles import Permission, has_permission
from app.auth.security import Principal
from app.documents import files
from app.documents import service as doc_service
from app.ingestion import checks, fileio
from app.ingestion import service as import_service
from app.ingestion.registry import get_template
from app.models import DocumentUploadItem, ImportBatch, Model
from app.rules import document_rules
from app.services.errors import ConflictError, ForbiddenError, NotFoundError, ServiceError, ValidationFailedError
from app.services.policy_access import Policy
from app.storage import get_store
from app.workers import runner
from app.workers.runner import progress

EDITABLE = ("Ready", "Validation Failed", "Failed")
ACTIONS = ("create", "new_version", "skip")


def _require(principal: Principal | None) -> None:
    if principal and not has_permission(principal.role, Permission.DOCUMENT_UPLOAD):
        raise ForbiddenError(f"Role '{principal.role}' is not permitted to upload documents.")


def _is_manifest(path: str) -> bool:
    name = PurePosixPath(path).name.lower()
    return name.endswith((".xlsx", ".csv")) and (name.startswith("manifest") or name.startswith(("t17", "t18")))


def _parse_manifests(db: Session, manifests: list[tuple[str, bytes]]) -> dict:
    """T17 rows by relative path, T18 folder → model, and any errors (BRD §33 Method D)."""
    out = {"documents": {}, "folders": {}, "errors": []}
    policy = Policy.load(db)
    for path, data in manifests:
        try:
            parsed = fileio.parse(PurePosixPath(path).name, data)
        except fileio.FileFormatError as exc:
            out["errors"].append(f"{path}: {exc}")
            continue
        tid, _ = checks.detect_template(PurePosixPath(path).name, parsed.headers, channel="documents")
        template = get_template(tid) if tid else None
        if template is None:
            out["errors"].append(f"{path}: not a T17 document manifest or T18 folder manifest (check the columns).")
            continue
        base = str(PurePosixPath(path).parent)
        allowed = checks.allowed_values(template, policy)
        for i, raw in enumerate(parsed.rows, start=2):
            typed, issues = checks.convert_row(db, template, raw, allowed, i)
            if issues:
                out["errors"] += [f"{path} row {i}: {x.message}" for x in issues]
                continue
            rel = typed["relative_path"].strip("/")
            keys = {rel} | ({f"{base}/{rel}"} if base != "." else set())
            for k in keys:
                if tid == "T17":
                    out["documents"][k] = {k2: (v.isoformat() if hasattr(v, "isoformat") else v)
                                           for k2, v in typed.items()}
                elif typed.get("model_id"):
                    out["folders"][k] = typed["model_id"]
    return out


def create_batch(db: Session, session_factory: Callable[[], Session], principal: Principal | None,
                 uploads: list[tuple[str, bytes]], *, source: str = "batch", auto_confirm: bool = False) -> ImportBatch:
    """uploads: (relative path, bytes); .zip entries are expanded safely. Analysis starts in the background."""
    _require(principal)
    if not uploads:
        raise ValidationFailedError("Choose at least one file or folder to upload.")
    dp = doc_service.DocPolicy.load(Policy.load(db))
    staged: list[tuple[str, bytes]] = []
    for name, data in uploads:
        rel = import_service.safe_relative_path(name)
        if rel.lower().endswith(".zip"):
            if len(data) > dp.max_zip_bytes:
                raise ValidationFailedError(f"{rel} is larger than the ZIP limit of {dp.max_zip_bytes // 1048576} MB.")
            try:
                staged += files.expand_zip(data, dp.zip_limits)
            except files.FileRejected as exc:
                raise ValidationFailedError(f"{rel}: {exc}") from None
            source = "zip"
        else:
            staged.append((rel, data))
    if principal is not None and len(staged) > dp.zip_limits.max_files:  # system seed loads are not capped
        raise ValidationFailedError(f"A batch can contain at most {dp.zip_limits.max_files} files.")

    manifests = [(p, d) for p, d in staged if _is_manifest(p)]
    docs = [(p, d) for p, d in staged if not _is_manifest(p)]
    if not docs:
        raise ValidationFailedError("The upload contains no documents.")
    batch = ImportBatch(batch_id=import_service._new_batch_id(db), batch_type="documents", source=source,
                        status="Validating", uploaded_by=principal.user_id if principal else None,
                        options={"role": principal.role if principal else None, "auto_confirm": auto_confirm,
                                 "manifest": _parse_manifests(db, manifests) if manifests else None,
                                 "manifest_files": [p for p, _ in manifests]},
                        started_at=datetime.now(UTC), total_files=len(docs))
    db.add(batch)
    db.flush()  # items reference the batch by id only
    store = get_store()
    seen: set[str] = set()
    for order, (rel, data) in enumerate(docs):
        key = f"staging/{batch.batch_id}/{rel}"
        store.put(key, data)
        item = DocumentUploadItem(batch_id=batch.batch_id, relative_path=rel, file_name=PurePosixPath(rel).name,
                                  file_type=files.extension(rel), size_bytes=len(data),
                                  checksum=hashlib.sha256(data).hexdigest(), staging_key=key, row_order=order)
        if rel in seen:
            item.status, item.error = "Invalid", "The same path appears twice in this upload."
        else:  # file checks while the bytes are in memory (BRD §65)
            try:
                item.mime_type = files.validate_document(rel, data, dp.extensions, dp.max_bytes)
            except files.FileRejected as exc:
                item.status, item.error = "Invalid", str(exc)
        seen.add(rel)
        db.add(item)
    audit.record(db, principal, action="upload", entity="document_batch", entity_id=batch.batch_id,
                 import_batch_id=batch.batch_id, after={"files": len(docs), "manifests": len(manifests),
                                                        "source": source})
    db.commit()
    runner.submit(analyse_job, session_factory, batch.batch_id, principal)
    return batch


def _items(db: Session, batch_id: str) -> list[DocumentUploadItem]:
    return list(db.scalars(select(DocumentUploadItem).where(DocumentUploadItem.batch_id == batch_id)
                           .order_by(DocumentUploadItem.row_order)))


def _resolve(db: Session, item: DocumentUploadItem, principal: Principal | None) -> None:
    """Recompute duplicate/version status and readiness after detection or a user change."""
    if item.status in ("Invalid", "Stored"):
        return
    item.error = None
    item.duplicate_kind = item.duplicate_of = item.target_document_id = None
    dup = doc_service.find_by_checksum(db, item.checksum)
    if dup is not None:
        item.duplicate_kind, item.duplicate_of = "exact", f"{dup.document_id} v{dup.version}"
        if item.action == "create":
            item.action = "skip"  # exact re-upload: not stored unless the user asks for a new version (BRD §35)
    else:
        earlier = db.scalar(select(DocumentUploadItem).where(
            DocumentUploadItem.batch_id == item.batch_id, DocumentUploadItem.checksum == item.checksum,
            DocumentUploadItem.row_order < item.row_order).limit(1))
        if earlier is not None:
            item.duplicate_kind, item.duplicate_of = "in_batch", earlier.relative_path
            if item.action == "create":
                item.action = "skip"
    if item.action == "skip":
        item.status = "Skipped"
        return
    model = db.get(Model, item.model_id) if item.model_id else None
    if item.model_id and model is None:
        item.status, item.error = "Needs mapping", f"Model {item.model_id} does not exist."
        return
    if model is None or not item.document_type:
        item.status = "Needs mapping"
        item.error = "Choose the model." if model is None else "Choose the document type."
        return
    reason = doc_service.can_upload_for(principal, model)
    if reason:
        item.status, item.error = "Needs mapping", reason
        return
    same = doc_service.find_same_document(db, model.model_id, item.document_type,
                                          item.title or document_rules.title_from_file(item.file_name))
    if same is not None:
        item.action, item.target_document_id = "new_version", same.document_id
        if item.duplicate_kind is None:
            item.duplicate_kind, item.duplicate_of = "same_name", f"{same.document_id} v{same.current_version}"
    elif item.action == "new_version" and item.duplicate_kind == "exact":
        item.target_document_id = item.duplicate_of.split(" ")[0]
    elif item.action == "new_version":
        item.action = "create"
    item.status = "Ready"


def analyse_job(session_factory: Callable[[], Session], batch_id: str, principal: Principal | None) -> None:
    with session_factory() as db:
        batch = db.get(ImportBatch, batch_id)
        policy = Policy.load(db)
        dp = doc_service.DocPolicy.load(policy)
        manifest = (batch.options or {}).get("manifest") or {"documents": {}, "folders": {}}
        items = _items(db, batch_id)
        progress.set(batch_id, stage="analyse", files_total=len(items), files_done=0)
        for n, item in enumerate(items):
            progress.set(batch_id, files_done=n, current_file=item.relative_path)
            if item.status == "Invalid":  # failed the file checks at upload
                continue
            folders = list(PurePosixPath(item.relative_path).parent.parts)
            m = manifest["documents"].get(item.relative_path)
            if m:
                item.model_id, item.model_source = m["model_id"], "manifest"
                item.document_type, item.type_source = m["document_type"], "manifest"
                item.type_confidence, item.type_reason = 1.0, "Listed in the document manifest."
                item.version = m.get("version") or document_rules.parse_version(item.file_name)
                item.effective_date = datetime.fromisoformat(m["effective_date"]).date() if m.get("effective_date") else None
                item.title = m.get("title")
            else:
                folder_model = next((manifest["folders"][p] for p in _prefixes(folders) if p in manifest["folders"]), None)
                if folder_model:
                    item.model_id, item.model_source = folder_model, "manifest"
                else:
                    item.model_id, item.model_source = document_rules.detect_model_id(folders, item.file_name)
                guess = document_rules.classify_type(item.file_name, folders, dp.keywords)
                item.document_type = guess.document_type if guess.document_type in dp.types else None
                item.type_source, item.type_confidence, item.type_reason = guess.source, guess.confidence, guess.reason
                item.version = document_rules.parse_version(item.file_name)
            item.title = item.title or document_rules.title_from_file(item.file_name)
            item.status = "Uploaded"
            _resolve(db, item, principal)
            db.flush()
        ready = sum(1 for i in items if i.status == "Ready")
        batch.status = "Ready" if ready else "Validation Failed"
        batch.validated_at = datetime.now(UTC)
        _count(batch, items)
        db.commit()
        auto = (batch.options or {}).get("auto_confirm")
    progress.clear(batch_id)
    if auto:
        confirm_job(session_factory, batch_id, principal, auto_threshold=dp.auto_confirm)


def _prefixes(parts: list[str]) -> list[str]:
    """Deepest first: ['a/b/c', 'a/b', 'a']."""
    return ["/".join(parts[:i]) for i in range(len(parts), 0, -1)]


def _count(batch: ImportBatch, items: list[DocumentUploadItem]) -> None:
    batch.total_files = batch.total_records = len(items)
    batch.successful_records = sum(1 for i in items if i.status == "Stored")
    batch.failed_records = sum(1 for i in items if i.status in ("Invalid", "Failed"))
    batch.warning_count = sum(1 for i in items if i.status == "Needs mapping" or i.duplicate_kind)
    batch.successful_files, batch.failed_files = batch.successful_records, batch.failed_records


def update_items(db: Session, principal: Principal, batch_id: str, item_ids: list[int], changes: dict) -> list[DocumentUploadItem]:
    """User mapping review (BRD §33 Method B, §34): model, type, version, date, title, action."""
    _require(principal)
    batch = get_batch(db, batch_id)
    if batch.status not in EDITABLE:
        raise ConflictError(f"Batch {batch_id} is {batch.status}; its mapping can no longer be changed.")
    dp = doc_service.DocPolicy.load(Policy.load(db))
    if "document_type" in changes and changes["document_type"] and changes["document_type"] not in dp.types:
        raise ValidationFailedError(f"'{changes['document_type']}' is not a document type.")
    if "action" in changes and changes["action"] not in ACTIONS:
        raise ValidationFailedError(f"Action must be one of {', '.join(ACTIONS)}.")
    if changes.get("version") and not re.fullmatch(r"\d+(\.\d+)?", changes["version"]):
        raise ValidationFailedError(f"'{changes['version']}' is not a version number such as 1.0 or 2.1.")
    items = [i for i in _items(db, batch_id) if i.item_id in set(item_ids)]
    if len(items) != len(set(item_ids)):
        raise NotFoundError("One or more files are not part of this batch.")
    for item in items:
        if item.status in ("Invalid", "Stored"):
            continue
        if "model_id" in changes:
            item.model_id, item.model_source = (changes["model_id"] or None), "user"
        if "document_type" in changes:
            item.document_type, item.type_source = changes["document_type"] or None, "user"
            item.type_confidence, item.type_reason = 1.0, "Chosen by the reviewer."
        for k in ("version", "effective_date", "title"):
            if k in changes:
                setattr(item, k, changes[k] or None)
        if "action" in changes:
            item.action = changes["action"]
        _resolve(db, item, principal)
    all_items = _items(db, batch_id)
    batch.status = "Ready" if any(i.status == "Ready" for i in all_items) else "Validation Failed"
    _count(batch, all_items)
    audit.record(db, principal, action="update", entity="document_batch", entity_id=batch_id,
                 import_batch_id=batch_id, after={"items": sorted(item_ids), "changes": {
                     k: (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in changes.items()}})
    db.commit()
    return items


def start_confirm(db: Session, session_factory: Callable[[], Session], principal: Principal, batch_id: str) -> ImportBatch:
    _require(principal)
    batch = get_batch(db, batch_id)
    if batch.status not in ("Ready", "Partially Completed", "Failed"):
        raise ConflictError(f"Batch {batch_id} is {batch.status}; there is nothing ready to store.")
    batch.status = "Processing"
    db.commit()
    runner.submit(confirm_job, session_factory, batch_id, principal)
    db.expire_all()
    return get_batch(db, batch_id)


def confirm_job(session_factory: Callable[[], Session], batch_id: str, principal: Principal | None,
                auto_threshold: float | None = None) -> None:
    with session_factory() as db:
        batch = db.get(ImportBatch, batch_id)
        dp = doc_service.DocPolicy.load(Policy.load(db))
        manifest = (batch.options or {}).get("manifest") or {"folders": {}}
        store = get_store()
        items = _items(db, batch_id)
        todo = [i for i in items if i.status == "Ready" and
                (auto_threshold is None or (i.type_confidence or 0) >= auto_threshold)]
        progress.set(batch_id, stage="store", files_total=len(todo), files_done=0)
        for n, item in enumerate(todo):
            progress.set(batch_id, files_done=n, current_file=item.relative_path)
            savepoint = db.begin_nested()
            try:
                folder_id = doc_service.ensure_folders(db, str(PurePosixPath(item.relative_path).parent),
                                                       manifest.get("folders", {}), batch_id)
                doc, v = doc_service.store_version(
                    db, principal, model_id=item.model_id, document_type=item.document_type,
                    data=store.get(item.staging_key), file_name=item.file_name, relative_path=item.relative_path,
                    version=item.version, effective_date=item.effective_date, title=item.title, folder_id=folder_id,
                    source=batch.source, classification=(item.type_source or "user", item.type_confidence or 1.0,
                                                   item.type_reason or ""),
                    batch_id=batch_id, target_document_id=item.target_document_id if item.action == "new_version" else None,
                    allow_duplicate=item.action == "new_version", mime=item.mime_type, dp=dp, commit=False)
                savepoint.commit()
                item.status, item.document_id, item.stored_version, item.error = "Stored", doc.document_id, v.version, None
            except (ServiceError, SQLAlchemyError) as exc:
                savepoint.rollback()
                item.status = "Failed"
                item.error = exc.message if isinstance(exc, ServiceError) else f"Database error: {type(exc).__name__}"
        items = _items(db, batch_id)
        stored = sum(1 for i in items if i.status == "Stored")
        failed = sum(1 for i in items if i.status in ("Failed", "Invalid"))
        pending = sum(1 for i in items if i.status in ("Ready", "Needs mapping"))
        batch.status = ("Failed" if stored == 0 and (failed or pending) else
                        "Partially Completed" if failed or pending else "Completed")
        batch.completed_at = datetime.now(UTC)
        _count(batch, items)
        audit.record(db, principal, action="import", entity="document_batch", entity_id=batch_id,
                     import_batch_id=batch_id, after={"stored": stored, "failed": failed, "not_stored": pending})
        db.commit()
    progress.clear(batch_id)


def get_batch(db: Session, batch_id: str) -> ImportBatch:
    b = db.get(ImportBatch, batch_id)
    if b is None or b.batch_type != "documents":
        raise NotFoundError(f"Document batch {batch_id} does not exist.")
    return b


def items(db: Session, batch_id: str) -> list[DocumentUploadItem]:
    get_batch(db, batch_id)
    return _items(db, batch_id)


def cancel(db: Session, principal: Principal, batch_id: str) -> ImportBatch:
    _require(principal)
    batch = get_batch(db, batch_id)
    if batch.status not in EDITABLE:
        raise ConflictError(f"Batch {batch_id} is {batch.status} and cannot be cancelled.")
    batch.status = "Cancelled"
    audit.record(db, principal, action="cancel", entity="document_batch", entity_id=batch_id, import_batch_id=batch_id)
    db.commit()
    return batch


def error_report_csv(db: Session, batch_id: str) -> bytes:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["relative_path", "status", "model_id", "document_type", "action", "duplicate", "message"])
    for i in items(db, batch_id):
        if i.status in ("Invalid", "Failed", "Needs mapping", "Skipped"):
            w.writerow([i.relative_path, i.status, i.model_id or "", i.document_type or "", i.action,
                        f"{i.duplicate_kind}: {i.duplicate_of}" if i.duplicate_kind else "", i.error or ""])
    for e in ((get_batch(db, batch_id).options or {}).get("manifest") or {}).get("errors", []):
        w.writerow(["(manifest)", "Invalid", "", "", "", "", e])
    return buf.getvalue().encode("utf-8-sig")
