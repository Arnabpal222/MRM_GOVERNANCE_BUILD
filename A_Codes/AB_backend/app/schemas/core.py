"""API schemas for Phase 1 (kept separate from ORM models, BRD §82 rule 4)."""
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --- auth ---------------------------------------------------------------------------

class LoginRequest(BaseModel):
    user_id: str
    role: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class MeResponse(BaseModel):
    user_id: str
    full_name: str
    role: str
    roles: list[str]
    permissions: list[str]


class DevUser(BaseModel):
    user_id: str
    full_name: str
    roles: list[str]


# --- users --------------------------------------------------------------------------

class UserOut(ORMModel):
    user_id: str
    full_name: str
    email: str
    business_line: str | None
    active: bool
    roles: list[str] = Field(validation_alias="role_names")
    row_version: int


class UserCreate(BaseModel):
    user_id: str = Field(pattern=r"^U-\d{3,}$")
    full_name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    business_line: str | None = None
    roles: list[str] = Field(min_length=1)
    active: bool = True


# --- policy -------------------------------------------------------------------------

class PolicySettingOut(ORMModel):
    setting_key: str
    value: str
    value_type: str
    category: str | None
    description: str | None
    updated_by: str | None
    updated_at: datetime | None
    row_version: int


class PolicySettingUpdate(BaseModel):
    value: str
    row_version: int
    reason: str | None = None


# --- audit --------------------------------------------------------------------------

class AuditEventOut(ORMModel):
    event_id: int
    occurred_at: datetime
    user_id: str | None
    role: str | None
    action: str
    entity: str
    entity_id: str
    model_id: str | None
    import_batch_id: str | None
    document_id: str | None
    reason: str | None
    before_json: dict[str, Any] | None
    after_json: dict[str, Any] | None


# --- health -------------------------------------------------------------------------

class ComponentHealth(BaseModel):
    status: str  # ok | down
    detail: str | None = None


class HealthResponse(BaseModel):
    status: str  # ok | degraded | down
    components: dict[str, ComponentHealth]
