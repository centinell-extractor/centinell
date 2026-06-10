# app/schemas/extraction.py
from pydantic import BaseModel, ConfigDict
from typing import Any, Dict, List, Optional
from uuid import UUID
from datetime import datetime

from app.schemas.billing_warning import QuotaWarning


class ExtractionRead(BaseModel):
    id: UUID
    prompt_config_id: UUID
    bu_id: Optional[UUID]
    document_id: Optional[UUID]
    collection_id: Optional[UUID]
    document_name: Optional[str]
    document_hash: Optional[str]
    prompt_sent: str
    raw_llm_response: Optional[str]
    validated_result: Optional[List[Dict[str, Any]]]
    status: str
    retries: int
    latency_ms: Optional[int]
    model_used: Optional[str]
    error_message: Optional[str]
    created_at: datetime
    quota_warning: Optional[QuotaWarning] = None  # Aviso de cuota si aplica

    model_config = ConfigDict(from_attributes=True)


class ExtractionValidateRequest(BaseModel):
    result: List[Dict[str, Any]]
