from datetime import date
from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, Response, UploadFile, status
from sqlalchemy import select

from app.api.deps import CurrentPrincipal, DbSession
from app.db import get_session_factory
from app.documents import batch as doc_batch
from app.documents import service as doc_service
from app.models import DocumentFolder, ImportBatch, Model
from app.schemas.documents import (
    ArchiveRequest,
    CompletenessOut,
    DocumentBatchOut,
    DocumentDetailOut,
    DocumentLinkOut,
    DocumentMetaOut,
    DocumentOut,
    DocumentSummaryOut,
    FolderOut,
    ItemUpdate,
    LegalHoldRequest,
    LinkCreate,
    UploadItemOut,
)
from app.schemas.ingestion import ImportBatchOut
from app.services.policy_access import Policy
from app.workers.runner import progress

router = APIRouter(prefix="/api/documents", tags=["documents"])
SessionFactory = Annotated[object, Depends(get_session_factory)]


def _folder_path(db, folder_id: int | None) -> str | None:
    if folder_id is None:
        return None
    f = db.get(DocumentFolder, folder_id)
    return f.relative_path if f else None


def _summary(db, d) -> DocumentSummaryOut:
    v = d.versions[0]
    return DocumentSummaryOut(**DocumentOut.model_validate(d).model_dump(), file_name=v.file_name,
                              size_bytes=v.size_bytes, uploaded_at=v.uploaded_at, folder_path=_folder_path(db, d.folder_id))


def _batch_out(db, b) -> DocumentBatchOut:
    manifest = (b.options or {}).get("manifest") or {}
    return DocumentBatchOut(**ImportBatchOut.model_validate(b).model_dump(),
                            items=[UploadItemOut.model_validate(i) for i in doc_batch.items(db, b.batch_id)],
                            progress=progress.get(b.batch_id), manifest_errors=manifest.get("errors", []),
                            manifest_files=(b.options or {}).get("manifest_files") or [])


@router.get("/meta", response_model=DocumentMetaOut)
def meta(db: DbSession, _: CurrentPrincipal):
    p = Policy.load(db)
    dp = doc_service.DocPolicy.load(p)
    return DocumentMetaOut(document_types=dp.types, confidentiality_levels=dp.confidentiality,
                           default_confidentiality=dp.default_confidentiality, extensions=dp.extensions,
                           max_document_mb=p.int("max_document_size_mb"), max_zip_mb=p.int("max_zip_size_mb"),
                           max_files=p.int("max_zip_file_count"))


@router.get("", response_model=list[DocumentSummaryOut])
def list_documents(db: DbSession, _: CurrentPrincipal, model_id: str | None = None, document_type: str | None = None,
                   folder_id: int | None = None, search: str | None = None, status: str | None = "Active",
                   limit: int = 500):
    return [_summary(db, d) for d in doc_service.search(db, model_id=model_id, document_type=document_type,
                                                         folder_id=folder_id, text=search, status=status or None,
                                                         limit=limit)]


@router.post("", response_model=DocumentDetailOut, status_code=status.HTTP_201_CREATED)
async def upload_single(
    db: DbSession, principal: CurrentPrincipal,
    file: Annotated[UploadFile, File()],
    model_id: Annotated[str, Form()],
    document_type: Annotated[str, Form()],
    version: Annotated[str | None, Form()] = None,
    effective_date: Annotated[date | None, Form()] = None,
    title: Annotated[str | None, Form()] = None,
    confidentiality: Annotated[str | None, Form()] = None,
    change_reason: Annotated[str | None, Form()] = None,
    new_version_of: Annotated[str | None, Form()] = None,
):
    """Individual upload (BRD §29): model, type and version chosen by the user; stored immediately."""
    doc, _ = doc_service.store_version(
        db, principal, model_id=model_id, document_type=document_type, data=await file.read(),
        file_name=file.filename or "document", version=version or None, effective_date=effective_date,
        title=title or None, confidentiality=confidentiality or None, source="single",
        change_reason=change_reason or None, target_document_id=new_version_of or None,
        allow_duplicate=bool(new_version_of))
    return get_document(doc.document_id, db, principal)


@router.get("/folders", response_model=list[FolderOut])
def list_folders(db: DbSession, _: CurrentPrincipal):
    counts = doc_service.document_counts_by_folder(db)
    return [FolderOut.model_validate(f).model_copy(update={"document_count": counts.get(f.folder_id, 0)})
            for f in doc_service.folders(db)]


@router.get("/completeness", response_model=list[CompletenessOut])
def completeness(db: DbSession, _: CurrentPrincipal, model_id: str | None = None, missing_only: bool = False):
    """Required-document completeness per model (BRD §40), from the configured policy."""
    policy = Policy.load(db)
    q = select(Model).order_by(Model.model_id)
    if model_id:
        q = q.where(Model.model_id == model_id)
    models = list(db.scalars(q))
    present = doc_service.present_types(db, [m.model_id for m in models] if model_id else None)
    from app.rules import document_rules

    out = []
    for m in models:
        c = document_rules.completeness(doc_service.required_for(policy, m.lifecycle_phase),
                                        present.get(m.model_id, set()))
        if missing_only and not c.missing:
            continue
        out.append(CompletenessOut(model_id=m.model_id, model_name=m.model_name, lifecycle_phase=m.lifecycle_phase,
                                   required=c.required, present=c.present, missing=c.missing, score=c.score))
    return out


