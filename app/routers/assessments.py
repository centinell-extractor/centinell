import asyncio
import csv
import io
import time
import logging
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.connection import AsyncSessionLocal, get_db
from app.db.models import Assessment, AssessmentConfig, AssessmentRun, PromptConfig
from app.dependencies.auth import AuthContext, get_bu_auth_context, require_bu_roles_with_audit
from app.schemas.assessment import (
    AssessmentCreate,
    AssessmentRead,
    AssessmentRunRead,
    AssessmentRunRequest,
    AssessmentUpdate,
    ConfigBrief,
)
from app.services.llm_client import call_llm_for_extraction_chained
from app.services.run_enricher import enrich_assessment_runs
from app.services.webhook import dispatch as webhook_dispatch
from app.services.email import send_assessment_complete_email
from app.db.models import User as UserModel

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/assessments", tags=["assessments"])


async def _load_assessment_with_configs(db: AsyncSession, assessment_id: UUID, bu_id: UUID) -> AssessmentRead | None:
    result = await db.execute(
        select(Assessment).where(Assessment.id == assessment_id, Assessment.bu_id == bu_id)
    )
    assessment = result.scalars().first()
    if not assessment:
        return None

    cfg_result = await db.execute(
        select(AssessmentConfig, PromptConfig)
        .join(PromptConfig, PromptConfig.id == AssessmentConfig.config_id)
        .where(AssessmentConfig.assessment_id == assessment_id)
        .order_by(AssessmentConfig.position)
    )
    configs = [
        ConfigBrief(config_id=ac.config_id, config_name=pc.name, position=ac.position)
        for ac, pc in cfg_result.all()
    ]

    return AssessmentRead(
        id=assessment.id,
        bu_id=assessment.bu_id,
        name=assessment.name,
        description=assessment.description,
        is_active=assessment.is_active,
        created_at=assessment.created_at,
        configs=configs,
    )


async def _run_assessment_background(
    run_id: UUID,
    document_text: str,
    config_entries: list[dict],
) -> None:
    async with AsyncSessionLocal() as db:
        run = await db.get(AssessmentRun, run_id)
        if not run:
            return
        run.status = "processing"
        db.add(run)
        await db.commit()

        start = time.perf_counter()
        try:
            async def _run_one(entry: dict) -> dict:
                t0 = time.perf_counter()
                try:
                    llm = await call_llm_for_extraction_chained(
                        document_text=document_text,
                        variables=entry["variables"],
                        model=entry["model"],
                        base_prompt=entry["base_prompt"],
                    )
                    return {
                        "config_id": entry["config_id"],
                        "config_name": entry["config_name"],
                        "position": entry["position"],
                        "result": llm["cleaned"],
                        "latency_ms": int((time.perf_counter() - t0) * 1000),
                        "error": None,
                    }
                except Exception as exc:
                    return {
                        "config_id": entry["config_id"],
                        "config_name": entry["config_name"],
                        "position": entry["position"],
                        "result": [],
                        "latency_ms": int((time.perf_counter() - t0) * 1000),
                        "error": str(exc)[:300],
                    }

            combined = await asyncio.gather(*[_run_one(e) for e in config_entries])
            combined = sorted(combined, key=lambda x: x["position"])

            run = await db.get(AssessmentRun, run_id)
            if run:
                run.status = "success"
                run.combined_result = combined
                run.latency_ms = int((time.perf_counter() - start) * 1000)
                db.add(run)
                await db.commit()

                if run.created_by:
                    user_obj = await db.get(UserModel, run.created_by)
                    if user_obj and user_obj.notify_on_completion:
                        await send_assessment_complete_email(
                            user_obj.email,
                            run.assessment_name or "assessment",
                            run.document_name or "documento",
                            "success",
                            str(run.id),
                        )

                await webhook_dispatch(run.bu_id, "assessment.completed", {
                    "run_id": str(run.id),
                    "assessment_id": str(run.assessment_id) if run.assessment_id else None,
                    "assessment_name": run.assessment_name,
                    "document_name": run.document_name,
                    "status": "success",
                    "latency_ms": run.latency_ms,
                })

        except Exception as exc:
            logger.exception("Assessment run fallido %s", run_id)
            run = await db.get(AssessmentRun, run_id)
            if run:
                run.status = "failed"
                run.error_message = str(exc)[:500]
                run.latency_ms = int((time.perf_counter() - start) * 1000)
                db.add(run)
                await db.commit()

                await webhook_dispatch(run.bu_id, "assessment.failed", {
                    "run_id": str(run.id),
                    "assessment_name": run.assessment_name,
                    "document_name": run.document_name,
                    "error": str(exc)[:200],
                })


