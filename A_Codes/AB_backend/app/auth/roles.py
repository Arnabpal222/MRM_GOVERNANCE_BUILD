"""Role model (BRD §5) and the server-side permission matrix (BRD §59).

Authorization is always decided here on the server; the frontend only mirrors it for display.
"""
from enum import StrEnum


class Role(StrEnum):
    ADMIN = "Admin"
    MODEL_OWNER = "Model Owner"
    MODEL_DEVELOPER = "Model Developer"
    VALIDATOR = "Validator"
    MRC_MEMBER = "MRC Member"
    AUDITOR = "Auditor"
    EXECUTIVE = "Executive"
    MONITORING_ANALYST = "Monitoring Analyst"
    DATA_OWNER = "Data Owner"
    PLATFORM_ADMIN = "Platform Administrator"


class Permission(StrEnum):
    READ = "read"
    AUDIT_READ = "audit:read"
    USER_MANAGE = "user:manage"
    POLICY_EDIT = "policy:edit"
    IMPORT_RUN = "import:run"
    MODEL_EDIT = "model:edit"
    TIER_OVERRIDE = "tier:override"
    VALIDATION_EDIT = "validation:edit"
    FINDING_EDIT = "finding:edit"
    APPROVAL_RECORD = "approval:record"
    DOCUMENT_UPLOAD = "document:upload"
    DOCUMENT_REVIEW = "document:review"
    MONITORING_MANAGE = "monitoring:manage"
    DQ_MANAGE = "dq:manage"
    SYSTEM_ADMIN = "system:admin"


_ALL_READ = {Permission.READ}

ROLE_PERMISSIONS: dict[Role, frozenset[Permission]] = {
    Role.ADMIN: frozenset(Permission) - {Permission.SYSTEM_ADMIN},
    Role.MODEL_OWNER: frozenset(_ALL_READ | {
        Permission.MODEL_EDIT, Permission.FINDING_EDIT, Permission.DOCUMENT_UPLOAD,
        Permission.DOCUMENT_REVIEW, Permission.MONITORING_MANAGE,
    }),
    Role.MODEL_DEVELOPER: frozenset(_ALL_READ | {Permission.DOCUMENT_UPLOAD}),
    Role.VALIDATOR: frozenset(_ALL_READ | {
        Permission.VALIDATION_EDIT, Permission.FINDING_EDIT, Permission.DOCUMENT_UPLOAD,
        Permission.DOCUMENT_REVIEW,
    }),
    Role.MRC_MEMBER: frozenset(_ALL_READ | {Permission.APPROVAL_RECORD, Permission.AUDIT_READ}),
    Role.AUDITOR: frozenset(_ALL_READ | {Permission.AUDIT_READ}),
    Role.EXECUTIVE: frozenset(_ALL_READ),
    Role.MONITORING_ANALYST: frozenset(_ALL_READ | {
        Permission.MONITORING_MANAGE, Permission.DOCUMENT_UPLOAD, Permission.DOCUMENT_REVIEW,
    }),
    Role.DATA_OWNER: frozenset(_ALL_READ | {Permission.DQ_MANAGE, Permission.DOCUMENT_UPLOAD}),
    Role.PLATFORM_ADMIN: frozenset(_ALL_READ | {Permission.SYSTEM_ADMIN, Permission.AUDIT_READ}),
}


def has_permission(role: str, permission: Permission) -> bool:
    try:
        return permission in ROLE_PERMISSIONS[Role(role)]
    except ValueError:
        return False


def permissions_for(role: str) -> list[str]:
    try:
        return sorted(p.value for p in ROLE_PERMISSIONS[Role(role)])
    except ValueError:
        return []
