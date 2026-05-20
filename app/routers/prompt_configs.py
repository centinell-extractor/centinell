# app/routers/prompt_configs.py
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from typing import List
import uuid
import logging

from app.db.connection import get_db
from app.db.models import PromptConfig
from app.schemas.prompt_config import PromptConfigCreate, PromptConfigRead
from app.services.template_engine import get_variable_placeholder_token

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/prompt-configs", tags=["prompt-configs"])


@router.post("/", response_model=PromptConfigRead, status_code=201)
async def create_prompt_config(
    data: PromptConfigCreate,
    db: AsyncSession = Depends(get_db),
):
    try:
        try:
            placeholder_token = get_variable_placeholder_token(data.base_prompt)
        except ValueError as exc:
            raise HTTPException(
                status_code=400,
                detail=str(exc),
            ) from exc

        if not placeholder_token:
            raise HTTPException(
                status_code=400,
                detail="El base_prompt debe contener un placeholder {{...}} para variables",
            )

        names = [v.name for v in data.variables]
        if len(names) != len(set(names)):
            raise HTTPException(
                status_code=400,
                detail="Hay variables con nombres duplicados",
            )

        variables_dicts = [v.model_dump() for v in data.variables]

        prompt_config = PromptConfig(
            id=uuid.uuid4(),
            name=data.name,
            description=data.description,
            base_prompt=data.base_prompt,
            variables=variables_dicts,
            model=data.model,
            temperature=int(data.temperature),
        )

        db.add(prompt_config)
        
        await db.flush()
        
        await db.commit()
        
        await db.refresh(prompt_config)
        return prompt_config

    except HTTPException:
        raise
    except Exception as exc:
        await db.rollback()
        logger.exception("Error creando PromptConfig")
        raise HTTPException(
            status_code=500,
            detail=f"Error interno: {str(exc)}"
        )


@router.get("/", response_model=List[PromptConfigRead])
async def list_prompt_configs(
    skip: int = Query(0, ge=0, description="Número de registros a saltar"),
    limit: int = Query(50, ge=1, le=500, description="Número máximo de registros a devolver"),
    db: AsyncSession = Depends(get_db),
):
    """
    Lista todas las configuraciones de prompts con paginación.
    Ordenado por fecha de creación (más recientes primero).
    """
    try:
        stmt = select(PromptConfig).order_by(desc(PromptConfig.created_at)).offset(skip).limit(limit)
        result = await db.execute(stmt)
        rows = result.scalars().all()
        return rows
    except Exception as exc:
        logger.error(f"Error al listar PromptConfigs: {exc}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error interno: {str(exc)}"
        )


@router.patch("/{config_id}", response_model=PromptConfigRead)
async def update_prompt_config(
    config_id: uuid.UUID,
    data: PromptConfigCreate,
    db: AsyncSession = Depends(get_db),
):
    try:
        try:
            placeholder_token = get_variable_placeholder_token(data.base_prompt)
        except ValueError as exc:
            raise HTTPException(
                status_code=400,
                detail=str(exc),
            ) from exc

        if not placeholder_token:
            raise HTTPException(
                status_code=400,
                detail="El base_prompt debe contener un placeholder {{...}} para variables",
            )

        names = [v.name for v in data.variables]
        if len(names) != len(set(names)):
            raise HTTPException(
                status_code=400,
                detail="Hay variables con nombres duplicados",
            )

        result = await db.execute(
            select(PromptConfig).where(PromptConfig.id == config_id)
        )
        prompt_config = result.scalars().first()

        if not prompt_config:
            raise HTTPException(status_code=404, detail="Configuración no encontrada")

        variables_dicts = [v.model_dump() for v in data.variables]

        prompt_config.name = data.name
        prompt_config.description = data.description
        prompt_config.base_prompt = data.base_prompt
        prompt_config.variables = variables_dicts
        prompt_config.model = data.model
        prompt_config.temperature = int(data.temperature)
        prompt_config.version = (prompt_config.version or 1) + 1

        db.add(prompt_config)
        await db.commit()
        await db.refresh(prompt_config)
        return prompt_config

    except HTTPException:
        raise
    except Exception as exc:
        await db.rollback()
        logger.exception("Error actualizando PromptConfig")
        raise HTTPException(
            status_code=500,
            detail=f"Error interno: {str(exc)}"
        )