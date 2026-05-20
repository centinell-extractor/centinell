# app/routers/extract_test.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any, Optional

from app.services.llm_client import call_llm_for_extraction, LLMExtractionError

router = APIRouter(prefix="/extract-test", tags=["extract-test"])


class VariableInput(BaseModel):
    name: str
    description: str
    required: bool = True
    type: str = "string"
    validation_regex: Optional[str] = None
    max_length: Optional[int] = None


class ExtractTestRequest(BaseModel):
    document_text: str
    variables: List[VariableInput]


@router.post("/")
async def extract_test(payload: ExtractTestRequest):
    try:
        variables_dicts: List[Dict[str, Any]] = [v.model_dump() for v in payload.variables]
        result = await call_llm_for_extraction(
            document_text=payload.document_text,
            variables=variables_dicts,
        )
        return {"result": result}
    except LLMExtractionError as e:
        raise HTTPException(status_code=500, detail=str(e))