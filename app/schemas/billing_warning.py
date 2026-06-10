# app/schemas/billing_warning.py
"""Schemas para avisos de cuota y billing."""
from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, ConfigDict


class QuotaWarningBase(BaseModel):
    """Aviso base de cuota."""
    type: str  # "approaching_limit" o "overage_charge"
    metric: str  # "documents", "extractions", "users"
    current_usage: int
    limit: int


class ApproachingLimitWarning(QuotaWarningBase):
    """Aviso cuando se acerca al límite (80%, 90%, 95%)."""
    type: str = "approaching_limit"
    percentage: int  # 80, 90, 95
    days_left: int  # Días hasta fin de mes

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "type": "approaching_limit",
                "metric": "documents",
                "current_usage": 80,
                "limit": 100,
                "percentage": 80,
                "days_left": 4,
            }
        }
    )


class OverageChargeWarning(QuotaWarningBase):
    """Aviso cuando se incurre en cargo por overage."""
    type: str = "overage_charge"
    overage_units: int  # Cantidad que excede el límite
    overage_cost_eur: float  # Costo en euros (ej: 0.20)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "type": "overage_charge",
                "metric": "documents",
                "current_usage": 101,
                "limit": 100,
                "overage_units": 1,
                "overage_cost_eur": 0.20,
            }
        }
    )


QuotaWarning = ApproachingLimitWarning | OverageChargeWarning
