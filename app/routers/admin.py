import secrets
from datetime import timedelta
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.connection import get_db
from app.db.models import AuditEvent, BusinessUnit, Extraction, PromptConfig, User, UserBUAccess
from app.dependencies.auth import require_global_admin
from app.schemas.auth import (
    AdminDashboardResponse,
    AuditEventRead,
    BUProvisionRequest,
    BUProvisionResult,
    BURead,
    DashboardByBU,
    UserCreateRequest,
    UserRead,
)
from app.services.audit import log_audit_event
from app.services.email import send_welcome_email
from app.services.security import hash_password, utcnow

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/audit-events", response_model=list[AuditEventRead])
async def list_audit_events(
    event_type: str | None = None,
    actor_user_id: UUID | None = None,
    bu_id: UUID | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_global_admin),
):
    _ = current_user

    stmt = (
        select(AuditEvent)
        .order_by(AuditEvent.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    if event_type:
        stmt = stmt.where(AuditEvent.event_type == event_type)
    if actor_user_id:
        stmt = stmt.where(AuditEvent.actor_user_id == actor_user_id)
    if bu_id:
        stmt = stmt.where(AuditEvent.bu_id == bu_id)

    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.get("/dashboard", response_model=AdminDashboardResponse)
async def dashboard(
    bu_id: UUID | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_global_admin),
):
    _ = current_user

    users_total = (await db.execute(select(func.count(User.id)))).scalar_one()
    business_units_total = (await db.execute(select(func.count(BusinessUnit.id)))).scalar_one()
    extractions_total = (await db.execute(select(func.count(Extraction.id)))).scalar_one()

    since = utcnow() - timedelta(hours=24)
    failed_24h = (
        await db.execute(
            select(func.count(Extraction.id)).where(
                Extraction.status == "failed",
                Extraction.created_at >= since,
            )
        )
    ).scalar_one()

    active_prompt_configs = (
        await db.execute(select(func.count(PromptConfig.id)).where(PromptConfig.is_active.is_(True)))
    ).scalar_one()

    by_bu_stmt = (
        select(
            Extraction.bu_id,
            func.count(Extraction.id).label("total"),
            func.count(
                case(
                    (
                        (Extraction.status == "failed") & (Extraction.created_at >= since),
                        1,
                    )
                )
            ).label("failed_24h"),
        )
        .where(Extraction.bu_id.is_not(None))
        .group_by(Extraction.bu_id)
        .order_by(func.count(Extraction.id).desc())
    )

    if bu_id is not None:
        by_bu_stmt = by_bu_stmt.where(Extraction.bu_id == bu_id)

    by_bu_rows = (await db.execute(by_bu_stmt)).all()
    by_bu = [
        DashboardByBU(
            bu_id=row.bu_id,
            extractions_total=row.total,
            extractions_failed_24h=row.failed_24h,
        )
        for row in by_bu_rows
    ]

    return AdminDashboardResponse(
        users_total=users_total,
        business_units_total=business_units_total,
        extractions_total=extractions_total,
        extractions_failed_24h=failed_24h,
        active_prompt_configs=active_prompt_configs,
        by_bu=by_bu,
    )


@router.post("/users", response_model=UserRead, status_code=201)
async def create_user(
    payload: UserCreateRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_global_admin),
):
    email = payload.email.lower().strip()
    if "@" not in email:
        raise HTTPException(status_code=422, detail="Email inválido")

    existing = await db.execute(select(User).where(User.email == email))
    if existing.scalars().first():
        raise HTTPException(status_code=409, detail="Ya existe un usuario con ese email")

    # Auto-generate password if not provided
    if payload.password:
        raw_password = payload.password
        will_send_email = payload.send_welcome_email
    else:
        raw_password = secrets.token_urlsafe(12)
        will_send_email = True

    user = User(
        email=email,
        full_name=payload.full_name,
        password_hash=hash_password(raw_password),
        is_global_admin=payload.is_global_admin,
        is_active=True,
        must_change_password=will_send_email,
    )
    db.add(user)
    await db.flush()

    await log_audit_event(
        db,
        event_type="user.created",
        actor_user_id=current_user.id,
        resource_type="user",
        resource_id=str(user.id),
        message="Alta de usuario",
        metadata={"is_global_admin": payload.is_global_admin, "welcome_email": will_send_email},
    )

    if will_send_email:
        background_tasks.add_task(send_welcome_email, email, payload.full_name or email, raw_password)

    return user


@router.post("/business-units", response_model=BUProvisionResult, status_code=201)
async def provision_business_unit(
    payload: BUProvisionRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_global_admin),
):
    """Crea una BU y opcionalmente su primer usuario admin con email de bienvenida."""
    existing_bu = await db.execute(select(BusinessUnit).where(BusinessUnit.code == payload.bu_code.upper()))
    if existing_bu.scalars().first():
        raise HTTPException(status_code=409, detail="Ya existe una BU con ese código")

    bu = BusinessUnit(name=payload.bu_name.strip(), code=payload.bu_code.upper())
    db.add(bu)
    await db.flush()
    await db.refresh(bu)

    await log_audit_event(
        db,
        event_type="bu.created",
        actor_user_id=current_user.id,
        bu_id=bu.id,
        resource_type="business_unit",
        resource_id=str(bu.id),
        message="Creación de BU via panel admin",
    )

    user_created = False
    user_email = None

    if payload.admin_email:
        admin_email = payload.admin_email.lower().strip()
        existing_user = await db.execute(select(User).where(User.email == admin_email))
        existing = existing_user.scalars().first()

        if existing:
            # Assign existing user to the new BU
            result = await db.execute(
                select(UserBUAccess).where(UserBUAccess.user_id == existing.id, UserBUAccess.bu_id == bu.id)
            )
            access = result.scalars().first()
            if not access:
                db.add(UserBUAccess(user_id=existing.id, bu_id=bu.id, role=payload.admin_role, is_active=True))
        else:
            raw_password = secrets.token_urlsafe(12)
            new_user = User(
                email=admin_email,
                full_name=payload.admin_full_name,
                password_hash=hash_password(raw_password),
                is_global_admin=False,
                is_active=True,
                must_change_password=payload.send_welcome_email,
            )
            db.add(new_user)
            await db.flush()

            db.add(UserBUAccess(user_id=new_user.id, bu_id=bu.id, role=payload.admin_role, is_active=True))

            await log_audit_event(
                db,
                event_type="user.created",
                actor_user_id=current_user.id,
                bu_id=bu.id,
                resource_type="user",
                resource_id=str(new_user.id),
                message="Alta de usuario admin de BU via panel admin",
                metadata={"welcome_email": payload.send_welcome_email},
            )

            if payload.send_welcome_email:
                background_tasks.add_task(
                    send_welcome_email, admin_email, payload.admin_full_name or admin_email, raw_password
                )

        user_created = not bool(existing)
        user_email = admin_email

    return BUProvisionResult(
        bu=BURead(id=bu.id, name=bu.name, code=bu.code, is_active=bu.is_active, created_at=bu.created_at),
        user_created=user_created,
        user_email=user_email,
    )


@router.get("/users", response_model=list[UserRead])
async def list_users(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_global_admin),
):
    _ = current_user
    result = await db.execute(select(User).order_by(User.created_at.desc()))
    return list(result.scalars().all())
