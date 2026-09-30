"""Document service: storing versions, folders, permissions, completeness and queries (BRD §27–§40).

Every stored file becomes an immutable DocumentVersion. An exact re-upload (same SHA-256) is refused
unless the caller explicitly asks for a new version; versions are never overwritten or deleted.
"""
import hashlib
from dataclasses import dataclass
from datetime import date
from pathlib import PurePosixPath

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.audit import service as audit
from app.auth.roles import Permission, Role, has_permission
from app.auth.security import Principal
from app.clock import today
from app.documents import files
from app.models import Document, DocumentFolder, DocumentLink, DocumentVersion, Model
from app.rules import document_rules
from app.rules.revalidation import add_months
from app.services import model_service
from app.services.errors import ConflictError, ForbiddenError, NotFoundError, ValidationFailedError
from app.services.ids import next_id
from app.services.policy_access import Policy
from app.storage import get_store

ENTITY = "document"
ANY_MODEL_ROLES = {Role.ADMIN.value, Role.MONITORING_ANALYST.value, Role.DATA_OWNER.value}
LINK_TYPES = {"validation", "finding", "approval"}


@dataclass(frozen=True)
class DocPolicy:
    types: list[str]
    keywords: list[tuple[str, list[str]]]
    extensions: list[str]
    max_bytes: int
    confidentiality: list[str]
    default_confidentiality: str
    retention_years: int
    auto_confirm: float
    zip_limits: files.ZipLimits
    max_zip_bytes: int

    @classmethod
    def load(cls, policy: Policy) -> "DocPolicy":
        return cls(
            types=policy.list("document_types"),
            keywords=document_rules.parse_keywords(policy.list("document_type_keywords")),
            extensions=[e.lower().lstrip(".") for e in policy.list("allowed_document_extensions")],
            max_bytes=policy.int("max_document_size_mb") * 1024 * 1024,
            confidentiality=policy.list("document_confidentiality_levels"),
            default_confidentiality=policy.text("document_default_confidentiality"),
            retention_years=policy.int("document_retention_years"),
            auto_confirm=float(policy.decimal("document_auto_confirm_confidence")),
            zip_limits=files.ZipLimits(policy.int("max_zip_file_count"),
                                       policy.int("max_zip_uncompressed_mb") * 1024 * 1024,
                                       policy.int("max_zip_compression_ratio")),
            max_zip_bytes=policy.int("max_zip_size_mb") * 1024 * 1024,
        )


# --- permissions ---------------------------------------------------------------------------

def can_upload_for(principal: Principal | None, model: Model) -> str | None:
    """None if allowed, else the reason. Owners, developers and validators upload for their own models."""
    if principal is None:
        return None
    if not has_permission(principal.role, Permission.DOCUMENT_UPLOAD):
        return f"Role '{principal.role}' is not permitted to upload documents."
    if principal.role in ANY_MODEL_ROLES:
        return None
    assigned = {Role.MODEL_OWNER.value: model.owner_id, Role.MODEL_DEVELOPER.value: model.developer_id,
                Role.VALIDATOR.value: model.validator_id}.get(principal.role)
    if assigned == principal.user_id:
        return None
    return f"{principal.user_id} ({principal.role}) is not assigned to model {model.model_id}."


def ensure_can_upload(principal: Principal | None, model: Model) -> None:
    reason = can_upload_for(principal, model)
    if reason:
        raise ForbiddenError(reason)


# --- folders -------------------------------------------------------------------------------

