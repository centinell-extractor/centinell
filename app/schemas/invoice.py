# app/schemas/invoice.py
"""Schemas para facturas."""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class InvoiceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    bu_id: UUID
    period_month: date
    plan_id: Optional[UUID] = None

    plan_price_cents: int
    overage_docs: int
    overage_docs_cost_cents: int
    overage_extractions: int
    overage_extractions_cost_cents: int
    overage_users: int
    overage_users_cost_cents: int

    total_cents: int
    status: str  # pending, paid, overdue, suspended
    paid_at: Optional[datetime] = None
    created_at: datetime
    created_by: Optional[UUID] = None


class InvoiceListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    period_month: date
    total_cents: int
    status: str
    paid_at: Optional[datetime] = None


class MarkInvoicePaidRequest(BaseModel):
    pass
