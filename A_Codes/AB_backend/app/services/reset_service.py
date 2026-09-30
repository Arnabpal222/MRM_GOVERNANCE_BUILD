"""Demo/dev "reset to seed" (BRD §70, REQ-GEN-01).

Clears governance data and rebuilds it through the import engine from the seed files in
B_Inputs/AC_seed — the same path a user import takes — then loads the seed evidence documents
through the Document Centre batch path. Stored objects of cleared documents remain in object storage. The audit trail and import history are
kept: audit records are immutable, and the reset itself is recorded as an audit event.
"""
import importlib.util
from collections.abc import Callable
from pathlib import Path

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.audit import service as audit
from app.auth.roles import Permission, has_permission
from app.auth.security import Principal
from app.clock import today
from app.config import get_settings
from app.ingestion import engine
from app.ingestion import service as import_service
from app.models import (
    AppUser,
    Approval,
    Document,
    DocumentFolder,
    DocumentLink,
    DocumentVersion,
    Finding,
    ImportBatch,
    Model,
    ModelPhaseHistory,
    ModelRelationship,
    ModelVersion,
    PolicySetting,
    TieringAnswer,
    TierOverride,
    UserRole,
    Validation,
)
from app.services.errors import ForbiddenError, ValidationFailedError
from app.services.policy_access import Policy
from app.workers import runner

# Children before parents.
DELETE_ORDER = (Finding, Approval, Validation, DocumentLink, DocumentVersion, Document, DocumentFolder, ModelRelationship,
                ModelVersion, ModelPhaseHistory, TierOverride, TieringAnswer, Model, UserRole, AppUser, PolicySetting)


def regenerate_seed(directory: Path) -> None:
    """Rewrite the seed templates (and demo files) for today's business date using A_Codes/AD_seed."""
    s = get_settings()
    spec = importlib.util.spec_from_file_location("generate_seed", s.seed_generator)
    if spec is None or not s.seed_generator.exists():
        raise ValidationFailedError(f"Seed generator not found at {s.seed_generator}.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.generate(directory, today(), demo_dir=s.demo_files_dir)


def seed_files(directory: Path) -> list[tuple[str, bytes]]:
    files = sorted(p for p in directory.glob("*") if p.suffix.lower() in (".xlsx", ".csv"))
    if not files:
        raise ValidationFailedError(f"No seed files found in {directory}. Run A_Codes/AD_seed/generate_seed.py.")
    return [(p.name, p.read_bytes()) for p in files]


def start_reset(db: Session, session_factory: Callable[[], Session], principal: Principal | None,
                directory: Path | None = None) -> ImportBatch:
    if not get_settings().allow_reset:
        raise ForbiddenError("Reset is disabled in this environment (MRM_ALLOW_RESET=false).")
    if principal and not has_permission(principal.role, Permission.POLICY_EDIT):
        raise ForbiddenError("Only an Admin can reset the application data.")
    directory = directory or get_settings().seed_dir
    if get_settings().regenerate_seed_on_reset:
        regenerate_seed(directory)
    uploads = seed_files(directory)
    batch = import_service.create_batch(db, None, uploads, source="reset", batch_type="seed")
    batch.uploaded_by = principal.user_id if principal else None
    db.commit()
    runner.submit(_reset_job, session_factory, batch.batch_id, principal)
    return batch


def _reset_job(session_factory: Callable[[], Session], batch_id: str, principal: Principal | None) -> None:
    with session_factory() as db:
        counts = {m.__tablename__: db.scalar(select(func.count()).select_from(m)) for m in DELETE_ORDER}
        for m in DELETE_ORDER:
            db.execute(delete(m))
        Policy.invalidate(db)
        audit.record(db, principal, action="reset", entity="application", entity_id="all", import_batch_id=batch_id,
                     before=counts, reason="Reset to seed")
        batch = db.get(ImportBatch, batch_id)
        batch.status = "Processing"
        db.commit()
    engine.run(session_factory, batch_id, "load", None)
    load_seed_documents(session_factory, get_settings().seed_dir / "documents")


def load_seed_documents(session_factory: Callable[[], Session], directory: Path) -> str | None:
    """Seed evidence goes through the Document Centre batch path: folder/file classification, then
    automatic confirmation of confidently classified files (system seed only)."""
    if not directory.is_dir():
        return None
    uploads = [(p.relative_to(directory).as_posix(), p.read_bytes()) for p in sorted(directory.rglob("*")) if p.is_file()]
    if not uploads:
        return None
    from app.documents import batch as doc_batch

    with session_factory() as db:
        return doc_batch.create_batch(db, session_factory, None, uploads, source="seed", auto_confirm=True).batch_id