def ensure_folders(db: Session, directory: str, model_for: dict[str, str], batch_id: str | None) -> int | None:
    """Create each level of a relative directory path once; returns the leaf folder id (BRD §31)."""
    if not directory or directory == ".":
        return None
    parent_id, path = None, ""
    for part in PurePosixPath(directory).parts:
        path = f"{path}/{part}" if path else part
        folder = db.scalar(select(DocumentFolder).where(DocumentFolder.relative_path == path))
        if folder is None:
            mid, _ = document_rules.detect_model_id([part], "")
            mid = model_for.get(path) or (mid if mid and db.get(Model, mid) else None)
            folder = DocumentFolder(parent_folder_id=parent_id, folder_name=part, relative_path=path, model_id=mid,
                                    created_batch_id=batch_id)
            db.add(folder)
            db.flush()
        parent_id = folder.folder_id
    return parent_id


# --- storing -------------------------------------------------------------------------------

def _snapshot(d: Document) -> dict:
    return {k: getattr(d, k) for k in ("document_id", "model_id", "title", "document_type", "current_version",
                                        "effective_date", "status", "folder_id", "confidentiality", "source")}


def find_same_document(db: Session, model_id: str, document_type: str, title: str) -> Document | None:
    """An existing active document this upload is a new version of: same model, type and title."""
    key = document_rules.normalised_title(title)
    for d in db.scalars(select(Document).where(Document.model_id == model_id, Document.document_type == document_type,
                                               Document.status == "Active")):
        if document_rules.normalised_title(d.title) == key:
            return d
    return None


def find_by_checksum(db: Session, checksum: str) -> DocumentVersion | None:
    return db.scalar(select(DocumentVersion).where(DocumentVersion.checksum == checksum).limit(1))


def store_version(
    db: Session, principal: Principal | None, *, model_id: str, document_type: str, data: bytes, file_name: str,
    relative_path: str | None = None, version: str | None = None, effective_date: date | None = None,
    title: str | None = None, confidentiality: str | None = None, folder_id: int | None = None,
    source: str = "single", classification: tuple[str, float, str] | None = None, batch_id: str | None = None,
    change_reason: str | None = None, target_document_id: str | None = None, allow_duplicate: bool = False,
    mime: str | None = None, dp: DocPolicy | None = None, commit: bool = True,
) -> tuple[Document, DocumentVersion]:
    dp = dp or DocPolicy.load(Policy.load(db))
    model = model_service.get_model(db, model_id)
    ensure_can_upload(principal, model)
    if document_type not in dp.types:
        raise ValidationFailedError(f"'{document_type}' is not a document type. Allowed: {', '.join(dp.types)}.")
    confidentiality = confidentiality or dp.default_confidentiality
    if confidentiality not in dp.confidentiality:
        raise ValidationFailedError(f"'{confidentiality}' is not a confidentiality level.")
    try:
        mime = mime or files.validate_document(file_name, data, dp.extensions, dp.max_bytes)
    except files.FileRejected as exc:
        raise ValidationFailedError(f"{file_name}: {exc}") from None

    checksum = hashlib.sha256(data).hexdigest()
    dup = find_by_checksum(db, checksum)
    if dup is not None and not allow_duplicate:
        raise ConflictError(f"Document already exists with SHA-256 checksum {checksum[:16]}… "
                            f"({dup.document_id} v{dup.version}). Choose 'new version' to store it again.")

    title = title or document_rules.title_from_file(file_name)
    doc = db.get(Document, target_document_id) if target_document_id else find_same_document(
        db, model_id, document_type, title)
    if target_document_id and doc is None:
        raise NotFoundError(f"Document {target_document_id} does not exist.")
    user_id = principal.user_id if principal else None

    if doc is None:
        version = version or "1.0"
        doc_id = next_id(db, Document.document_id, "D", 6)
        start = effective_date or today()
        doc = Document(document_id=doc_id, model_id=model_id, title=title, document_type=document_type,
                       current_version=version, effective_date=effective_date, status="Active", folder_id=folder_id,
                       source=source, confidentiality=confidentiality, retention_start=start,
                       retention_end=add_months(start, 12 * dp.retention_years), created_by=user_id,
                       classification_source=classification[0] if classification else "user",
                       classification_confidence=classification[1] if classification else 1.0,
                       classification_reason=classification[2] if classification else "Chosen by the uploader.")
        db.add(doc)
        action, before = "upload", None
    else:
        if doc.model_id != model_id:
            raise ValidationFailedError(f"{doc.document_id} belongs to {doc.model_id}, not {model_id}.")
        existing = [v.version for v in doc.versions]
        version = version or document_rules.next_version(existing)
        if version in existing:
            raise ConflictError(f"{doc.document_id} already has version {version}; versions are never overwritten.")
        if not document_rules.is_newer(version, existing):
            raise ValidationFailedError(f"Version {version} is older than the current version {doc.current_version} "
                                        f"of {doc.document_id}.")
        before = _snapshot(doc)
        doc.current_version = version
        doc.effective_date = effective_date or doc.effective_date
        doc.folder_id = folder_id or doc.folder_id
        action = "version"

    key = f"models/{model_id}/documents/{doc.document_id}/{version}/{file_name}"
    get_store().put(key, data, mime)
    v = DocumentVersion(document_id=doc.document_id, version=version, file_name=file_name, relative_path=relative_path,
                        file_type=files.extension(file_name), mime_type=mime, size_bytes=len(data), checksum=checksum,
                        storage_key=key, change_reason=change_reason, import_batch_id=batch_id, uploaded_by=user_id)
    db.add(v)
    db.flush()
    db.expire(doc, ["versions"])  # reload the version list including this one
    audit.record(db, principal, action=action, entity=ENTITY, entity_id=doc.document_id, model_id=model_id,
                 document_id=doc.document_id, import_batch_id=batch_id, before=before,
                 after={**_snapshot(doc), "version": version, "file_name": file_name, "checksum": checksum,
                        "relative_path": relative_path}, reason=change_reason)
    if commit:
        db.commit()
    return doc, v


