"""
Servicio de entrega de webhooks de salida.

Firma cada payload con HMAC-SHA256 usando el secret del webhook.
El receptor puede verificar la autenticidad comprobando el header
X-Centinell-Signature: sha256=<hex_digest>
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.connection import AsyncSessionLocal
from app.db.models import WebhookConfig

logger = logging.getLogger(__name__)

_TIMEOUT = 10.0
_RETRIES = 2


def _sign(secret: str, body: bytes) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


async def _deliver(wh: WebhookConfig, payload: dict[str, Any]) -> int:
    body = json.dumps(payload, default=str).encode()
    headers = {
        "Content-Type": "application/json",
        "X-Centinell-Signature": _sign(wh.secret, body),
        "X-Centinell-Event": payload.get("event", ""),
        "User-Agent": "Centinell-Webhook/1.0",
    }
    last_code = 0
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        for attempt in range(_RETRIES + 1):
            try:
                resp = await client.post(str(wh.url), content=body, headers=headers)
                last_code = resp.status_code
                if resp.status_code < 400:
                    return last_code
                logger.warning("Webhook %s devolvió %s (intento %s)", wh.id, resp.status_code, attempt + 1)
            except Exception as exc:
                logger.warning("Webhook %s falló (intento %s): %s", wh.id, attempt + 1, exc)
    return last_code


async def dispatch(bu_id: UUID, event: str, data: dict[str, Any]) -> None:
    """Busca webhooks activos suscritos al evento y entrega el payload en background."""
    payload = {
        "event": event,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "bu_id": str(bu_id),
        "data": data,
    }
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(WebhookConfig).where(
                WebhookConfig.bu_id == bu_id,
                WebhookConfig.is_active.is_(True),
            )
        )
        webhooks = [w for w in result.scalars().all() if event in (w.events or [])]

        for wh in webhooks:
            status_code = await _deliver(wh, payload)
            wh.last_triggered_at = datetime.now(timezone.utc)
            wh.last_status_code = status_code
            db.add(wh)

        if webhooks:
            await db.commit()
