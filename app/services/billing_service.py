# app/services/billing_service.py
"""
Servicio de control de cuotas y billing.
Verifica límites, aplica overages, y genera invoices.
"""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import BUPlan, Invoice, Plan, UsageEvent
from app.services import usage_service


class QuotaExceededError(Exception):
    """Se ha excedido la cuota y el plan no permite overages."""
    pass


async def get_active_plan(db: AsyncSession, bu_id: UUID) -> Plan | None:
    """Obtiene el plan activo (vigente) de una BU."""
    stmt = (
        select(Plan)
        .join(BUPlan, BUPlan.plan_id == Plan.id)
        .where(
            and_(
                BUPlan.bu_id == bu_id,
                BUPlan.ends_at.is_(None),  # Plan activo (no finalizado)
            )
        )
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def get_month_usage(db: AsyncSession, bu_id: UUID, month: datetime) -> dict[str, int]:
    """
    Obtiene el consumo de la BU para el mes especificado.
    Retorna: {'docs_uploaded': n, 'extractions_run': n, 'users_added': n, ...}
    """
    month_start, month_end = usage_service._month_bounds(month)

    stmt = (
        select(UsageEvent.event_type, UsageEvent.quantity)
        .where(
            and_(
                UsageEvent.bu_id == bu_id,
                UsageEvent.created_at >= month_start,
                UsageEvent.created_at < month_end,
            )
        )
    )
    result = await db.execute(stmt)
    rows = result.all()

    usage = {
        "docs_uploaded": 0,
        "extractions_run": 0,
        "users_added": 0,
    }

    for event_type, quantity in rows:
        if event_type == usage_service.DOC_UPLOADED:
            usage["docs_uploaded"] += quantity
        elif event_type == usage_service.EXTRACTION_RUN:
            usage["extractions_run"] += quantity
        # Para usuarios: usar tabla users_bu_access (más adelante si es necesario)

    return usage


async def check_quota(
    db: AsyncSession,
    bu_id: UUID,
    action_type: str,
    quantity: int = 1,
) -> tuple[bool, int]:
    """
    Verifica si una acción se puede ejecutar bajo las restricciones de cuota.

    Args:
        db: Sesión de BD
        bu_id: ID de la BU
        action_type: "doc.upload", "extraction.run", etc.
        quantity: Cantidad a consumir (por defecto 1)

    Returns:
        (allowed: bool, overage_cost_cents: int)
        - allowed=True: acción permitida (sin overage o plan lo permite)
        - allowed=False: acción rechazada (cuota excedida, plan sin overage)
        - overage_cost_cents: costo en céntimos si hay overage (0 si no hay)

    Raises:
        QuotaExceededError: si se excede cuota y plan no permite overage
    """
    plan = await get_active_plan(db, bu_id)
    if not plan:
        # Sin plan asignado = no puede hacer nada
        raise QuotaExceededError(f"BU {bu_id} no tiene plan asignado")

    now = datetime.now(timezone.utc)
    usage = await get_month_usage(db, bu_id, now)

    overage_cost_cents = 0

    if action_type == "doc.upload":
        if usage["docs_uploaded"] >= plan.max_docs_per_month:
            if not plan.allow_overage:
                raise QuotaExceededError(
                    f"Cuota de documentos alcanzada (máx {plan.max_docs_per_month}/mes). "
                    f"Plan {plan.code} no permite overages."
                )
            overage_cost_cents = plan.overage_doc_cents * quantity

    elif action_type == "extraction.run":
        if usage["extractions_run"] >= plan.max_extractions_per_month:
            if not plan.allow_overage:
                raise QuotaExceededError(
                    f"Cuota de extracciones alcanzada (máx {plan.max_extractions_per_month}/mes). "
                    f"Plan {plan.code} no permite overages."
                )
            overage_cost_cents = plan.overage_extraction_cents * quantity

    # Para otros tipos de acción: agregar lógica según necesidad

    return True, overage_cost_cents


async def record_overage(
    db: AsyncSession,
    bu_id: UUID,
    action_type: str,
    quantity: int,
    cost_cents: int,
) -> None:
    """
    Registra un cargo de overage como evento de uso especial.
    El valor se sumará a la invoice al fin de mes.

    En el futuro esto podría ir a una tabla separada de "pending_charges".
    Por ahora se registra como evento de tipo "overage.{action_type}".
    """
    if cost_cents <= 0:
        return  # No hay overage, no registrar

    overage_event_type = f"overage.{action_type}"
    await usage_service.track_event(
        db,
        bu_id=bu_id,
        event_type=overage_event_type,
        quantity=cost_cents,  # Almacenar céntimos como cantidad
        metadata={"base_action": action_type, "units": quantity},
    )