@router.get("/", response_model=list[AssessmentRead])
async def list_assessments(
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_bu_auth_context),
):
    # 1ª query: todos los assessments de la BU
    result = await db.execute(
        select(Assessment)
        .where(Assessment.bu_id == auth.bu_id, Assessment.is_active.is_(True))
        .order_by(Assessment.created_at.desc())
    )
    assessments = result.scalars().all()
    if not assessments:
        return []

    # 2ª query: todas las configs de todos los assessments a la vez (sin N+1)
    assessment_ids = [a.id for a in assessments]
    cfg_result = await db.execute(
        select(AssessmentConfig, PromptConfig)
        .join(PromptConfig, PromptConfig.id == AssessmentConfig.config_id)
        .where(AssessmentConfig.assessment_id.in_(assessment_ids))
        .order_by(AssessmentConfig.assessment_id, AssessmentConfig.position)
    )
    configs_by_assessment: dict[UUID, list[ConfigBrief]] = {}
    for ac, pc in cfg_result.all():
        configs_by_assessment.setdefault(ac.assessment_id, []).append(
            ConfigBrief(config_id=ac.config_id, config_name=pc.name, position=ac.position)
        )

    return [
        AssessmentRead(
            id=a.id,
            bu_id=a.bu_id,
            name=a.name,
            description=a.description,
            is_active=a.is_active,
            created_at=a.created_at,
            configs=configs_by_assessment.get(a.id, []),
        )
        for a in assessments
    ]


@router.post("/", response_model=AssessmentRead, status_code=201)
async def create_assessment(
    payload: AssessmentCreate,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_bu_auth_context),
):
    await require_bu_roles_with_audit(
        auth, {"admin_global", "bu_admin"},
        "Solo bu_admin o admin_global pueden crear evaluaciones", db,
        action="assessment.create", resource_type="assessment",
    )

    # Validate all config_ids belong to this BU
    for cid in payload.config_ids:
        r = await db.execute(
            select(PromptConfig).where(PromptConfig.id == cid, PromptConfig.bu_id == auth.bu_id, PromptConfig.is_active.is_(True))
        )
        if not r.scalars().first():
            raise HTTPException(status_code=404, detail=f"Configuracion {cid} no encontrada en esta BU")

    assessment = Assessment(bu_id=auth.bu_id, name=payload.name, description=payload.description)
    db.add(assessment)
    await db.flush()

    for pos, cid in enumerate(payload.config_ids):
        db.add(AssessmentConfig(assessment_id=assessment.id, config_id=cid, position=pos))

    await db.commit()
    await db.refresh(assessment)
    return await _load_assessment_with_configs(db, assessment.id, auth.bu_id)


@router.get("/runs", response_model=list[AssessmentRunRead])
async def list_all_assessment_runs(
    limit: int = Query(20, ge=1, le=200),
    status: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_bu_auth_context),
):
    q = select(AssessmentRun).where(AssessmentRun.bu_id == auth.bu_id)
    if status:
        q = q.where(AssessmentRun.status == status)
    q = q.order_by(AssessmentRun.created_at.desc()).limit(limit)
    result = await db.execute(q)
    runs = list(result.scalars().all())
    return await enrich_assessment_runs(runs, db)


