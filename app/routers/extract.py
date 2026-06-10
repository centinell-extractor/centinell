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
from app.schemas.billing_warning import QuotaWarning
from app.services.billing_service import QuotaExceededError, check_quota, record_overage
from app.services.llm_client import call_llm_for_extraction_chained, LLMExtractionError
from app.services.usage_service import EXTRACTION_RUN, TOKENS_CONSUMED, track_event
from app.services.webhook import dispatch as webhook_dispatch
from app.services.email import send_extraction_complete_email
from app.services.field_validator import validate_result
from app.db.models import User as UserModel
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
    quota_warning: Optional[QuotaWarning] = None  # Aviso de cuota si aplica


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
            # Verificación defensiva: el registro puede haberse eliminado mientras el LLM procesaba
            extraction = await db.get(Extraction, extraction_id)
            if not extraction:
                logger.warning("Extracción %s ya no existe en BD; descartando resultado LLM", extraction_id)
                return

            llm_result = await call_llm_for_extraction_chained(
                document_text=document_text,
                variables=variables,
                model=model,
                base_prompt=base_prompt,
            )
            latency_ms = int((time.perf_counter() - start_time) * 1000)

            extraction = await db.get(Extraction, extraction_id)
            if extraction:
                cleaned = llm_result["cleaned"] or []
                annotated, has_errors = validate_result(variables, cleaned)
                extraction.prompt_sent = llm_result["prompt_sent"]
                extraction.raw_llm_response = llm_result["raw_llm_response"]
                extraction.validated_result = annotated
                extraction.status = "pending_review" if has_errors else "success"
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

            # Email de notificación al usuario si lo tiene activado
            if user_id:
                user_obj = await db.get(UserModel, user_id)
                if user_obj and user_obj.notify_on_completion:
                    await send_extraction_complete_email(
                        user_obj.email,
                        extraction.document_name or "documento",
                        "success",
                        str(extraction_id),
                    )

            # Webhook: extracción completada
            await webhook_dispatch(bu_id, "extraction.completed", {
                "extraction_id": str(extraction_id),
                "document_id": str(extraction.document_id) if extraction and extraction.document_id else None,
                "document_name": extraction.document_name if extraction else None,
                "status": "success",
                "latency_ms": latency_ms,
            })

        except Exception as exc:
            latency_ms = int((time.perf_counter() - start_time) * 1000)
            logger.exception("Extracción background fallida para %s", extraction_id)
            extraction = await db.get(Extraction, extraction_id)
            if extraction:
                extraction.status = "failed"
                extraction.latency_ms = latency_ms
                extraction.error_message = str(exc)[:500]
                db.add(extraction)

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

            # Webhook: extracción fallida
            await webhook_dispatch(bu_id, "extraction.failed", {
                "extraction_id": str(extraction_id),
                "document_name": extraction.document_name if extraction else None,
                "error": str(exc)[:200],
            })


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

    # Verificar cuota de extracciones
    try:
        _, overage_cost_cents = await check_quota(db, auth.bu_id, "extraction.run", quantity=1)
    except QuotaExceededError as e:
        raise HTTPException(status_code=429, detail=str(e))

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

        # Registrar overage si aplica
        if overage_cost_cents > 0:
            await record_overage(db, auth.bu_id, "extraction.run", quantity=1, cost_cents=overage_cost_cents)

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
        quota_warning=quota_warning,
    )


class BatchExtractRequest(BaseModel):
    config_id: UUID
    document_ids: List[UUID]


class BatchExtractResponse(BaseModel):
    queued: int
    extraction_ids: List[UUID]
    skipped: List[UUID]  # docs sin texto OCR procesado


@router.post("/batch", response_model=BatchExtractResponse, status_code=202)
async def batch_extract(
    payload: BatchExtractRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_bu_auth_context),
):
    """Encola extracciones sobre múltiples documentos con la misma configuración."""
    await require_bu_roles_with_audit(
        auth,
        {"admin_global", "bu_admin", "bu_user"},
        "No tienes permisos para ejecutar extracciones en esta BU",
        db,
        action="extract.batch",
        resource_type="extraction",
    )

    config_res = await db.execute(
        select(PromptConfig).where(
            PromptConfig.id == payload.config_id,
            PromptConfig.bu_id == auth.bu_id,
            PromptConfig.is_active.is_(True),
        )
    )
    config = config_res.scalars().first()
    if not config:
        raise HTTPException(status_code=404, detail="Configuración no encontrada")

    docs_res = await db.execute(
        select(Document).where(
            Document.id.in_(payload.document_ids),
            Document.bu_id == auth.bu_id,
        )
    )
    docs = {d.id: d for d in docs_res.scalars().all()}

    extraction_ids: List[UUID] = []
    skipped: List[UUID] = []

    for doc_id in payload.document_ids:
        doc = docs.get(doc_id)
        if not doc or doc.status != "processed" or not doc.ocr_text:
            skipped.append(doc_id)
            continue

        extraction = Extraction(
            prompt_config_id=config.id,
            bu_id=auth.bu_id,
            document_id=doc.id,
            document_name=doc.filename,
            document_hash=doc.sha256,
            prompt_sent="",
            status="pending",
            retries=0,
            model_used=config.model,
        )
        db.add(extraction)
        await db.flush()
        extraction_ids.append(extraction.id)

        background_tasks.add_task(
            _run_extraction_background,
            extraction.id,
            doc.ocr_text,
            config.variables,
            config.model,
            config.base_prompt,
            doc.filename,
            auth.bu_id,
            auth.actor_user_id,
        )

    await db.commit()
    return BatchExtractResponse(
        queued=len(extraction_ids),
        extraction_ids=extraction_ids,
        skipped=skipped,
    )