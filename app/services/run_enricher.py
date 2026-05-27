# app/services/run_enricher.py
"""
Utilidad compartida para enriquecer AssessmentRun con datos del usuario creador.
Centraliza la lógica duplicada que existía en documents.py y assessments.py.
"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AssessmentRun, User
from app.schemas.assessment import AssessmentRunRead


async def enrich_assessment_runs(
    runs: list[AssessmentRun], db: AsyncSession
) -> list[AssessmentRunRead]:
    """
    Dado una lista de AssessmentRun, carga los usuarios creadores en una sola
    query y devuelve la lista de AssessmentRunRead enriquecida.
    """
    user_ids = {r.created_by for r in runs if r.created_by}
    users: dict = {}
    if user_ids:
        result = await db.execute(select(User).where(User.id.in_(user_ids)))
        for u in result.scalars().all():
            users[u.id] = u

    out = []
    for run in runs:
        u = users.get(run.created_by) if run.created_by else None
        out.append(
            AssessmentRunRead(
                id=run.id,
                assessment_id=run.assessment_id,
                assessment_name=run.assessment_name,
                bu_id=run.bu_id,
                document_id=run.document_id,
                document_name=run.document_name,
                created_by_id=u.id if u else None,
                created_by_name=(u.full_name or u.email) if u else None,
                status=run.status,
                combined_result=run.combined_result,
                error_message=run.error_message,
                latency_ms=run.latency_ms,
                created_at=run.created_at,
                updated_at=run.updated_at,
            )
        )
    return out