# --- queries ---------------------------------------------------------------------------------

def get_document(db: Session, document_id: str) -> Document:
    d = db.get(Document, document_id)
    if d is None:
        raise NotFoundError(f"Document {document_id} does not exist.")
    return d


def get_version(db: Session, document_id: str, version: str) -> DocumentVersion:
    v = db.scalar(select(DocumentVersion).where(DocumentVersion.document_id == document_id,
                                                DocumentVersion.version == version))
    if v is None:
        raise NotFoundError(f"Document {document_id} has no version {version}.")
    return v


def read_version(v: DocumentVersion) -> bytes:
    return get_store().get(v.storage_key)


def search(db: Session, *, model_id: str | None = None, document_type: str | None = None, folder_id: int | None = None,
           text: str | None = None, status: str | None = "Active", limit: int = 500) -> list[Document]:
    q = select(Document).order_by(Document.updated_at.desc(), Document.document_id.desc()).limit(limit)
    if model_id:
        q = q.where(Document.model_id == model_id)
    if document_type:
        q = q.where(Document.document_type == document_type)
    if folder_id:
        q = q.where(Document.folder_id == folder_id)
    if status:
        q = q.where(Document.status == status)
    if text:
        like = f"%{text.strip()}%"
        q = q.where(Document.title.ilike(like) | Document.document_id.ilike(like) | Document.document_id.in_(
            select(DocumentVersion.document_id).where(DocumentVersion.file_name.ilike(like))))
    return list(db.scalars(q))


def folders(db: Session) -> list[DocumentFolder]:
    return list(db.scalars(select(DocumentFolder).order_by(DocumentFolder.relative_path)))


def document_counts_by_folder(db: Session) -> dict[int, int]:
    rows = db.execute(select(Document.folder_id, func.count()).where(Document.status == "Active")
                      .group_by(Document.folder_id))
    return {fid: n for fid, n in rows if fid is not None}


