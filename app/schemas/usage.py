# app/schemas/usage.py
"""
Schemas para el sistema de tracking de uso y planes comerciales.
"""
from __future__ import annotations

from datetime import date
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# ── Planes ────────────────────────────────────────────────────────────────────

class PlanRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    code: str
    display_name: str
    max_docs_per_month: Optional[int] = None
    max_extractions_per_month: Optional[int] = None
    max_tokens_per_month: Optional[int] = None
    max_users: Optional[int] = None
    price_monthly_cents: int = 0
    is_active: bool = True


class PlanCreate(BaseModel):
    code: str = Field(..., min_length=2, max_length=40, pattern=r"^[a-z0-9_-]+$")
    display_name: str = Field(..., min_length=2, max_length=128)
    max_docs_per_month: Optional[int] = Field(None, ge=1)
    max_extractions_per_month: Optional[int] = Field(None, ge=1)
    max_tokens_per_month: Optional[int] = Field(None, ge=1)
    max_users: Optional[int] = Field(None, ge=1)
    price_monthly_cents: int = Field(0, ge=0)


class PlanUpdate(BaseModel):
    display_name: Optional[str] = Field(None, min_length=2, max_length=128)
    max_docs_per_month: Optional[int] = Field(None, ge=1)
    max_extractions_per_month: Optional[int] = Field(None, ge=1)
    max_tokens_per_month: Optional[int] = Field(None, ge=1)
    max_users: Optional[int] = Field(None, ge=1)
    price_monthly_cents: Optional[int] = Field(None, ge=0)
    is_active: Optional[bool] = None


class AssignPlanRequest(BaseModel):
    plan_id: UUID


# ── Métricas de uso ───────────────────────────────────────────────────────────

class PeriodUsage(BaseModel):
    """Métricas de uso para un período (mes, semana, etc.)."""
    docs_uploaded: int = 0
    docs_deleted: int = 0
    extractions_run: int = 0
    tokens_consumed: int = 0
    exports_done: int = 0


class QuotaStatus(BaseModel):
    """
    Estado de consumo vs. límites del plan activo.
    Los campos *_pct son None cuando el límite es ilimitado (NULL en el plan).
    """
    docs_used: int
    docs_limit: Optional[int]
    docs_pct: Optional[float]

    extractions_used: int
    extractions_limit: Optional[int]
    extractions_pct: Optional[float]

    tokens_used: int
    tokens_limit: Optional[int]
    tokens_pct: Optional[float]


class DailyPoint(BaseModel):
    """Punto de datos diario para gráficas de tendencia."""
    date: date
    docs_uploaded: int = 0
    extractions_run: int = 0
    tokens_consumed: int = 0


# ── Resúmenes ─────────────────────────────────────────────────────────────────

class BUUsageSummary(BaseModel):
    """
    Resumen completo de uso de una BU:
    - Plan activo y estado de cuotas
    - Mes actual y mes anterior
    - Tendencia diaria (últimos 30 días)
    """
    bu_id: UUID
    bu_name: str
    bu_code: str
    plan: Optional[PlanRead] = None
    quota_status: Optional[QuotaStatus] = None
    current_month: PeriodUsage
    last_month: PeriodUsage
    daily_trend: List[DailyPoint]


class AdminBURow(BaseModel):
    """Fila de la tabla de visión global de todas las BUs."""
    bu_id: UUID
    bu_name: str
    bu_code: str
    is_active: bool
    plan: Optional[PlanRead] = None
    current_month: PeriodUsage
    users_count: int


class AdminOverview(BaseModel):
    """
    Vista ejecutiva de todas las BUs para admin_global.
    Incluye totales globales del mes en curso y desglose por BU.
    """
    period_label: str               # e.g. "Mayo 2026"
    total_bus: int
    active_bus: int
    current_month_totals: PeriodUsage
    bus: List[AdminBURow]
