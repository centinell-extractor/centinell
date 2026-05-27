# app/schemas/collection.py
from pydantic import BaseModel, ConfigDict
from typing import Optional
from uuid import UUID
from datetime import datetime


class CollectionCreate(BaseModel):
    name: str
    config_id: UUID


class CollectionRead(BaseModel):
    id: UUID
    bu_id: UUID
    name: str
    config_id: UUID
    created_at: datetime
    total_docs: int = 0
    success_count: int = 0
    failed_count: int = 0
    validated_count: int = 0

    model_config = ConfigDict(from_attributes=True)
