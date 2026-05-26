import hashlib
import secrets
from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.connection import get_db
from app.db.models import ApiKey
from app.dependencies.auth import AuthContext, get_bu_auth_context, require_bu_roles
from app.services.audit import log_audit_event

router = APIRouter(prefix="/api-keys", tags=["api-keys"])


class ApiKeyCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    role: str = Field(default="bu_user", pattern="^(bu_admin|bu_user|bu_viewer)$")


class ApiKeyRead(BaseModel):
    id: UUID
    name: str
    key_prefix: str
    role: str
    is_active: bool
    created_at: datetime
    last_used_at: Optional[datetime] = None


class ApiKeyCreateResponse(ApiKeyRead):
    key: str


@router.get("/", response_model=list[ApiKeyRead])
async def list_api_keys(
    auth: AuthContext = Depends(get_bu_auth_context),
    db: AsyncSession = Depends(get_db),
):
    require_bu_roles(auth, {"bu_admin", "admin_global"}, "Requiere rol bu_admin")
    result = await db.execute(
        select(ApiKey)
        .where(ApiKey.bu_id == auth.bu_id, ApiKey.is_active.is_(True))
        .order_by(ApiKey.created_at.desc())
    )
    return list(result.scalars().all())


@router.post("/", response_model=ApiKeyCreateResponse, status_code=201)
async def create_api_key(
    payload: ApiKeyCreateRequest,
    auth: AuthContext = Depends(get_bu_auth_context),
    db: AsyncSession = Depends(get_db),
):
    require_bu_roles(auth, {"bu_admin", "admin_global"}, "Requiere rol bu_admin")

    key_b64 = secrets.token_urlsafe(32)
    full_key = f"cnt_{key_b64}"
    key_hash = hashlib.sha256(full_key.encode()).hexdigest()
    key_prefix = full_key[:12]

    api_key = ApiKey(
        bu_id=auth.bu_id,
        created_by=auth.actor_user_id,
        name=payload.name,
        key_prefix=key_prefix,
        key_hash=key_hash,
        role=payload.role,
    )
    db.add(api_key)
    await db.flush()
    await db.refresh(api_key)

    await log_audit_event(
        db,
        event_type="api_key.created",
        actor_user_id=auth.actor_user_id,
        bu_id=auth.bu_id,
        resource_type="api_key",
        resource_id=str(api_key.id),
        message=f"API key creada: {payload.name}",
        metadata={"role": payload.role, "prefix": key_prefix},
    )

    return ApiKeyCreateResponse(
        id=api_key.id,
        name=api_key.name,
        key_prefix=api_key.key_prefix,
        role=api_key.role,
        is_active=api_key.is_active,
        created_at=api_key.created_at,
        last_used_at=api_key.last_used_at,
        key=full_key,
    )


@router.delete("/{key_id}", status_code=204)
async def revoke_api_key(
    key_id: UUID,
    auth: AuthContext = Depends(get_bu_auth_context),
    db: AsyncSession = Depends(get_db),
):
    require_bu_roles(auth, {"bu_admin", "admin_global"}, "Requiere rol bu_admin")

    api_key = await db.get(ApiKey, key_id)
    if not api_key or api_key.bu_id != auth.bu_id or not api_key.is_active:
        raise HTTPException(status_code=404, detail="API Key no encontrada")

    api_key.is_active = False
    await db.flush()

    await log_audit_event(
        db,
        event_type="api_key.revoked",
        actor_user_id=auth.actor_user_id,
        bu_id=auth.bu_id,
        resource_type="api_key",
        resource_id=str(key_id),
        message=f"API key revocada: {api_key.name}",
    )
