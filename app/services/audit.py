from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AuditEvent


async def log_audit_event(
    db: AsyncSession,
    event_type: str,
    actor_user_id: UUID | None = None,
    bu_id: UUID | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    message: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    event = AuditEvent(
        actor_user_id=actor_user_id,
        bu_id=bu_id,
        event_type=event_type,
        resource_type=resource_type,
        resource_id=resource_id,
        message=message,
        details=metadata,
    )
    db.add(event)
