# app/routers/collections.py
import io
import logging
from typing import List, Optional
from uuid import UUID

import openpyxl
import openpyxl.utils
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select, desc, func, case
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.connection import get_db
from app.db.models import Collection, PromptConfig, Extraction
from app.schemas.collection import CollectionCreate, CollectionRead
from app.schemas.extraction import ExtractionRead

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/collections", tags=["collections"])


async def _collection_with_counts(collection: Collection, db: AsyncSession) -> CollectionRead:
    """Adjunta conteos de extracciones a un objeto Collection."""
    counts = await db.execute(
        select(
            func.count().label("total"),
            func.count(case((Extraction.status == "success", 1))).label("success_count"),
            func.count(case((Extraction.status == "failed", 1))).label("failed_count"),
            func.count(case((Extraction.status == "validated", 1))).label("validated_count"),
        ).where(Extraction.collection_id == collection.id)
    )
    row = counts.one()
    return CollectionRead(
        id=collection.id,
        name=collection.name,
        config_id=collection.config_id,
        created_at=collection.created_at,
        total_docs=row.total,
        success_count=row.success_count,
        failed_count=row.failed_count,
        validated_count=row.validated_count,
    )


@router.post("/", response_model=CollectionRead, status_code=201)
async def create_collection(payload: CollectionCreate, db: AsyncSession = Depends(get_db)):
    """Crea una nueva colección (agrupador de extracciones en lote)."""
    config_result = await db.execute(
        select(PromptConfig).where(
            PromptConfig.id == payload.config_id,
            PromptConfig.is_active.is_(True),
        )
    )
    if not config_result.scalars().first():
        raise HTTPException(status_code=404, detail="Configuración de prompt no encontrada o inactiva")

    collection = Collection(name=payload.name.strip(), config_id=payload.config_id)
    db.add(collection)
    await db.commit()
    await db.refresh(collection)
    return await _collection_with_counts(collection, db)


@router.get("/", response_model=List[CollectionRead])
async def list_collections(
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """Lista colecciones ordenadas de más reciente a más antigua."""
    result = await db.execute(
        select(Collection).order_by(desc(Collection.created_at)).limit(limit)
    )
    collections = result.scalars().all()
    return [await _collection_with_counts(c, db) for c in collections]


@router.get("/{collection_id}", response_model=CollectionRead)
async def get_collection(collection_id: UUID, db: AsyncSession = Depends(get_db)):
    """Devuelve detalle de una colección con conteos."""
    result = await db.execute(select(Collection).where(Collection.id == collection_id))
    collection = result.scalars().first()
    if not collection:
        raise HTTPException(status_code=404, detail="Colección no encontrada")
    return await _collection_with_counts(collection, db)


@router.get("/{collection_id}/extractions", response_model=List[ExtractionRead])
async def get_collection_extractions(
    collection_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Lista todas las extracciones de una colección."""
    result = await db.execute(
        select(Collection).where(Collection.id == collection_id)
    )
    if not result.scalars().first():
        raise HTTPException(status_code=404, detail="Colección no encontrada")

    exts = await db.execute(
        select(Extraction)
        .where(Extraction.collection_id == collection_id)
        .order_by(Extraction.created_at)
    )
    return exts.scalars().all()


@router.get("/{collection_id}/export/xlsx")
async def export_collection_xlsx(
    collection_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Exporta toda la colección como Excel.
    Cada fila = un documento. Cada columna = un campo extraído.
    """
    result = await db.execute(select(Collection).where(Collection.id == collection_id))
    collection = result.scalars().first()
    if not collection:
        raise HTTPException(status_code=404, detail="Colección no encontrada")

    exts_result = await db.execute(
        select(Extraction)
        .where(Extraction.collection_id == collection_id)
        .order_by(Extraction.created_at)
    )
    extractions = exts_result.scalars().all()

    # Recopilar columnas de campos dinámicamente
    field_cols: list[str] = []
    seen: set[str] = set()
    records = []
    for ext in extractions:
        data = ext.validated_result or []
        if not data and ext.raw_llm_response:
            import json
            try:
                parsed = json.loads(ext.raw_llm_response)
                if isinstance(parsed, list):
                    data = parsed
            except (json.JSONDecodeError, TypeError):
                pass

        rec = {
            "documento": ext.document_name or "",
            "estado": ext.status,
            "latencia_ms": ext.latency_ms or "",
            "fecha": ext.created_at.isoformat() if ext.created_at else "",
            "error": ext.error_message or "",
        }
        for row in data:
            t = row.get("title", "")
            rec[t] = row.get("answer", "")
            if t and t not in seen:
                seen.add(t)
                field_cols.append(t)
        records.append(rec)

    meta_cols = ["documento", "estado", "latencia_ms", "fecha", "error"]
    all_cols = meta_cols + field_cols

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Colección"
    ws.append(all_cols)
    for rec in records:
        ws.append([rec.get(c, "") for c in all_cols])
    for i, col in enumerate(all_cols, 1):
        ws.column_dimensions[openpyxl.utils.get_column_letter(i)].width = max(15, len(col) + 4)

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)

    safe_name = "".join(c if c.isalnum() or c in "-_." else "_" for c in collection.name)
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="coleccion_{safe_name}.xlsx"'},
    )
