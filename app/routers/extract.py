# app/routers/extract.py
import hashlib
import time
import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.db.connection import get_db
from app.db.models import PromptConfig, Extraction
from app.services.llm_client import call_llm_for_extraction, LLMExtractionError
from app.config import MAX_DOCUMENT_SIZE_BYTES

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/extract", tags=["extract"])


class ExtractRequest(BaseModel):
    config_id: UUID
    document_text: str
    document_name: Optional[str] = None
    collection_id: Optional[UUID] = None


class ExtractResponse(BaseModel):
    extraction_id: Optional[UUID] = None
    config_id: UUID
    result: List[Dict[str, Any]]


@router.post("/", response_model=ExtractResponse)
async def extract(payload: ExtractRequest, db: AsyncSession = Depends(get_db)):
    """
    Endpoint de extracción real:
    - Recibe un config_id y el texto del documento.
    - Carga la configuración de prompt desde la BD.
    - Construye el prompt y llama al LLM.
    - Devuelve el JSON estructurado validado.
    """
    
    # Validar tamaño del documento
    document_size = len(payload.document_text.encode('utf-8'))
    if document_size > MAX_DOCUMENT_SIZE_BYTES:
        size_mb = MAX_DOCUMENT_SIZE_BYTES / (1024 * 1024)
        raise HTTPException(
            status_code=413,
            detail=f"Documento demasiado grande. Máximo permitido: {size_mb:.1f} MB"
        )
    
    if document_size == 0:
        raise HTTPException(
            status_code=400,
            detail="El documento está vacío"
        )

    # 1) Buscar configuración en la tabla prompt_configs
    stmt = select(PromptConfig).where(
        PromptConfig.id == payload.config_id,
        PromptConfig.is_active.is_(True),
    )
    result = await db.execute(stmt)
    config = result.scalars().first()

    if not config:
        raise HTTPException(
            status_code=404,
            detail="Configuración de prompt no encontrada",
        )

    # 2) Variables desde la configuración almacenada (campo JSON)
    variables: List[Dict[str, Any]] = config.variables

    # Hash SHA-256 del texto del documento para trazabilidad y detección de duplicados
    document_hash = hashlib.sha256(payload.document_text.encode()).hexdigest()

    # 3) Llamar al LLM usando el motor de plantillas y el cliente de IA
    start_time = time.perf_counter()
    try:
        llm_result = await call_llm_for_extraction(
            document_text=payload.document_text,
            variables=variables,
            model=config.model,
            base_prompt=config.base_prompt,
        )
        latency_ms = int((time.perf_counter() - start_time) * 1000)
    except LLMExtractionError as e:
        latency_ms = int((time.perf_counter() - start_time) * 1000)

        # Registrar extracción fallida
        extraction = Extraction(
            prompt_config_id=config.id,
            document_name=payload.document_name,
            document_hash=document_hash,
            collection_id=payload.collection_id,
            prompt_sent="",
            raw_llm_response=None,
            validated_result=None,
            status="failed",
            retries=0,
            latency_ms=latency_ms,
            model_used=config.model,
            error_message=str(e),
        )

        try:
            db.add(extraction)
            await db.commit()
        except SQLAlchemyError as db_err:
            logger.exception("Error guardando extracción fallida")
            await db.rollback()

        raise HTTPException(status_code=500, detail=str(e))

    # 4) Registrar extracción exitosa
    extraction = Extraction(
        prompt_config_id=config.id,
        document_name=payload.document_name,
        document_hash=document_hash,
        collection_id=payload.collection_id,
        prompt_sent=llm_result["prompt_sent"],
        raw_llm_response=llm_result["raw_llm_response"],
        validated_result=llm_result["cleaned"],
        status="success",
        retries=0,
        latency_ms=latency_ms,
        model_used=config.model,
        error_message=None,
    )

    try:
        db.add(extraction)
        await db.commit()
        extraction_id = extraction.id
    except SQLAlchemyError as db_err:
        logger.exception("Error guardando extracción exitosa")
        await db.rollback()
        # Si falla el guardado pero la extracción fue bien, devolvemos igual el resultado
        extraction_id = None

    return ExtractResponse(
        extraction_id=extraction_id,
        config_id=payload.config_id,
        result=llm_result["cleaned"],
    )