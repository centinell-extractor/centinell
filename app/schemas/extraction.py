# app/schemas/extraction.py
from pydantic import BaseModel, ConfigDict
from typing import Any, Dict, List, Optional
from uuid import UUID
from datetime import datetime


class ExtractionRead(BaseModel):
    id: UUID
    prompt_config_id: UUID
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

    model_config = ConfigDict(from_attributes=True)


class ExtractionValidateRequest(BaseModel):
    result: List[Dict[str, Any]]
