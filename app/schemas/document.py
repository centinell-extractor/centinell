from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class DocumentRead(BaseModel):
    id: UUID
    bu_id: UUID
    bu_code: str | None = None
    created_by_name: str | None = None
    title: str
    filename: str
    mime_type: str
    size_bytes: int
    storage_key: str
    created_by: UUID | None
    created_at: datetime
    status: str          # pending | processing | processed | failed
    ocr_text: str | None
    ocr_error: str | None

    model_config = ConfigDict(from_attributes=True)


class DocumentListResponse(BaseModel):
    items: list[DocumentRead]
    total: int
