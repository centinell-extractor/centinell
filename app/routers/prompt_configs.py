# app/routers/prompt_configs.py
import re
import uuid
import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from app.db.connection import get_db
from app.db.models import BusinessUnit, PromptConfig
from app.dependencies.auth import AuthContext, get_bu_auth_context, require_bu_roles_with_audit
from app.schemas.prompt_config import PromptConfigCreate, PromptConfigRead
from app.services.template_engine import get_variable_placeholder_token, parse_var_refs

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/prompt-configs", tags=["prompt-configs"])


def _validate_variable_deps(variables) -> None:
    """
    Valida que las referencias {{VarName}} en las descripciones:
    - Apunten a variables que existen en el mismo config.
    - No formen ciclos.
    Lanza HTTPException 400 si hay algún error.
    """
    all_names = {v.name for v in variables}

    _raw_ref_re = re.compile(r"\{\{(\w+)\}\}")

    # Comprobar que todas las referencias existen
    for v in variables:
        raw_refs = set(_raw_ref_re.findall(v.description or ""))
        unknown_refs = raw_refs - all_names
        if unknown_refs:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"La variable '{v.name}' referencia variables inexistentes: "
                    f"{', '.join(sorted(unknown_refs))}. "
                    "Asegúrate de que los nombres coincidan exactamente."
                ),
            )

    # Detectar ciclos con DFS
    deps = {v.name: parse_var_refs(v.description, all_names) for v in variables}
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {name: WHITE for name in all_names}
    path = []

    def dfs(name: str) -> None:
        color[name] = GRAY
        path.append(name)
        for dep in deps.get(name, set()):
            if color[dep] == GRAY:
                cycle = " → ".join(path[path.index(dep):] + [dep])
                raise HTTPException(
                    status_code=400,
                    detail=f"Dependencia circular detectada: {cycle}",
                )
            if color[dep] == WHITE:
                dfs(dep)
        path.pop()
        color[name] = BLACK

    for name in all_names:
        if color[name] == WHITE:
            dfs(name)


@router.post("/", response_model=PromptConfigRead, status_code=201)
async def create_prompt_config(
    data: PromptConfigCreate,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_bu_auth_context),
):
    await require_bu_roles_with_audit(
        auth,
        {"admin_global", "bu_admin"},
        "No tienes permisos para configurar prompts en esta BU",
        db,
        action="prompt_config.create",
        resource_type="prompt_config",
    )
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

        _validate_variable_deps(data.variables)

        variables_dicts = [v.model_dump() for v in data.variables]

        prompt_config = PromptConfig(
            id=uuid.uuid4(),
            bu_id=auth.bu_id,
            name=data.name,
            description=data.description,
            base_prompt=data.base_prompt,
            variables=variables_dicts,
            model=data.model,
            temperature=float(data.temperature),
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
    auth: AuthContext = Depends(get_bu_auth_context),
):
    """
    Lista todas las configuraciones de prompts con paginación.
    Ordenado por fecha de creación (más recientes primero).
    """
    try:
        stmt = (
            select(PromptConfig)
            .where(
                PromptConfig.bu_id == auth.bu_id,
                PromptConfig.is_active.is_(True),
            )
            .order_by(desc(PromptConfig.created_at))
            .offset(skip)
            .limit(limit)
        )
        result = await db.execute(stmt)
        rows = result.scalars().all()
        return rows
    except Exception as exc:
        logger.error(f"Error al listar PromptConfigs: {exc}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error interno: {str(exc)}"
        )


@router.delete("/{config_id}", status_code=204)
async def delete_prompt_config(
    config_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_bu_auth_context),
):
    await require_bu_roles_with_audit(
        auth,
        {"admin_global", "bu_admin"},
        "No tienes permisos para configurar prompts en esta BU",
        db,
        action="prompt_config.delete",
        resource_type="prompt_config",
        resource_id=str(config_id),
    )

    result = await db.execute(
        select(PromptConfig).where(
            PromptConfig.id == config_id,
            PromptConfig.bu_id == auth.bu_id,
            PromptConfig.is_active.is_(True),
        )
    )
    prompt_config = result.scalars().first()

    if not prompt_config:
        raise HTTPException(status_code=404, detail="Configuración no encontrada")

    prompt_config.is_active = False
    db.add(prompt_config)
    await db.commit()


@router.patch("/{config_id}", response_model=PromptConfigRead)
async def update_prompt_config(
    config_id: uuid.UUID,
    data: PromptConfigCreate,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_bu_auth_context),
):
    await require_bu_roles_with_audit(
        auth,
        {"admin_global", "bu_admin"},
        "No tienes permisos para configurar prompts en esta BU",
        db,
        action="prompt_config.update",
        resource_type="prompt_config",
        resource_id=str(config_id),
    )
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

        _validate_variable_deps(data.variables)

        result = await db.execute(
            select(PromptConfig).where(
                PromptConfig.id == config_id,
                PromptConfig.bu_id == auth.bu_id,
            )
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


@router.post("/{config_id}/copy-to-bu/{target_bu_id}", response_model=PromptConfigRead, status_code=201)
async def copy_prompt_config_to_bu(
    config_id: uuid.UUID,
    target_bu_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_bu_auth_context),
):
    await require_bu_roles_with_audit(
        auth,
        {"admin_global"},
        "Solo admin_global puede copiar configuraciones entre BUs",
        db,
        action="prompt_config.copy_to_bu",
        resource_type="prompt_config",
        resource_id=str(config_id),
    )

    result = await db.execute(
        select(PromptConfig).where(
            PromptConfig.id == config_id,
            PromptConfig.bu_id == auth.bu_id,
            PromptConfig.is_active.is_(True),
        )
    )
    source = result.scalars().first()
    if not source:
        raise HTTPException(status_code=404, detail="Configuracion origen no encontrada o no pertenece a esta BU")

    target_bu = await db.get(BusinessUnit, target_bu_id)
    if not target_bu or not target_bu.is_active:
        raise HTTPException(status_code=404, detail="BU destino no encontrada")

    copy = PromptConfig(
        id=uuid.uuid4(),
        bu_id=target_bu_id,
        name=source.name,
        description=source.description,
        base_prompt=source.base_prompt,
        variables=source.variables,
        model=source.model,
        temperature=source.temperature,
        version=1,
        is_active=True,
    )
    db.add(copy)
    await db.commit()
    await db.refresh(copy)
    return copy