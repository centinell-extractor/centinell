from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ConfigBrief(BaseModel):
    config_id: UUID
    config_name: str
    position: int


class AssessmentCreate(BaseModel):
    name: str = Field(min_length=2, max_length=150)
    description: Optional[str] = Field(default=None, max_length=1000)
    config_ids: List[UUID] = Field(min_length=1)


class AssessmentUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=150)
    description: Optional[str] = Field(default=None, max_length=1000)
    config_ids: Optional[List[UUID]] = None
    is_active: Optional[bool] = None


class AssessmentRead(BaseModel):
    id: UUID
    bu_id: UUID
    name: str
    description: Optional[str]
    is_active: bool
    created_at: datetime
    configs: List[ConfigBrief] = []

    model_config = ConfigDict(from_attributes=True)


class AssessmentRunResult(BaseModel):
    config_id: str
    config_name: str
    position: int
    result: List[Dict[str, Any]]
    latency_ms: Optional[int] = None
    error: Optional[str] = None


class AssessmentRunRead(BaseModel):
    id: UUID
    assessment_id: Optional[UUID]
    assessment_name: Optional[str]
    bu_id: Optional[UUID]
    document_id: Optional[UUID]
    document_name: Optional[str]
    created_by_id: Optional[UUID] = None
    created_by_name: Optional[str] = None
    status: str
    combined_result: Optional[List[Dict[str, Any]]]
    error_message: Optional[str]
    latency_ms: Optional[int]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AssessmentRunRequest(BaseModel):
    document_text: str
    document_name: Optional[str] = None
    document_id: Optional[UUID] = None