@router.get("/runs/{run_id}", response_model=AssessmentRunRead)
async def get_assessment_run(
    run_id: UUID,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_bu_auth_context),
):
    run = await db.get(AssessmentRun, run_id)
    if not run or run.bu_id != auth.bu_id:
        raise HTTPException(status_code=404, detail="Ejecucion no encontrada")
    enriched = await enrich_assessment_runs([run], db)
    return enriched[0]


@router.get("/runs/{run_id}/export", summary="Exportar resultado de ejecucion (JSON o CSV)")
async def export_assessment_run(
    run_id: UUID,
    format: str = Query("json", pattern="^(json|csv)$", description="json o csv"),
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_bu_auth_context),
):
    """
    Devuelve el resultado de una ejecución en formato plano, ideal para
    integraciones (Power Automate, Zapier, sistemas externos).

    - **json** (defecto): objeto con `fields` key-value + metadatos.
    - **csv**: dos columnas campo/valor, descargable directamente.

    Si la evaluación tiene varias configuraciones y hay campos con el mismo
    nombre en distintas configs, se prefixa con `NombreConfig.Campo`.
    """
    run = await db.get(AssessmentRun, run_id)
    if not run or run.bu_id != auth.bu_id:
        raise HTTPException(status_code=404, detail="Ejecucion no encontrada")
    if run.status != "success":
        raise HTTPException(
            status_code=409,
            detail=f"La ejecucion no esta completada (status: {run.status})",
        )

    combined = sorted(run.combined_result or [], key=lambda x: x.get("position", 0))

    # Build per-section field maps
    sections_out = []
    for section in combined:
        sec_fields = {
            item.get("title", ""): item.get("answer")
            for item in (section.get("result") or [])
            if item.get("title")
        }
        sections_out.append({"config_name": section.get("config_name"), "fields": sec_fields})

    # Flat merge — prefix with config name if duplicate keys across sections
    all_keys = [k for s in sections_out for k in s["fields"]]
    has_conflicts = len(combined) > 1 and len(all_keys) != len(set(all_keys))

    flat_fields: dict = {}
    for s in sections_out:
        for k, v in s["fields"].items():
            key = f"{s['config_name']}.{k}" if has_conflicts else k
            flat_fields[key] = v

    payload = {
        "run_id": str(run.id),
        "assessment_id": str(run.assessment_id) if run.assessment_id else None,
        "assessment_name": run.assessment_name,
        "document_id": str(run.document_id) if run.document_id else None,
        "document_name": run.document_name,
        "status": run.status,
        "executed_at": run.created_at.isoformat(),
        "latency_ms": run.latency_ms,
        "fields": flat_fields,
        "sections": sections_out,
    }

    if format == "csv":
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["campo", "valor"])
        for k, v in flat_fields.items():
            writer.writerow([k, "" if v is None else v])
        return Response(
            content=buf.getvalue(),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="run_{run_id}.csv"'},
        )

    return payload


@router.get("/{assessment_id}", response_model=AssessmentRead)
async def get_assessment(
    assessment_id: UUID,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_bu_auth_context),
):
    obj = await _load_assessment_with_configs(db, assessment_id, auth.bu_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Evaluacion no encontrada")
    return obj


@router.put("/{assessment_id}", response_model=AssessmentRead)
async def update_assessment(
    assessment_id: UUID,
    payload: AssessmentUpdate,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_bu_auth_context),
):
    await require_bu_roles_with_audit(
        auth, {"admin_global", "bu_admin"},
        "Solo bu_admin o admin_global pueden editar evaluaciones", db,
        action="assessment.update", resource_type="assessment", resource_id=str(assessment_id),
    )

    result = await db.execute(
        select(Assessment).where(Assessment.id == assessment_id, Assessment.bu_id == auth.bu_id)
    )
    assessment = result.scalars().first()
    if not assessment:
        raise HTTPException(status_code=404, detail="Evaluacion no encontrada")

    if payload.name is not None:
        assessment.name = payload.name
    if payload.description is not None:
        assessment.description = payload.description
    if payload.is_active is not None:
        assessment.is_active = payload.is_active

    if payload.config_ids is not None:
        for cid in payload.config_ids:
            r = await db.execute(
                select(PromptConfig).where(PromptConfig.id == cid, PromptConfig.bu_id == auth.bu_id, PromptConfig.is_active.is_(True))
            )
            if not r.scalars().first():
                raise HTTPException(status_code=404, detail=f"Configuracion {cid} no encontrada en esta BU")

        await db.execute(delete(AssessmentConfig).where(AssessmentConfig.assessment_id == assessment_id))
        for pos, cid in enumerate(payload.config_ids):
            db.add(AssessmentConfig(assessment_id=assessment_id, config_id=cid, position=pos))

    db.add(assessment)
    await db.commit()
    return await _load_assessment_with_configs(db, assessment_id, auth.bu_id)