# --- batches (multi-file, folder, ZIP) --------------------------------------------------------------

@router.post("/batches", response_model=DocumentBatchOut, status_code=status.HTTP_201_CREATED)
async def upload_batch(
    db: DbSession, principal: CurrentPrincipal, session_factory: SessionFactory,
    files: Annotated[list[UploadFile], File()],
    paths: Annotated[list[str] | None, Form()] = None,
    source: Annotated[str, Form()] = "batch",
):
    uploads = []
    for i, f in enumerate(files):
        name = paths[i] if paths and i < len(paths) and paths[i] else (f.filename or f"file_{i + 1}")
        uploads.append((name, await f.read()))
    b = doc_batch.create_batch(db, session_factory, principal, uploads,
                               source=source if source in ("batch", "folder") else "batch")
    db.expire_all()
    return _batch_out(db, doc_batch.get_batch(db, b.batch_id))


@router.get("/batches", response_model=list[ImportBatchOut])
def list_batches(db: DbSession, _: CurrentPrincipal, limit: int = 100):
    return list(db.scalars(select(ImportBatch).where(ImportBatch.batch_type == "documents")
                           .order_by(ImportBatch.created_at.desc(), ImportBatch.batch_id.desc()).limit(limit)))


@router.get("/batches/{batch_id}", response_model=DocumentBatchOut)
def get_batch(batch_id: str, db: DbSession, _: CurrentPrincipal):
    return _batch_out(db, doc_batch.get_batch(db, batch_id))


@router.patch("/batches/{batch_id}/items", response_model=DocumentBatchOut)
def update_items(batch_id: str, body: ItemUpdate, db: DbSession, principal: CurrentPrincipal):
    changes = body.model_dump(exclude={"item_ids"}, exclude_unset=True)
    doc_batch.update_items(db, principal, batch_id, body.item_ids, changes)
    return _batch_out(db, doc_batch.get_batch(db, batch_id))


@router.post("/batches/{batch_id}/confirm", response_model=DocumentBatchOut)
def confirm(batch_id: str, db: DbSession, principal: CurrentPrincipal, session_factory: SessionFactory):
    doc_batch.start_confirm(db, session_factory, principal, batch_id)
    db.expire_all()
    return _batch_out(db, doc_batch.get_batch(db, batch_id))


@router.post("/batches/{batch_id}/cancel", response_model=DocumentBatchOut)
def cancel(batch_id: str, db: DbSession, principal: CurrentPrincipal):
    doc_batch.cancel(db, principal, batch_id)
    return _batch_out(db, doc_batch.get_batch(db, batch_id))


@router.get("/batches/{batch_id}/error-report")
def batch_error_report(batch_id: str, db: DbSession, _: CurrentPrincipal):
    return Response(doc_batch.error_report_csv(db, batch_id), media_type="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="{batch_id}_document_errors.csv"'})


# --- single document ---------------------------------------------------------------------------------

@router.get("/{document_id}", response_model=DocumentDetailOut)
def get_document(document_id: str, db: DbSession, _: CurrentPrincipal):
    d = doc_service.get_document(db, document_id)
    return DocumentDetailOut(**DocumentOut.model_validate(d).model_dump(),
                             versions=list(d.versions),
                             links=[DocumentLinkOut.model_validate(x) for x in doc_service.links_for(db, document_id)],
                             folder_path=_folder_path(db, d.folder_id))


@router.get("/{document_id}/versions/{version}/download")
def download(document_id: str, version: str, db: DbSession, _: CurrentPrincipal, inline: bool = False):
    """Original bytes of any version, current or historical (DOC-17)."""
    v = doc_service.get_version(db, document_id, version)
    disposition = "inline" if inline else "attachment"
    return Response(doc_service.read_version(v), media_type=v.mime_type, headers={
        "Content-Disposition": f"{disposition}; filename*=UTF-8''{quote(v.file_name)}",
        "X-Content-Type-Options": "nosniff"})


@router.post("/{document_id}/archive", response_model=DocumentOut)
def archive(document_id: str, body: ArchiveRequest, db: DbSession, principal: CurrentPrincipal):
    return doc_service.archive(db, principal, document_id, body.reason)


@router.post("/{document_id}/legal-hold", response_model=DocumentOut)
def legal_hold(document_id: str, body: LegalHoldRequest, db: DbSession, principal: CurrentPrincipal):
    return doc_service.set_legal_hold(db, principal, document_id, body.hold, body.reason)


@router.post("/{document_id}/links", response_model=DocumentLinkOut, status_code=status.HTTP_201_CREATED)
def add_link(document_id: str, body: LinkCreate, db: DbSession, principal: CurrentPrincipal):
    return doc_service.add_link(db, principal, document_id, body.entity_type, body.entity_id)
