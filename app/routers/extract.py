# app/routers/extract.py
import hashlib
import time
import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.db.connection import AsyncSessionLocal, get_db
from app.db.models import Document, Extraction, PromptConfig
from app.dependencies.auth import AuthContext, get_bu_auth_context, require_bu_roles_with_audit
from app.services.llm_client import call_llm_for_extraction_chained, LLMExtractionError
from app.services.usage_service import EXTRACTION_RUN, TOKENS_CONSUMED, track_event
from app.config import MAX_DOCUMENT_SIZE_BYTES

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/extract", tags=["extract"])


class ExtractRequest(BaseModel):
    config_id: UUID
    document_text: str
    document_name: Optional[str] = None
    collection_id: Optional[UUID] = None
    document_id: Optional[UUID] = None


class ExtractResponse(BaseModel):
    extraction_id: Optional[UUID] = None
    config_id: UUID
    result: List[Dict[str, Any]]


async def _run_extraction_background(
    extraction_id: UUID,
    document_text: str,
    variables: List[Dict[str, Any]],
    model: str,
    base_prompt: str,
    document_name: Optional[str],
    bu_id: UUID,
    user_id: Optional[UUID],
) -> None:
    """
    Tarea de background: llama al LLM, actualiza el registro de extracción
    y registra los eventos de uso (extraction.run + tokens.consumed).
    """
    async with AsyncSessionLocal() as db:
        start_time = time.perf_counter()
        try:
            llm_result = await call_llm_for_extraction_chained(
                document_text=document_text,
                variables=variables,
                model=model,
                base_prompt=base_prompt,
            )
            latency_ms = int((time.perf_counter() - start_time) * 1000)

            extraction = await db.get(Extraction, extraction_id)
            if extraction:
                extraction.prompt_sent = llm_result["prompt_sent"]
                extraction.raw_llm_response = llm_result["raw_llm_response"]
                extraction.validated_result = llm_result["cleaned"]
                extraction.status = "success"
                extraction.latency_ms = latency_ms
                db.add(extraction)

                # ── Tracking de uso ──────────────────────────────────────────
                await track_event(
                    db,
                    bu_id=bu_id,
                    event_type=EXTRACTION_RUN,
                    user_id=user_id,
                    metadata={
                        "extraction_id": str(extraction_id),
                        "model": model,
                        "latency_ms": latency_ms,
                        "status": "success",
                    },
                )
                total_tokens = llm_result.get("total_tokens", 0)
                if total_tokens > 0:
                    await track_event(
                        db,
                        bu_id=bu_id,
                        event_type=TOKENS_CONSUMED,
                        quantity=total_tokens,
                        user_id=user_id,
                        metadata={
                            "model": model,
                            "prompt_tokens": llm_result.get("prompt_tokens", 0),
                            "completion_tokens": llm_result.get("completion_tokens", 0),
                            "extraction_id": str(extraction_id),
                        },
                    )

                await db.commit()

        except Exception as exc:
            latency_ms = int((time.perf_counter() - start_time) * 1000)
            logger.exception("Extracción background fallida para %s", extraction_id)
            extraction = await db.get(Extraction, extraction_id)
            if extraction:
                extraction.status = "failed"
                extraction.latency_ms = latency_ms
                extraction.error_message = str(exc)[:500]
                db.add(extraction)

                # Registrar también las extracciones fallidas para métricas reales
                await track_event(
                    db,
                    bu_id=bu_id,
                    event_type=EXTRACTION_RUN,
                    user_id=user_id,
                    metadata={
                        "extraction_id": str(extraction_id),
                        "model": model,
                        "latency_ms": latency_ms,
                        "status": "failed",
                    },
                )

                await db.commit()


@router.post("/", response_model=ExtractResponse)
async def extract(
    payload: ExtractRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_bu_auth_context),
):
    """
    Inicia una extracción de forma asíncrona.
    Devuelve inmediatamente con status='pending' y un extraction_id.
    Sondea GET /extractions/{id} hasta que status sea 'success' o 'failed'.
    """

    await require_bu_roles_with_audit(
        auth,
        {"admin_global", "bu_admin", "bu_user"},
        "No tienes permisos para ejecutar extracciones en esta BU",
        db,
        action="extract.run",
        resource_type="extraction",
    )

    document_size = len(payload.document_text.encode('utf-8'))
    if document_size > MAX_DOCUMENT_SIZE_BYTES:
        size_mb = MAX_DOCUMENT_SIZE_BYTES / (1024 * 1024)
        raise HTTPException(status_code=413, detail=f"Documento demasiado grande. Máximo: {size_mb:.1f} MB")

    if document_size == 0:
        raise HTTPException(status_code=400, detail="El documento está vacío")

    stmt = select(PromptConfig).where(
        PromptConfig.id == payload.config_id,
        PromptConfig.bu_id == auth.bu_id,
        PromptConfig.is_active.is_(True),
    )
    result = await db.execute(stmt)
    config = result.scalars().first()
    if not config:
        raise HTTPException(status_code=404, detail="Configuración de prompt no encontrada")

    if payload.document_id is not None:
        doc_result = await db.execute(
            select(Document).where(Document.id == payload.document_id, Document.bu_id == auth.bu_id)
        )
        document = doc_result.scalars().first()
        if not document:
            raise HTTPException(status_code=404, detail="Documento no encontrado en esta BU")
    else:
        document = None

    variables: List[Dict[str, Any]] = config.variables
    document_hash = hashlib.sha256(payload.document_text.encode()).hexdigest()
    document_name = payload.document_name or (document.filename if document else None)

    extraction = Extraction(
        prompt_config_id=config.id,
        bu_id=auth.bu_id,
        document_id=payload.document_id,
        document_name=document_name,
        document_hash=document_hash,
        collection_id=payload.collection_id,
        prompt_sent="",
        raw_llm_response=None,
        validated_result=None,
        status="pending",
        retries=0,
        latency_ms=None,
        model_used=config.model,
        error_message=None,
    )

    try:
        db.add(extraction)
        await db.commit()
        await db.refresh(extraction)
    except SQLAlchemyError:
        logger.exception("Error creando registro de extracción")
        await db.rollback()
        raise HTTPException(status_code=500, detail="Error interno al crear la extracción")

    background_tasks.add_task(
        _run_extraction_background,
        extraction.id,
        payload.document_text,
        variables,
        config.model,
        config.base_prompt,
        document_name,
        auth.bu_id,
        auth.actor_user_id,
    )

    return ExtractResponse(
        extraction_id=extraction.id,
        config_id=payload.config_id,
        result=[],
    )