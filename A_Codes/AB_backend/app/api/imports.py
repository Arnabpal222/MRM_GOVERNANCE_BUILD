from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Response, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import CurrentPrincipal, DbSession, require
from app.auth.roles import Permission
from app.auth.security import Principal
from app.db import get_session_factory
from app.ingestion import checks, fileio
from app.ingestion import service as import_service
from app.ingestion.registry import TEMPLATES, get_template
from app.models import AppUser, Approval, Finding, Model, PolicySetting, Validation
from app.schemas.ingestion import (
    ColumnOut,
    FileTemplateUpdate,
    ImportBatchDetail,
    ImportBatchOut,
    ImportFileOut,
    ImportIssueOut,
    TemplateOut,
)
from app.services.errors import NotFoundError, ValidationFailedError
from app.services.policy_access import Policy
from app.workers.runner import progress

router = APIRouter(prefix="/api/imports", tags=["imports"])

Importer = Annotated[Principal, Depends(require(Permission.IMPORT_RUN))]
SessionFactory = Annotated[object, Depends(get_session_factory)]
TARGET_MODELS = {"policy_setting": PolicySetting, "app_user": AppUser, "model": Model, "validation": Validation,
                 "finding": Finding, "approval": Approval}


def _detail(db: Session, batch) -> ImportBatchDetail:
    files = []
    for f in batch.files:
        out = ImportFileOut.model_validate(f)
        out.duplicate_of_batch = import_service.duplicate_of(db, f)
        files.append(out)
    return ImportBatchDetail(**ImportBatchOut.model_validate(batch).model_dump(), files=files,
                             progress=progress.get(batch.batch_id))


@router.get("/templates", response_model=list[TemplateOut])
def list_templates(db: DbSession, _: CurrentPrincipal):
    policy = Policy.load(db)
    counts = {t: db.scalar(select(func.count()).select_from(m)) for t, m in TARGET_MODELS.items()}
    by_id = {t.template_id: t for t in TEMPLATES}
    out = []
    for t in sorted(TEMPLATES, key=lambda x: x.order):
        allowed = checks.allowed_values(t, policy)
        missing = [d for d in t.depends_on if not counts.get(by_id[d].target)]
        out.append(TemplateOut(
            template_id=t.template_id, name=t.name, format=t.format, target=t.target, key=t.key, order=t.order,
            available=t.available, channel=t.channel, phase=t.phase, description=t.description, depends_on=list(t.depends_on),
            record_count=counts.get(t.target), prerequisites_met=not missing, missing_prerequisites=missing,
            columns=[ColumnOut(name=c.name, type=c.type, required=c.required, condition=c.condition,
                               allowed=allowed.get(c.name), reference=c.fk, description=c.description,
                               example=c.example) for c in t.columns]))
    return out


@router.get("/templates/{template_id}/blank")
def blank_template(template_id: str, db: DbSession, _: CurrentPrincipal, format: str | None = None):
    """Blank template with the header row and an instructions sheet (REQ-IMP-06)."""
    t = get_template(template_id)
    if t is None or not t.available:
        raise NotFoundError(f"Template {template_id} is not available for download.")
    fmt = format or t.format
    if fmt == "csv":
        body, media, ext = fileio.write_csv(t, []), "text/csv", "csv"
    elif fmt == "xlsx":
        body = fileio.write_workbook(t, [], checks.allowed_values(t, Policy.load(db)))
        media, ext = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "xlsx"
    else:
        raise ValidationFailedError("format must be xlsx or csv.")
    name = f"{t.template_id}_{t.name.lower().replace(' ', '_').replace('/', '_')}_template.{ext}"
    return Response(body, media_type=media, headers={"Content-Disposition": f'attachment; filename="{name}"'})


@router.post("/batches", response_model=ImportBatchDetail, status_code=status.HTTP_201_CREATED)
async def upload_batch(
    db: DbSession, principal: Importer, session_factory: SessionFactory,
    files: Annotated[list[UploadFile], File()],
    paths: Annotated[list[str] | None, Form()] = None,
    on_existing: Annotated[str, Form()] = "update",
):
    """Upload one or many files as one batch; validation starts automatically (preview, nothing saved)."""
    uploads = []
    for i, f in enumerate(files):
        name = paths[i] if paths and i < len(paths) and paths[i] else (f.filename or f"file_{i + 1}")
        uploads.append((name, await f.read()))
    batch = import_service.create_batch(db, principal, uploads, on_existing=on_existing)
    batch = import_service.start(db, session_factory, principal, batch.batch_id, "validate")
    return _detail(db, batch)


@router.get("/batches", response_model=list[ImportBatchOut])
def list_batches(db: DbSession, _: Importer, limit: int = 100):
    return import_service.list_batches(db, limit)


@router.get("/batches/{batch_id}", response_model=ImportBatchDetail)
def get_batch(batch_id: str, db: DbSession, _: Importer):
    return _detail(db, import_service.get_batch(db, batch_id))


@router.get("/batches/{batch_id}/issues", response_model=list[ImportIssueOut])
def batch_issues(batch_id: str, db: DbSession, _: Importer, file_id: int | None = None, limit: int = 500):
    import_service.get_batch(db, batch_id)
    return import_service.issues(db, batch_id, file_id, limit)


@router.get("/batches/{batch_id}/error-report")
def error_report(batch_id: str, db: DbSession, _: Importer):
    return Response(import_service.error_report_csv(db, batch_id), media_type="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="{batch_id}_errors.csv"'})


@router.post("/batches/{batch_id}/validate", response_model=ImportBatchDetail)
def validate_batch(batch_id: str, db: DbSession, principal: Importer, session_factory: SessionFactory):
    return _detail(db, import_service.start(db, session_factory, principal, batch_id, "validate"))


@router.post("/batches/{batch_id}/load", response_model=ImportBatchDetail)
def load_batch(batch_id: str, db: DbSession, principal: Importer, session_factory: SessionFactory):
    """Explicit Load (BRD §43): persists valid rows; invalid rows are rejected and reported."""
    return _detail(db, import_service.start(db, session_factory, principal, batch_id, "load"))


@router.post("/batches/{batch_id}/cancel", response_model=ImportBatchDetail)
def cancel_batch(batch_id: str, db: DbSession, principal: Importer):
    return _detail(db, import_service.cancel(db, principal, batch_id))


@router.patch("/files/{file_id}", response_model=ImportFileOut)
def set_template(file_id: int, body: FileTemplateUpdate, db: DbSession, principal: Importer):
    return import_service.set_file_template(db, principal, file_id, body.template_id)
