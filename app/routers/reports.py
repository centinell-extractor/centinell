# app/routers/reports.py
"""
Router de reporting y gestión de planes comerciales.

Estructura:
  GET  /reports/me                      — bu_admin: uso de su propia BU
  GET  /reports/admin/overview          — admin_global: todas las BUs
  GET  /reports/admin/bu/{bu_id}        — admin_global: BU concreta
  PUT  /reports/admin/bu/{bu_id}/plan   — admin_global: asignar plan

  GET  /plans                           — lista planes disponibles
  POST /plans                           — crear plan (admin_global)
  PATCH /plans/{plan_id}                — actualizar plan (admin_global)
"""
from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.connection import get_db
from app.db.models import BUPlan, BusinessUnit, Plan, User
from app.dependencies.auth import (
    AuthContext,
    get_bu_auth_context,
    require_bu_roles,
    require_global_admin,
)
from app.schemas.usage import (
    AdminOverview,
    AssignPlanRequest,
    BUUsageSummary,
    PlanCreate,
    PlanRead,
    PlanUpdate,
)
from app.services.security import utcnow
from app.services.usage_service import get_admin_overview, get_bu_usage_summary

logger = logging.getLogger(__name__)

router = APIRouter(tags=["reports"])


# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║  PLANES — catálogo y gestión                                                ║
# ╚══════════════════════════════════════════════════════════════════════════════╝

@router.get("/plans", response_model=list[PlanRead], summary="Lista de planes disponibles")
async def list_plans(
    db: AsyncSession = Depends(get_db),
) -> list[PlanRead]:
    """
    Devuelve todos los planes activos del catálogo.
    Endpoint público (no requiere autenticación) para que el frontend
    pueda mostrar los planes disponibles sin login.
    """
    result = await db.execute(
        select(Plan)
        .where(Plan.is_active.is_(True))
        .order_by(Plan.price_monthly_cents)
    )
    return [PlanRead.model_validate(p) for p in result.scalars().all()]


@router.post(
    "/plans",
    response_model=PlanRead,
    status_code=status.HTTP_201_CREATED,
    summary="Crear plan (admin_global)",
)
async def create_plan(
    payload: PlanCreate,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_global_admin),
) -> PlanRead:
    """Crea un nuevo plan en el catálogo. Solo admin_global."""
    existing = await db.execute(select(Plan).where(Plan.code == payload.code))
    if existing.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Ya existe un plan con código '{payload.code}'",
        )

    plan = Plan(
        code=payload.code,
        display_name=payload.display_name,
        max_docs_per_month=payload.max_docs_per_month,
        max_extractions_per_month=payload.max_extractions_per_month,
        max_tokens_per_month=payload.max_tokens_per_month,
        max_users=payload.max_users,
        price_monthly_cents=payload.price_monthly_cents,
    )
    db.add(plan)
    await db.commit()
    await db.refresh(plan)
    logger.info("Plan creado: %s (%s)", plan.code, plan.id)
    return PlanRead.model_validate(plan)


@router.patch(
    "/plans/{plan_id}",
    response_model=PlanRead,
    summary="Actualizar plan (admin_global)",
)
async def update_plan(
    plan_id: UUID,
    payload: PlanUpdate,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_global_admin),
) -> PlanRead:
    """Actualiza campos de un plan existente. Solo admin_global."""
    plan = await db.get(Plan, plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan no encontrado")

    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(plan, field, value)

    db.add(plan)
    await db.commit()
    await db.refresh(plan)
    logger.info("Plan actualizado: %s (%s)", plan.code, plan.id)
    return PlanRead.model_validate(plan)


# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║  INFORMES — uso por BU                                                      ║
# ╚══════════════════════════════════════════════════════════════════════════════╝

@router.get(
    "/reports/me",
    response_model=BUUsageSummary,
    summary="Uso de mi BU (bu_admin)",
)
async def my_bu_usage(
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_bu_auth_context),
) -> BUUsageSummary:
    """
    Devuelve el resumen de uso de la BU activa del caller.
    Requiere rol bu_admin o admin_global.
    """
    require_bu_roles(
        auth,
        {"admin_global", "bu_admin"},
        "Solo bu_admin puede consultar informes de uso",
    )
    return await get_bu_usage_summary(db, auth.bu_id)


@router.get(
    "/reports/admin/overview",
    response_model=AdminOverview,
    summary="Visión global de todas las BUs (admin_global)",
)
async def admin_overview(
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_global_admin),
) -> AdminOverview:
    """
    Vista ejecutiva: todas las BUs con su uso del mes, plan asignado y usuarios.
    Solo admin_global. No requiere X-BU-ID.
    """
    return await get_admin_overview(db)


@router.get(
    "/reports/admin/bu/{bu_id}",
    response_model=BUUsageSummary,
    summary="Detalle de uso de una BU (admin_global)",
)
async def admin_bu_detail(
    bu_id: UUID,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_global_admin),
) -> BUUsageSummary:
    """
    Detalle completo de uso de cualquier BU: mes actual, mes anterior,
    tendencia diaria y estado de cuotas. Solo admin_global.
    """
    bu = await db.get(BusinessUnit, bu_id)
    if not bu:
        raise HTTPException(status_code=404, detail="BU no encontrada")
    return await get_bu_usage_summary(db, bu_id)


@router.put(
    "/reports/admin/bu/{bu_id}/plan",
    response_model=BUUsageSummary,
    summary="Asignar plan a una BU (admin_global)",
)
async def assign_plan_to_bu(
    bu_id: UUID,
    payload: AssignPlanRequest,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_global_admin),
) -> BUUsageSummary:
    """
    Asigna un plan a la BU.

    - Cierra el plan activo anterior (sets ends_at = now()).
    - Crea un nuevo registro activo con el plan indicado.
    - Devuelve el resumen de uso actualizado de la BU.

    Solo admin_global.
    """
    bu = await db.get(BusinessUnit, bu_id)
    if not bu:
        raise HTTPException(status_code=404, detail="BU no encontrada")

    plan = await db.get(Plan, payload.plan_id)
    if not plan or not plan.is_active:
        raise HTTPException(status_code=404, detail="Plan no encontrado o inactivo")

    # Cerrar plan activo anterior si existe
    prev_stmt = (
        select(BUPlan)
        .where(BUPlan.bu_id == bu_id, BUPlan.ends_at.is_(None))
    )
    prev_plans = (await db.execute(prev_stmt)).scalars().all()
    now = utcnow()
    for prev in prev_plans:
        prev.ends_at = now
        db.add(prev)

    # Crear nuevo plan activo
    new_assignment = BUPlan(
        bu_id=bu_id,
        plan_id=plan.id,
        starts_at=now,
        created_by=admin.id,
    )
    db.add(new_assignment)
    await db.commit()

    logger.info(
        "Plan '%s' asignado a BU %s por admin %s",
        plan.code, bu.code, admin.email,
    )
    return await get_bu_usage_summary(db, bu_id)
