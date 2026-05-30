from __future__ import annotations

import secrets
from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, HttpUrl, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.connection import get_db
from app.db.models import WebhookConfig
from app.dependencies.auth import AuthContext, get_bu_auth_context, require_bu_roles
from app.services.audit import log_audit_event
from app.services.webhook import dispatch

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

VALID_EVENTS = {
    "extraction.completed",
    "extraction.failed",
    "assessment.completed",
    "assessment.failed",
}


class WebhookCreate(BaseModel):
    name: str
    url: HttpUrl
    events: list[str]

    @field_validator("events")
    @classmethod
    def check_events(cls, v: list[str]) -> list[str]:
        invalid = set(v) - VALID_EVENTS
        if invalid:
            raise ValueError(f"Eventos no válidos: {invalid}. Válidos: {VALID_EVENTS}")
        if not v:
            raise ValueError("Selecciona al menos un evento")
        return v


class WebhookRead(BaseModel):
    id: UUID
    name: str
    url: str
    events: list[str]
    is_active: bool
    last_triggered_at: Optional[datetime] = None
    last_status_code: Optional[int] = None
    created_at: datetime
    secret_prefix: str  # primeros 8 chars del secret para identificarlo

    model_config = {"from_attributes": True}


@router.get("/", response_model=list[WebhookRead])
async def list_webhooks(
    auth: AuthContext = Depends(get_bu_auth_context),
    db: AsyncSession = Depends(get_db),
):
    require_bu_roles(auth, {"bu_admin", "admin_global"}, "Requiere rol bu_admin")
    result = await db.execute(
        select(WebhookConfig)
        .where(WebhookConfig.bu_id == auth.bu_id)
        .order_by(WebhookConfig.created_at.desc())
    )
    rows = result.scalars().all()
    return [
        WebhookRead(
            **{k: getattr(r, k) for k in ("id", "name", "events", "is_active",
                                           "last_triggered_at", "last_status_code", "created_at")},
            url=str(r.url),
            secret_prefix=r.secret[:8] + "…",
        )
        for r in rows
    ]


@router.post("/", response_model=WebhookRead, status_code=201)
async def create_webhook(
    payload: WebhookCreate,
    auth: AuthContext = Depends(get_bu_auth_context),
    db: AsyncSession = Depends(get_db),
):
    require_bu_roles(auth, {"bu_admin", "admin_global"}, "Requiere rol bu_admin")
    secret = secrets.token_hex(32)
    wh = WebhookConfig(
        bu_id=auth.bu_id,
        name=payload.name,
        url=str(payload.url),
        secret=secret,
        events=payload.events,
    )
    db.add(wh)
    await db.flush()
    await db.refresh(wh)
    await log_audit_event(db, event_type="webhook.created", actor_user_id=auth.actor_user_id,
                          bu_id=auth.bu_id, resource_type="webhook", resource_id=str(wh.id),
                          message=f"Webhook creado: {payload.name}")
    await db.commit()
    return WebhookRead(
        **{k: getattr(wh, k) for k in ("id", "name", "events", "is_active",
                                        "last_triggered_at", "last_status_code", "created_at")},
        url=str(wh.url),
        secret_prefix=secret[:8] + "…",
    )


@router.patch("/{webhook_id}/toggle", response_model=WebhookRead)
async def toggle_webhook(
    webhook_id: UUID,
    auth: AuthContext = Depends(get_bu_auth_context),
    db: AsyncSession = Depends(get_db),
):
    require_bu_roles(auth, {"bu_admin", "admin_global"}, "Requiere rol bu_admin")
    wh = await db.get(WebhookConfig, webhook_id)
    if not wh or wh.bu_id != auth.bu_id:
        raise HTTPException(status_code=404, detail="Webhook no encontrado")
    wh.is_active = not wh.is_active
    await db.commit()
    return WebhookRead(
        **{k: getattr(wh, k) for k in ("id", "name", "events", "is_active",
                                        "last_triggered_at", "last_status_code", "created_at")},
        url=str(wh.url),
        secret_prefix=wh.secret[:8] + "…",
    )


@router.delete("/{webhook_id}", status_code=204)
async def delete_webhook(
    webhook_id: UUID,
    auth: AuthContext = Depends(get_bu_auth_context),
    db: AsyncSession = Depends(get_db),
):
    require_bu_roles(auth, {"bu_admin", "admin_global"}, "Requiere rol bu_admin")
    wh = await db.get(WebhookConfig, webhook_id)
    if not wh or wh.bu_id != auth.bu_id:
        raise HTTPException(status_code=404, detail="Webhook no encontrado")
    await log_audit_event(db, event_type="webhook.deleted", actor_user_id=auth.actor_user_id,
                          bu_id=auth.bu_id, resource_type="webhook", resource_id=str(webhook_id),
                          message=f"Webhook eliminado: {wh.name}")
    await db.delete(wh)
    await db.commit()


@router.post("/{webhook_id}/test", status_code=204)
async def test_webhook(
    webhook_id: UUID,
    auth: AuthContext = Depends(get_bu_auth_context),
    db: AsyncSession = Depends(get_db),
):
    """Envía un evento de prueba al webhook."""
    require_bu_roles(auth, {"bu_admin", "admin_global"}, "Requiere rol bu_admin")
    wh = await db.get(WebhookConfig, webhook_id)
    if not wh or wh.bu_id != auth.bu_id:
        raise HTTPException(status_code=404, detail="Webhook no encontrado")
    await dispatch(auth.bu_id, "extraction.completed", {
        "extraction_id": "00000000-0000-0000-0000-000000000000",
        "document_name": "test_document.pdf",
        "status": "success",
        "latency_ms": 0,
        "test": True,
    })
