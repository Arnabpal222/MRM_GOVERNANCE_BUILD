"""Validations, findings and approvals APIs. Record-level authorization lives in the services."""
from fastapi import APIRouter, status

from app.api.deps import CurrentPrincipal, DbSession
from app.api.models import finding_out
from app.schemas.governance import (
    ApprovalCreate,
    ApprovalOut,
    ApprovalUpdate,
    FindingCreate,
    FindingOut,
    FindingUpdate,
    ValidationCreate,
    ValidationOut,
    ValidationUpdate,
)
from app.services import approval_service, finding_service, validation_service
from app.services.policy_access import Policy

validations = APIRouter(prefix="/api/validations", tags=["validations"])
findings = APIRouter(prefix="/api/findings", tags=["findings"])
approvals = APIRouter(prefix="/api/approvals", tags=["approvals"])


@validations.get("", response_model=list[ValidationOut])
def list_validations(db: DbSession, _: CurrentPrincipal, model_id: str | None = None):
    return validation_service.list_validations(db, model_id)


@validations.post("", response_model=ValidationOut, status_code=status.HTTP_201_CREATED)
def create_validation(body: ValidationCreate, db: DbSession, principal: CurrentPrincipal):
    return validation_service.create_validation(db, principal, body.model_dump())


@validations.put("/{validation_id}", response_model=ValidationOut)
def update_validation(validation_id: str, body: ValidationUpdate, db: DbSession, principal: CurrentPrincipal):
    return validation_service.update_validation(db, principal, validation_id,
                                                body.model_dump(exclude={"row_version"}), body.row_version)


@findings.get("", response_model=list[FindingOut])
def list_findings(db: DbSession, _: CurrentPrincipal, model_id: str | None = None, status: str | None = None,
                  severity: str | None = None, overdue_only: bool = False):
    policy = Policy.load(db)
    rows = finding_service.list_findings(db, model_id=model_id, status=status, severity=severity,
                                         overdue_only=overdue_only)
    return [finding_out(f, policy) for f in rows]


@findings.post("", response_model=FindingOut, status_code=status.HTTP_201_CREATED)
def create_finding(body: FindingCreate, db: DbSession, principal: CurrentPrincipal):
    f = finding_service.create_finding(db, principal, body.model_dump())
    return finding_out(f, Policy.load(db))


@findings.patch("/{finding_id}", response_model=FindingOut)
def update_finding(finding_id: str, body: FindingUpdate, db: DbSession, principal: CurrentPrincipal):
    data = body.model_dump(exclude={"row_version", "reason"}, exclude_unset=True)
    f = finding_service.update_finding(db, principal, finding_id, data, body.row_version, body.reason)
    return finding_out(f, Policy.load(db))


@approvals.get("", response_model=list[ApprovalOut])
def list_approvals(db: DbSession, _: CurrentPrincipal, model_id: str | None = None, decision: str | None = None):
    return approval_service.list_approvals(db, model_id, decision)


@approvals.post("", response_model=ApprovalOut, status_code=status.HTTP_201_CREATED)
def create_approval(body: ApprovalCreate, db: DbSession, principal: CurrentPrincipal):
    return approval_service.create_approval(db, principal, body.model_dump())


@approvals.patch("/{approval_id}", response_model=ApprovalOut)
def update_approval(approval_id: str, body: ApprovalUpdate, db: DbSession, principal: CurrentPrincipal):
    data = body.model_dump(exclude={"row_version", "reason"}, exclude_unset=True)
    return approval_service.update_approval(db, principal, approval_id, data, body.row_version, body.reason)