def present_types(db: Session, model_ids: list[str] | None = None) -> dict[str, set[str]]:
    q = select(Document.model_id, Document.document_type).where(Document.status == "Active").distinct()
    if model_ids is not None:
        q = q.where(Document.model_id.in_(model_ids))
    out: dict[str, set[str]] = {}
    for mid, t in db.execute(q):
        out.setdefault(mid, set()).add(t)
    return out


def required_for(policy: Policy, phase: str) -> list[str]:
    return document_rules.required_types(phase, policy.phases, policy.list("required_docs_development"),
                                         policy.list("required_docs_validation"),
                                         policy.list("required_docs_production"))


def completeness(db: Session, model: Model, policy: Policy | None = None) -> document_rules.Completeness:
    policy = policy or Policy.load(db)
    return document_rules.completeness(required_for(policy, model.lifecycle_phase),
                                       present_types(db, [model.model_id]).get(model.model_id, set()))


# --- lifecycle and links ------------------------------------------------------------------------

def archive(db: Session, principal: Principal, document_id: str, reason: str) -> Document:
    """Controlled retirement of a document (BRD §68): never deleted, only archived — and not under legal hold."""
    if not has_permission(principal.role, Permission.POLICY_EDIT):
        raise ForbiddenError("Only an Admin can archive documents.")
    if not (reason or "").strip():
        raise ValidationFailedError("A reason is required to archive a document.")
    d = get_document(db, document_id)
    if d.legal_hold:
        raise ConflictError(f"{document_id} is under legal hold and cannot be archived.")
    if d.status == "Archived":
        return d
    before = _snapshot(d)
    d.status = "Archived"
    audit.record(db, principal, action="archive", entity=ENTITY, entity_id=document_id, model_id=d.model_id,
                 document_id=document_id, before=before, after=_snapshot(d), reason=reason)
    db.commit()
    return d


def set_legal_hold(db: Session, principal: Principal, document_id: str, hold: bool, reason: str) -> Document:
    if not has_permission(principal.role, Permission.POLICY_EDIT):
        raise ForbiddenError("Only an Admin can change legal hold.")
    d = get_document(db, document_id)
    before = _snapshot(d) | {"legal_hold": d.legal_hold}
    d.legal_hold = hold
    audit.record(db, principal, action="legal_hold", entity=ENTITY, entity_id=document_id, model_id=d.model_id,
                 document_id=document_id, before=before, after=_snapshot(d) | {"legal_hold": hold}, reason=reason)
    db.commit()
    return d


def add_link(db: Session, principal: Principal, document_id: str, entity_type: str, entity_id: str) -> DocumentLink:
    from app.models import Approval, Finding, Validation

    d = get_document(db, document_id)
    ensure_can_upload(principal, model_service.get_model(db, d.model_id))
    orm = {"validation": Validation, "finding": Finding, "approval": Approval}.get(entity_type)
    if orm is None:
        raise ValidationFailedError(f"Documents can be linked to: {', '.join(sorted(LINK_TYPES))}.")
    target = db.get(orm, entity_id)
    if target is None:
        raise NotFoundError(f"{entity_type.title()} {entity_id} does not exist.")
    if target.model_id != d.model_id:
        raise ValidationFailedError(f"{entity_id} belongs to {target.model_id}; {document_id} belongs to {d.model_id}.")
    if db.get(DocumentLink, (document_id, entity_type, entity_id)) is not None:
        raise ConflictError(f"{document_id} is already linked to {entity_id}.")
    link = DocumentLink(document_id=document_id, entity_type=entity_type, entity_id=entity_id,
                        created_by=principal.user_id)
    db.add(link)
    audit.record(db, principal, action="link", entity=ENTITY, entity_id=document_id, model_id=d.model_id,
                 document_id=document_id, after={"entity_type": entity_type, "entity_id": entity_id})
    db.commit()
    return link


def links_for(db: Session, document_id: str) -> list[DocumentLink]:
    return list(db.scalars(select(DocumentLink).where(DocumentLink.document_id == document_id)))
