from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.db.connection import get_db
from app.db.models import BusinessUnit, User, UserBUAccess
from app.dependencies.auth import (
    AuthContext,
    get_current_user,
    get_bu_auth_context,
    require_bu_roles_with_audit,
    require_global_admin,
)
from datetime import datetime

from app.schemas.auth import AssignUserBURequest, BUCreateRequest, BURead, BUUserAccessRead
from pydantic import BaseModel


class BUAccessWithRole(BaseModel):
    id: UUID
    name: str
    code: str
    is_active: bool
    created_at: datetime
    role: str
from app.services.audit import log_audit_event

router = APIRouter(prefix="/bus", tags=["business-units"])


@router.get("/my-access", response_model=list[BURead])
async def list_my_business_units(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.is_global_admin:
        result = await db.execute(select(BusinessUnit).order_by(BusinessUnit.created_at.desc()))
        return list(result.scalars().all())

    stmt = (
        select(BusinessUnit)
        .join(UserBUAccess, UserBUAccess.bu_id == BusinessUnit.id)
        .where(
            UserBUAccess.user_id == current_user.id,
            UserBUAccess.is_active.is_(True),
            BusinessUnit.is_active.is_(True),
        )
        .order_by(BusinessUnit.created_at.desc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.get("/my-access-with-roles", response_model=list[BUAccessWithRole])
async def list_my_bus_with_roles(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.is_global_admin:
        result = await db.execute(select(BusinessUnit).order_by(BusinessUnit.created_at.desc()))
        return [
            BUAccessWithRole(
                id=bu.id, name=bu.name, code=bu.code,
                is_active=bu.is_active, created_at=bu.created_at,
                role="admin_global",
            )
            for bu in result.scalars().all()
        ]

    stmt = (
        select(BusinessUnit, UserBUAccess.role)
        .join(UserBUAccess, UserBUAccess.bu_id == BusinessUnit.id)
        .where(
            UserBUAccess.user_id == current_user.id,
            UserBUAccess.is_active.is_(True),
            BusinessUnit.is_active.is_(True),
        )
        .order_by(BusinessUnit.created_at.desc())
    )
    result = await db.execute(stmt)
    return [
        BUAccessWithRole(
            id=bu.id, name=bu.name, code=bu.code,
            is_active=bu.is_active, created_at=bu.created_at,
            role=role,
        )
        for bu, role in result.all()
    ]


@router.post("/", response_model=BURead, status_code=201)
async def create_business_unit(
    payload: BUCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_global_admin),
):
    existing = await db.execute(select(BusinessUnit).where(BusinessUnit.code == payload.code.upper()))
    if existing.scalars().first():
        raise HTTPException(status_code=409, detail="Ya existe una BU con ese código")

    bu = BusinessUnit(name=payload.name.strip(), code=payload.code.upper())
    db.add(bu)
    await db.flush()

    await log_audit_event(
        db,
        event_type="bu.created",
        actor_user_id=current_user.id,
        bu_id=bu.id,
        resource_type="business_unit",
        resource_id=str(bu.id),
        message="Creación de BU",
    )

    return bu


@router.get("/", response_model=list[BURead])
async def list_business_units(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_global_admin),
):
    _ = current_user
    result = await db.execute(select(BusinessUnit).order_by(BusinessUnit.created_at.desc()))
    return list(result.scalars().all())


@router.post("/{bu_id}/users", status_code=201)
async def assign_user_to_bu(
    bu_id: UUID,
    payload: AssignUserBURequest,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_bu_auth_context),
):
    await require_bu_roles_with_audit(
        auth,
        {"admin_global", "bu_admin"},
        "No tienes permisos para administrar usuarios de esta BU",
        db,
        action="bu.user.assign",
        resource_type="business_unit",
        resource_id=str(bu_id),
    )

    if auth.role != "admin_global" and auth.bu_id != bu_id:
        await require_bu_roles_with_audit(
            auth,
            {"admin_global"},
            "No puedes administrar usuarios de otra BU",
            db,
            action="bu.user.assign.cross_bu",
            resource_type="business_unit",
            resource_id=str(bu_id),
        )

    bu = await db.get(BusinessUnit, bu_id)
    if not bu:
        raise HTTPException(status_code=404, detail="BU no encontrada")

    user = await db.get(User, payload.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    if user.is_global_admin:
        raise HTTPException(status_code=400, detail="No se puede modificar acceso o rol de un admin_global")

    result = await db.execute(
        select(UserBUAccess).where(UserBUAccess.user_id == user.id, UserBUAccess.bu_id == bu.id)
    )
    access = result.scalars().first()

    if access:
        access.role = payload.role
        access.is_active = True
        db.add(access)
    else:
        db.add(UserBUAccess(user_id=user.id, bu_id=bu.id, role=payload.role, is_active=True))

    await log_audit_event(
        db,
        event_type="bu.user_assigned",
        actor_user_id=auth.actor_user_id,
        bu_id=bu.id,
        resource_type="user",
        resource_id=str(user.id),
        message="Asignación de usuario a BU",
        metadata={"role": payload.role},
    )

    return {"status": "ok", "bu_id": str(bu.id), "user_id": str(user.id), "role": payload.role}


@router.get("/{bu_id}/users", response_model=list[BUUserAccessRead])
async def list_users_in_bu(
    bu_id: UUID,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_bu_auth_context),
):
    await require_bu_roles_with_audit(
        auth,
        {"admin_global", "bu_admin"},
        "No tienes permisos para administrar usuarios de esta BU",
        db,
        action="bu.user.list",
        resource_type="business_unit",
        resource_id=str(bu_id),
    )

    if auth.role != "admin_global" and auth.bu_id != bu_id:
        await require_bu_roles_with_audit(
            auth,
            {"admin_global"},
            "No puedes administrar usuarios de otra BU",
            db,
            action="bu.user.list.cross_bu",
            resource_type="business_unit",
            resource_id=str(bu_id),
        )

    bu = await db.get(BusinessUnit, bu_id)
    if not bu:
        raise HTTPException(status_code=404, detail="BU no encontrada")

    stmt = (
        select(UserBUAccess, User)
        .join(User, User.id == UserBUAccess.user_id)
        .where(UserBUAccess.bu_id == bu_id, UserBUAccess.is_active.is_(True))
        .order_by(User.email.asc())
    )
    rows = (await db.execute(stmt)).all()

    return [
        {
            "user_id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "is_global_admin": user.is_global_admin,
            "is_active": user.is_active,
            "role": access.role,
            "bu_id": access.bu_id,
        }
        for access, user in rows
    ]


@router.delete("/{bu_id}/users/{user_id}", status_code=204)
async def remove_user_from_bu(
    bu_id: UUID,
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_bu_auth_context),
):
    await require_bu_roles_with_audit(
        auth,
        {"admin_global", "bu_admin"},
        "No tienes permisos para administrar usuarios de esta BU",
        db,
        action="bu.user.remove",
        resource_type="business_unit",
        resource_id=str(bu_id),
    )

    if auth.role != "admin_global" and auth.bu_id != bu_id:
        await require_bu_roles_with_audit(
            auth,
            {"admin_global"},
            "No puedes administrar usuarios de otra BU",
            db,
            action="bu.user.remove.cross_bu",
            resource_type="business_unit",
            resource_id=str(bu_id),
        )

    bu = await db.get(BusinessUnit, bu_id)
    if not bu:
        raise HTTPException(status_code=404, detail="BU no encontrada")

    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    if user.is_global_admin:
        raise HTTPException(status_code=400, detail="No se puede modificar acceso o rol de un admin_global")

    result = await db.execute(
        select(UserBUAccess).where(
            UserBUAccess.user_id == user_id,
            UserBUAccess.bu_id == bu_id,
            UserBUAccess.is_active.is_(True),
        )
    )
    access = result.scalars().first()
    if not access:
        raise HTTPException(status_code=404, detail="Acceso BU no encontrado")

    access.is_active = False
    db.add(access)

    await log_audit_event(
        db,
        event_type="bu.user_removed",
        actor_user_id=auth.actor_user_id,
        bu_id=bu.id,
        resource_type="user",
        resource_id=str(user.id),
        message="Remocion de acceso de usuario en BU",
    )
