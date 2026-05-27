# app/services/usage_service.py
"""
Servicio de tracking y agregación de uso por BU.

Diseño:
  - track_event(): función fire-and-forget que añade un evento a la sesión
    activa. NO hace commit — el caller decide cuándo hacer commit.
    Silencia cualquier error para garantizar que nunca interrumpa el flujo
    principal de la aplicación.
  - get_bu_usage_summary(): agrega uso de una BU para el reporting del bu_admin.
  - get_admin_overview(): vista global de todas las BUs para admin_global.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import Date, and_, case, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import BUPlan, BusinessUnit, Plan, UsageEvent, UserBUAccess
from app.schemas.usage import (
    AdminBURow,
    AdminOverview,
    BUUsageSummary,
    DailyPoint,
    PeriodUsage,
    PlanRead,
    QuotaStatus,
)

logger = logging.getLogger(__name__)

# ── Constantes de tipos de evento ─────────────────────────────────────────────
# Usar siempre estas constantes en lugar de strings literales.

DOC_UPLOADED      = "doc.uploaded"
DOC_DELETED       = "doc.deleted"
EXTRACTION_RUN    = "extraction.run"
TOKENS_CONSUMED   = "tokens.consumed"
COLLECTION_EXPORT = "collection.export"


# ── Helpers internos ──────────────────────────────────────────────────────────

def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _month_bounds(ref: datetime) -> tuple[datetime, datetime]:
    """Devuelve (inicio_mes, inicio_mes_siguiente) para el mes de `ref`, en UTC."""
    start = ref.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if start.month == 12:
        end = start.replace(year=start.year + 1, month=1)
    else:
        end = start.replace(month=start.month + 1)
    return start, end


def _prev_month_bounds(ref: datetime) -> tuple[datetime, datetime]:
    curr_start, _ = _month_bounds(ref)
    if curr_start.month == 1:
        prev_start = curr_start.replace(year=curr_start.year - 1, month=12)
    else:
        prev_start = curr_start.replace(month=curr_start.month - 1)
    return prev_start, curr_start  # fin del mes anterior = inicio del actual


def _rows_to_period_usage(rows) -> PeriodUsage:
    """Convierte filas (event_type, total) a PeriodUsage."""
    totals = {row.event_type: int(row.total) for row in rows}
    return PeriodUsage(
        docs_uploaded=totals.get(DOC_UPLOADED, 0),
        docs_deleted=totals.get(DOC_DELETED, 0),
        extractions_run=totals.get(EXTRACTION_RUN, 0),
        tokens_consumed=totals.get(TOKENS_CONSUMED, 0),
        exports_done=totals.get(COLLECTION_EXPORT, 0),
    )


def _build_quota_status(plan: Optional[Plan], usage: PeriodUsage) -> Optional[QuotaStatus]:
    if plan is None:
        return None

    def _pct(used: int, limit: Optional[int]) -> Optional[float]:
        if not limit:
            return None
        return round(used / limit * 100, 1)

    return QuotaStatus(
        docs_used=usage.docs_uploaded,
        docs_limit=plan.max_docs_per_month,
        docs_pct=_pct(usage.docs_uploaded, plan.max_docs_per_month),
        extractions_used=usage.extractions_run,
        extractions_limit=plan.max_extractions_per_month,
        extractions_pct=_pct(usage.extractions_run, plan.max_extractions_per_month),
        tokens_used=usage.tokens_consumed,
        tokens_limit=plan.max_tokens_per_month,
        tokens_pct=_pct(usage.tokens_consumed, plan.max_tokens_per_month),
    )


# ── Core tracking ─────────────────────────────────────────────────────────────

async def track_event(
    db: AsyncSession,
    *,
    bu_id: UUID,
    event_type: str,
    quantity: int = 1,
    user_id: Optional[UUID] = None,
    metadata: Optional[dict] = None,
) -> None:
    """
    Agrega un evento de uso a la sesión activa.

    IMPORTANTE: NO hace commit. El caller commit en su propio ciclo de
    transacción. Esto permite que el evento y la operación que lo genera
    sean atómicos (mismo commit).

    Nunca lanza excepción — captura y loggea cualquier error para que
    un fallo de tracking no interrumpa nunca el flujo principal.
    """
    try:
        event = UsageEvent(
            bu_id=bu_id,
            user_id=user_id,
            event_type=event_type,
            quantity=max(1, quantity),
            payload=metadata or {},
        )
        db.add(event)
    except Exception:
        logger.exception(
            "Error registrando usage_event (non-fatal): type=%s bu_id=%s",
            event_type,
            bu_id,
        )


# ── Queries de agregación ─────────────────────────────────────────────────────

async def _period_usage(
    db: AsyncSession,
    bu_id: UUID,
    period_start: datetime,
    period_end: datetime,
) -> PeriodUsage:
    stmt = (
        select(
            UsageEvent.event_type,
            func.sum(UsageEvent.quantity).label("total"),
        )
        .where(
            UsageEvent.bu_id == bu_id,
            UsageEvent.created_at >= period_start,
            UsageEvent.created_at < period_end,
        )
        .group_by(UsageEvent.event_type)
    )
    rows = (await db.execute(stmt)).all()
    return _rows_to_period_usage(rows)


async def _daily_trend(
    db: AsyncSession,
    bu_id: UUID,
    days: int = 30,
) -> list[DailyPoint]:
    """
    Tendencia diaria de los últimos N días.
    Rellena explícitamente todos los días aunque no haya actividad,
    para que el frontend siempre reciba una serie continua.
    Usa CAST(... AS DATE) para compatibilidad PostgreSQL/SQLite.
    """
    now = _utcnow()
    trend_start = (now - timedelta(days=days - 1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )

    stmt = (
        select(
            cast(UsageEvent.created_at, Date).label("day"),
            UsageEvent.event_type,
            func.sum(UsageEvent.quantity).label("total"),
        )
        .where(
            UsageEvent.bu_id == bu_id,
            UsageEvent.created_at >= trend_start,
        )
        .group_by("day", UsageEvent.event_type)
        .order_by("day")
    )
    rows = (await db.execute(stmt)).all()

    # Indexar: date → {event_type: total}
    data: dict[date, dict[str, int]] = {}
    for row in rows:
        d: date = row.day if isinstance(row.day, date) else row.day
        data.setdefault(d, {})[row.event_type] = int(row.total)

    # Rellenar gaps para serie continua
    result: list[DailyPoint] = []
    cursor = trend_start.date()
    today = now.date()
    while cursor <= today:
        day_data = data.get(cursor, {})
        result.append(DailyPoint(
            date=cursor,
            docs_uploaded=day_data.get(DOC_UPLOADED, 0),
            extractions_run=day_data.get(EXTRACTION_RUN, 0),
            tokens_consumed=day_data.get(TOKENS_CONSUMED, 0),
        ))
        cursor += timedelta(days=1)
    return result


async def _get_active_plan(db: AsyncSession, bu_id: UUID) -> Optional[Plan]:
    """Devuelve el plan activo de la BU (ends_at IS NULL), o None."""
    stmt = (
        select(Plan)
        .join(BUPlan, BUPlan.plan_id == Plan.id)
        .where(
            BUPlan.bu_id == bu_id,
            BUPlan.ends_at.is_(None),
        )
        .order_by(BUPlan.starts_at.desc())
        .limit(1)
    )
    return (await db.execute(stmt)).scalars().first()


# ── API pública ───────────────────────────────────────────────────────────────

async def get_bu_usage_summary(db: AsyncSession, bu_id: UUID) -> BUUsageSummary:
    """
    Resumen completo de uso para una BU:
    mes actual, mes anterior, tendencia diaria 30 días y estado de cuotas.
    Uso: endpoint GET /reports/me (bu_admin) y GET /reports/admin/bu/{id}.
    """
    bu = await db.get(BusinessUnit, bu_id)
    if not bu:
        raise ValueError(f"BU not found: {bu_id}")

    now = _utcnow()
    curr_start, curr_end = _month_bounds(now)
    prev_start, prev_end = _prev_month_bounds(now)

    # Queries secuenciales (AsyncSession no es segura para concurrencia)
    current    = await _period_usage(db, bu_id, curr_start, curr_end)
    last_month = await _period_usage(db, bu_id, prev_start, prev_end)
    trend      = await _daily_trend(db, bu_id)
    plan       = await _get_active_plan(db, bu_id)

    return BUUsageSummary(
        bu_id=bu.id,
        bu_name=bu.name,
        bu_code=bu.code,
        plan=PlanRead.model_validate(plan) if plan else None,
        quota_status=_build_quota_status(plan, current),
        current_month=current,
        last_month=last_month,
        daily_trend=trend,
    )


async def get_admin_overview(db: AsyncSession) -> AdminOverview:
    """
    Vista ejecutiva para admin_global: todas las BUs con su uso del mes actual,
    plan asignado y conteo de usuarios. Máximo 3 queries independientemente
    del número de BUs (no hay N+1).
    """
    now = _utcnow()
    curr_start, curr_end = _month_bounds(now)

    # Nombres de mes en español (strftime devuelve en locale del sistema;
    # hardcodeamos para garantizar consistencia)
    _MES = [
        "", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
        "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
    ]
    period_label = f"{_MES[now.month]} {now.year}"

    # ── Query 1: BUs + conteo de usuarios activos ─────────────────────────────
    stmt_bus = (
        select(
            BusinessUnit,
            func.count(UserBUAccess.id).label("users_count"),
        )
        .outerjoin(
            UserBUAccess,
            and_(
                UserBUAccess.bu_id == BusinessUnit.id,
                UserBUAccess.is_active.is_(True),
            ),
        )
        .group_by(BusinessUnit.id)
        .order_by(BusinessUnit.name)
    )
    bus_rows = (await db.execute(stmt_bus)).all()

    # ── Query 2: uso del mes por BU y tipo de evento ──────────────────────────
    stmt_usage = (
        select(
            UsageEvent.bu_id,
            UsageEvent.event_type,
            func.sum(UsageEvent.quantity).label("total"),
        )
        .where(
            UsageEvent.created_at >= curr_start,
            UsageEvent.created_at < curr_end,
        )
        .group_by(UsageEvent.bu_id, UsageEvent.event_type)
    )
    usage_rows = (await db.execute(stmt_usage)).all()
    usage_map: dict[UUID, dict[str, int]] = {}
    for row in usage_rows:
        usage_map.setdefault(row.bu_id, {})[row.event_type] = int(row.total)

    # ── Query 3: planes activos por BU ────────────────────────────────────────
    stmt_plans = (
        select(BUPlan.bu_id, Plan)
        .join(Plan, Plan.id == BUPlan.plan_id)
        .where(BUPlan.ends_at.is_(None))
    )
    plan_rows = (await db.execute(stmt_plans)).all()
    plan_map: dict[UUID, Plan] = {row.bu_id: row.Plan for row in plan_rows}

    # ── Construir resultado ───────────────────────────────────────────────────
    bu_list: list[AdminBURow] = []
    totals = PeriodUsage()

    for row in bus_rows:
        bu      = row.BusinessUnit
        ev      = usage_map.get(bu.id, {})
        plan_db = plan_map.get(bu.id)

        usage = PeriodUsage(
            docs_uploaded=ev.get(DOC_UPLOADED, 0),
            docs_deleted=ev.get(DOC_DELETED, 0),
            extractions_run=ev.get(EXTRACTION_RUN, 0),
            tokens_consumed=ev.get(TOKENS_CONSUMED, 0),
            exports_done=ev.get(COLLECTION_EXPORT, 0),
        )

        totals.docs_uploaded    += usage.docs_uploaded
        totals.docs_deleted     += usage.docs_deleted
        totals.extractions_run  += usage.extractions_run
        totals.tokens_consumed  += usage.tokens_consumed
        totals.exports_done     += usage.exports_done

        bu_list.append(AdminBURow(
            bu_id=bu.id,
            bu_name=bu.name,
            bu_code=bu.code,
            is_active=bu.is_active,
            plan=PlanRead.model_validate(plan_db) if plan_db else None,
            current_month=usage,
            users_count=row.users_count,
        ))

    return AdminOverview(
        period_label=period_label,
        total_bus=len(bu_list),
        active_bus=sum(1 for b in bu_list if b.is_active),
        current_month_totals=totals,
        bus=bu_list,
    )
