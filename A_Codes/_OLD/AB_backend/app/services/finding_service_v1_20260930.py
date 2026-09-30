"""Findings and remediation (BRD §11)."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit import service as audit
from app.auth.security import Principal
from app.clock import today
from app.models import Finding, Validation
from app.rules import governance_rules
from app.services import access, model_service
from app.services.errors import ConflictError, NotFoundError
from app.services.ids import next_id
from app.services.policy_access import Policy
from app.services.record_helpers import check_allowed, check_required, check_user, raise_if

ENTITY = "finding"
FIELDS = ("validation_id", "title", "description", "severity", "category", "status", "owner_id", "raised_date",
          "due_date", "closed_date", "evidence", "root_cause", "management_response", "remediation_action")


def snapshot(f: Finding) -> dict:
    return {k: getattr(f, k) for k in ("finding_id", "model_id", "source", *FIELDS)}


def age(f: Finding, policy: Policy) -> governance_rules.FindingAge:
    return governance_rules.finding_age(f.status, f.raised_date, f.due_date, f.closed_date, today(),
                                        policy.list("finding_open_statuses"))


def list_findings(db: Session, *, model_id: str | None = None, status: str | None = None,
                  severity: str | None = None, overdue_only: bool = False) -> list[Finding]:
    q = select(Finding).order_by(Finding.raised_date.desc(), Finding.finding_id.desc())
    if model_id:
        q = q.where(Finding.model_id == model_id)
    if status:
        q = q.where(Finding.status == status)
    if severity:
        q = q.where(Finding.severity == severity)
    rows = list(db.scalars(q))
    if overdue_only:
        policy = Policy.load(db)
        rows = [f for f in rows if age(f, policy).is_overdue]
    return rows


def get_finding(db: Session, finding_id: str) -> Finding:
    f = db.get(Finding, finding_id)
    if f is None:
        raise NotFoundError(f"Finding {finding_id} does not exist.")
    return f


def _validate(db: Session, policy: Policy, model_id: str, data: dict) -> None:
    errors: list[tuple[str, str]] = []
    check_required(errors, data, ("title", "description", "severity", "category", "status", "raised_date", "due_date"))
    if data.get("title") and len(data["title"]) > 120:
        errors.append(("title", "Title must be at most 120 characters."))
    for field, key in (("severity", "finding_severities"), ("category", "finding_categories"),
                       ("status", "finding_statuses")):
        if data.get(field):
            check_allowed(errors, field, data[field], policy.list(key))
    check_user(errors, db, "owner_id", data.get("owner_id"))
    vid = data.get("validation_id")
    if vid:
        v = db.get(Validation, vid)
        if v is None:
            errors.append(("validation_id", f"Validation {vid} does not exist."))
        elif v.model_id != model_id:
            errors.append(("validation_id", f"Validation {vid} belongs to {v.model_id}, not {model_id}."))
    if data.get("status") and data.get("raised_date") and data.get("due_date"):
        errors += governance_rules.finding_errors(data["status"], data["raised_date"], data["due_date"],
                                                  data.get("closed_date"), policy.list("finding_open_statuses"))
    raise_if(f"Finding for {model_id}", errors)


def create_finding(db: Session, principal: Principal | None, data: dict, *,
                   import_batch_id: str | None = None, commit: bool = True) -> Finding:
    policy = Policy.load(db)
    model = model_service.get_model(db, data.get("model_id"))
    if principal:
        access.ensure_can_edit_finding(principal, model)
    data = {**data, "raised_date": data.get("raised_date") or today(), "owner_id": data.get("owner_id") or model.owner_id}
    source = data.get("source") or "Manual"
    if source not in policy.list("finding_sources"):
        raise_if("Finding", [("source", f"'{source}' is not an allowed finding source.")])
    finding_id = data.get("finding_id") or next_id(db, Finding.finding_id, "F")
    if db.get(Finding, finding_id) is not None:
        raise ConflictError(f"Finding {finding_id} already exists.")
    _validate(db, policy, model.model_id, data)
    f = Finding(finding_id=finding_id, model_id=model.model_id, source=source, **{k: data.get(k) for k in FIELDS})
    db.add(f)
    audit.record(db, principal, action="create", entity=ENTITY, entity_id=finding_id, model_id=model.model_id,
                 after=snapshot(f), import_batch_id=import_batch_id)
    if commit:
        db.commit()
        db.refresh(f)
    return f


def update_finding(db: Session, principal: Principal, finding_id: str, data: dict, expected_version: int,
                   reason: str | None = None) -> Finding:
    policy = Policy.load(db)
    f = get_finding(db, finding_id)
    model = model_service.get_model(db, f.model_id)
    access.ensure_can_edit_finding(principal, model)
    if f.row_version != expected_version:
        raise ConflictError(f"Finding {finding_id} was changed by someone else; reload and retry.")
    merged = {k: data.get(k, getattr(f, k)) for k in FIELDS}
    open_statuses = policy.list("finding_open_statuses")
    # Closing without a date defaults to today; re-opening clears the closed date.
    if merged["status"] not in open_statuses and merged["closed_date"] is None:
        merged["closed_date"] = today()
    if merged["status"] in open_statuses:
        merged["closed_date"] = None
    _validate(db, policy, model.model_id, merged)
    before = snapshot(f)
    for k, v in merged.items():
        setattr(f, k, v)
    if snapshot(f) == before:
        return f
    action = "close" if before["status"] in open_statuses and f.status not in open_statuses else "update"
    audit.record(db, principal, action=action, entity=ENTITY, entity_id=finding_id, model_id=model.model_id,
                 before=before, after=snapshot(f), reason=reason)
    db.commit()
    db.refresh(f)
    return f
