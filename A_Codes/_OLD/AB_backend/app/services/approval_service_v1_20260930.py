"""MRC and approval decisions (BRD §12)."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit import service as audit
from app.auth.security import Principal
from app.models import Approval
from app.rules import governance_rules
from app.services import access, model_service
from app.services.errors import ConflictError, NotFoundError
from app.services.ids import next_id
from app.services.policy_access import Policy
from app.services.record_helpers import check_allowed, check_required, raise_if

ENTITY = "approval"
FIELDS = ("decision_date", "forum", "decision_type", "decision", "conditions", "condition_due_date",
          "condition_status", "supporting_document_id")


def snapshot(a: Approval) -> dict:
    return {k: getattr(a, k) for k in ("approval_id", "model_id", *FIELDS)}


def list_approvals(db: Session, model_id: str | None = None, decision: str | None = None) -> list[Approval]:
    q = select(Approval).order_by(Approval.decision_date.desc(), Approval.approval_id.desc())
    if model_id:
        q = q.where(Approval.model_id == model_id)
    if decision:
        q = q.where(Approval.decision == decision)
    return list(db.scalars(q))


def get_approval(db: Session, approval_id: str) -> Approval:
    a = db.get(Approval, approval_id)
    if a is None:
        raise NotFoundError(f"Approval {approval_id} does not exist.")
    return a


def _validate(policy: Policy, model_id: str, data: dict) -> None:
    errors: list[tuple[str, str]] = []
    check_required(errors, data, ("decision_date", "forum", "decision_type", "decision"))
    for field, key in (("forum", "approval_forums"), ("decision_type", "approval_decision_types"),
                       ("decision", "approval_decisions")):
        if data.get(field):
            check_allowed(errors, field, data[field], policy.list(key))
    if data.get("decision"):
        errors += governance_rules.approval_errors(data["decision"], data.get("conditions"),
                                                   data.get("condition_due_date"), data.get("condition_status"))
    raise_if(f"Approval for {model_id}", errors)


def create_approval(db: Session, principal: Principal | None, data: dict, *,
                    import_batch_id: str | None = None, commit: bool = True) -> Approval:
    policy = Policy.load(db)
    model = model_service.get_model(db, data.get("model_id"))
    if principal:
        access.ensure_can_record_approval(principal)
    approval_id = data.get("approval_id") or next_id(db, Approval.approval_id, "A")
    if db.get(Approval, approval_id) is not None:
        raise ConflictError(f"Approval {approval_id} already exists.")
    _validate(policy, model.model_id, data)
    a = Approval(approval_id=approval_id, model_id=model.model_id,
                 recorded_by=principal.user_id if principal else None, **{k: data.get(k) for k in FIELDS})
    db.add(a)
    audit.record(db, principal, action="create", entity=ENTITY, entity_id=approval_id, model_id=model.model_id,
                 after=snapshot(a), import_batch_id=import_batch_id)
    if commit:
        db.commit()
        db.refresh(a)
    return a


def update_approval(db: Session, principal: Principal, approval_id: str, data: dict, expected_version: int,
                    reason: str | None = None) -> Approval:
    """Mainly used to mark conditions Met; decisions themselves are corrected with a reason."""
    access.ensure_can_record_approval(principal)
    policy = Policy.load(db)
    a = get_approval(db, approval_id)
    if a.row_version != expected_version:
        raise ConflictError(f"Approval {approval_id} was changed by someone else; reload and retry.")
    merged = {k: data.get(k, getattr(a, k)) for k in FIELDS}
    _validate(policy, a.model_id, merged)
    before = snapshot(a)
    for k, v in merged.items():
        setattr(a, k, v)
    if snapshot(a) == before:
        return a
    audit.record(db, principal, action="update", entity=ENTITY, entity_id=approval_id, model_id=a.model_id,
                 before=before, after=snapshot(a), reason=reason)
    db.commit()
    db.refresh(a)
    return a
