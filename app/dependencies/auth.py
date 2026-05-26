from typing import Optional
from uuid import UUID
import hashlib
import logging

from fastapi import Depends, Header, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.connection import get_db
from app.db.models import ApiKey, User, UserBUAccess
from app.services.security import decode_and_verify_token
from app.services.audit import log_audit_event


security_scheme = HTTPBearer(auto_error=False)
logger = logging.getLogger(__name__)


class AuthContext:
    def __init__(self, user: Optional[User], role: str, bu_id: UUID, api_key_id: Optional[UUID] = None):
        self.user = user
        self.role = role
        self.bu_id = bu_id
        self.api_key_id = api_key_id

    @property
    def actor_user_id(self) -> Optional[UUID]:
        return self.user.id if self.user else None


def require_bu_roles(auth: AuthContext, allowed_roles: set[str], detail: str) -> None:
    if auth.role not in allowed_roles:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


async def require_bu_roles_with_audit(
    auth: AuthContext,
    allowed_roles: set[str],
    detail: str,
    db: AsyncSession,
    *,
    action: str,
    resource_type: str = "authorization",
    resource_id: str | None = None,
) -> None:
    if auth.role in allowed_roles:
        return

    try:
        await log_audit_event(
            db,
            event_type="authz.denied",
            actor_user_id=auth.actor_user_id,
            bu_id=auth.bu_id,
            resource_type=resource_type,
            resource_id=resource_id,
            message=detail,
            metadata={
                "action": action,
                "role": auth.role,
                "allowed_roles": sorted(allowed_roles),
            },
        )
        await db.commit()
    except Exception:
        await db.rollback()
        logger.exception("No se pudo registrar auditoria de denegacion")

    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    token = request.cookies.get("centinell_access")
    if not token and credentials:
        token = credentials.credentials
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Falta token de acceso")

    try:
        payload = decode_and_verify_token(token)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token invalido")

    user = await db.get(User, UUID(user_id))
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuario inactivo o inexistente")

    return user


async def require_global_admin(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> User:
    if not current_user.is_global_admin:
        try:
            await log_audit_event(
                db,
                event_type="authz.denied",
                actor_user_id=current_user.id,
                resource_type="authorization",
                message="Requiere rol admin_global",
                metadata={
                    "action": "admin_global.required",
                    "role": "non_admin_global",
                    "allowed_roles": ["admin_global"],
                },
            )
            await db.commit()
        except Exception:
            await db.rollback()
            logger.exception("No se pudo registrar auditoria de denegacion admin_global")

        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Requiere rol admin_global")
    return current_user


async def _resolve_api_key(raw_key: str, db: AsyncSession) -> AuthContext:
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    result = await db.execute(
        select(ApiKey).where(ApiKey.key_hash == key_hash, ApiKey.is_active.is_(True))
    )
    api_key = result.scalars().first()
    if not api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="API Key invalida o revocada")

    # Update last_used_at without waiting for commit — best effort
    from app.services.security import utcnow
    api_key.last_used_at = utcnow()
    try:
        await db.flush()
    except Exception:
        logger.warning("No se pudo actualizar last_used_at para API key")

    # Optionally load the creating user for audit context
    creator: Optional[User] = None
    if api_key.created_by:
        creator = await db.get(User, api_key.created_by)
        if creator and not creator.is_active:
            creator = None

    return AuthContext(creator, api_key.role, api_key.bu_id, api_key_id=api_key.id)


async def get_bu_auth_context(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
    x_bu_id: Optional[str] = Header(None, alias="X-BU-ID"),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    db: AsyncSession = Depends(get_db),
) -> AuthContext:
    # API key path — no JWT or X-BU-ID needed
    if x_api_key:
        return await _resolve_api_key(x_api_key, db)

    # JWT + X-BU-ID path
    token = request.cookies.get("centinell_access")
    if not token and credentials:
        token = credentials.credentials
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Falta token de acceso")

    try:
        payload = decode_and_verify_token(token)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token invalido")

    user = await db.get(User, UUID(user_id))
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuario inactivo o inexistente")

    if not x_bu_id:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Falta cabecera X-BU-ID")

    try:
        bu_id = UUID(x_bu_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="X-BU-ID no es UUID valido") from exc

    if user.is_global_admin:
        return AuthContext(user, "admin_global", bu_id)

    access_result = await db.execute(
        select(UserBUAccess).where(
            UserBUAccess.user_id == user.id,
            UserBUAccess.bu_id == bu_id,
            UserBUAccess.is_active.is_(True),
        )
    )
    access = access_result.scalars().first()
    if not access:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sin acceso a esta BU")

    return AuthContext(user, access.role, bu_id)
