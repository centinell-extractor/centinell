from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    email: str = Field(min_length=5, max_length=255)
    password: str = Field(min_length=8, max_length=256)


class RefreshRequest(BaseModel):
    refresh_token: Optional[str] = None  # opcional: fallback a cookie httpOnly


class UserPublic(BaseModel):
    id: UUID
    email: str
    full_name: Optional[str] = None
    role: str
    must_change_password: bool = False


class TokenResponse(BaseModel):
    """Mantiene compatibilidad con clientes API (Power Automate, etc.)."""
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "bearer"
    expires_in: int
    user: Optional[UserPublic] = None


class LoginResponse(BaseModel):
    """Respuesta para el navegador: tokens en cookies httpOnly, no en body."""
    expires_in: int
    user: UserPublic


class UserCreateRequest(BaseModel):
    email: str = Field(min_length=5, max_length=255)
    password: Optional[str] = Field(default=None, min_length=10, max_length=256)
    full_name: Optional[str] = Field(default=None, max_length=200)
    is_global_admin: bool = False
    send_welcome_email: bool = False


class UserRead(BaseModel):
    id: UUID
    email: str
    full_name: Optional[str]
    is_global_admin: bool
    is_active: bool
    must_change_password: bool
    created_at: datetime


class AssignUserBURequest(BaseModel):
    user_id: UUID
    role: str = Field(default="bu_user", pattern="^(bu_admin|bu_user|bu_viewer)$")


class BUUserAccessRead(BaseModel):
    user_id: UUID
    email: str
    full_name: Optional[str]
    is_global_admin: bool
    is_active: bool
    role: str
    bu_id: UUID


class BUCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    code: str = Field(min_length=2, max_length=40, pattern="^[A-Za-z0-9_-]+$")


class BURead(BaseModel):
    id: UUID
    name: str
    code: str
    is_active: bool
    created_at: datetime


class DashboardByBU(BaseModel):
    bu_id: UUID
    extractions_total: int
    extractions_failed_24h: int


class AdminDashboardResponse(BaseModel):
    users_total: int
    business_units_total: int
    extractions_total: int
    extractions_failed_24h: int
    active_prompt_configs: int
    by_bu: list[DashboardByBU] = []


class AuditEventRead(BaseModel):
    id: UUID
    actor_user_id: Optional[UUID]
    bu_id: Optional[UUID]
    event_type: str
    resource_type: Optional[str]
    resource_id: Optional[str]
    message: Optional[str]
    details: Optional[dict]
    created_at: datetime


class BUProvisionRequest(BaseModel):
    bu_name: str = Field(min_length=2, max_length=200)
    bu_code: str = Field(min_length=2, max_length=40, pattern="^[A-Za-z0-9_-]+$")
    admin_email: Optional[str] = Field(default=None, min_length=5, max_length=255)
    admin_full_name: Optional[str] = Field(default=None, max_length=200)
    admin_role: str = Field(default="bu_admin", pattern="^(bu_admin|bu_user|bu_viewer)$")
    send_welcome_email: bool = True


class BUProvisionResult(BaseModel):
    bu: BURead
    user_created: bool
    user_email: Optional[str] = None


class ChangePasswordRequest(BaseModel):
    current_password: Optional[str] = Field(default=None, min_length=1, max_length=256)
    new_password: str = Field(min_length=8, max_length=256)