@router.delete("/{assessment_id}", status_code=204)
async def delete_assessment(
    assessment_id: UUID,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_bu_auth_context),
):
    await require_bu_roles_with_audit(
        auth, {"admin_global", "bu_admin"},
        "Solo bu_admin o admin_global pueden eliminar evaluaciones", db,
        action="assessment.delete", resource_type="assessment", resource_id=str(assessment_id),
    )

    result = await db.execute(
        select(Assessment).where(Assessment.id == assessment_id, Assessment.bu_id == auth.bu_id)
    )
    assessment = result.scalars().first()
    if not assessment:
        raise HTTPException(status_code=404, detail="Evaluacion no encontrada")

    assessment.is_active = False
    db.add(assessment)
    await db.commit()


@router.post("/{assessment_id}/run", response_model=AssessmentRunRead, status_code=202)
async def run_assessment(
    assessment_id: UUID,
    payload: AssessmentRunRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_bu_auth_context),
):
    await require_bu_roles_with_audit(
        auth, {"admin_global", "bu_admin", "bu_user"},
        "No tienes permisos para ejecutar evaluaciones", db,
        action="assessment.run", resource_type="assessment", resource_id=str(assessment_id),
    )

    obj = await _load_assessment_with_configs(db, assessment_id, auth.bu_id)
    if not obj or not obj.is_active:
        raise HTTPException(status_code=404, detail="Evaluacion no encontrada o inactiva")
    if not obj.configs:
        raise HTTPException(status_code=400, detail="La evaluacion no tiene configuraciones asignadas")
    if not payload.document_text.strip():
        raise HTTPException(status_code=400, detail="El texto del documento esta vacio")

    # Load full config data for background task
    config_entries = []
    for brief in obj.configs:
        cfg_result = await db.execute(
            select(PromptConfig).where(PromptConfig.id == brief.config_id)
        )
        cfg = cfg_result.scalars().first()
        if cfg:
            config_entries.append({
                "config_id": str(cfg.id),
                "config_name": cfg.name,
                "position": brief.position,
                "variables": cfg.variables,
                "model": cfg.model,
                "base_prompt": cfg.base_prompt,
            })

    run = AssessmentRun(
        assessment_id=assessment_id,
        assessment_name=obj.name,
        bu_id=auth.bu_id,
        document_id=payload.document_id,
        document_name=payload.document_name,
        created_by=auth.actor_user_id,
        status="pending",
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)

    background_tasks.add_task(
        _run_assessment_background, run.id, payload.document_text, config_entries
    )
    enriched = await enrich_assessment_runs([run], db)
    return enriched[0]


@router.get("/{assessment_id}/runs", response_model=list[AssessmentRunRead])
async def list_assessment_runs(
    assessment_id: UUID,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_bu_auth_context),
):
    result = await db.execute(
        select(AssessmentRun)
        .where(AssessmentRun.assessment_id == assessment_id, AssessmentRun.bu_id == auth.bu_id)
        .order_by(AssessmentRun.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    runs = list(result.scalars().all())
    return await enrich_assessment_runs(runs, db)
