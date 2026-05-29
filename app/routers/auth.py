import secrets
from datetime import timezone

from fastapi import APIRouter, BackgroundTasks, Cookie, Depends, HTTPException, Request, Response
from pydantic import BaseModel, EmailStr
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    PASSWORD_RESET_EXPIRE_MINUTES,
    REFRESH_TOKEN_EXPIRE_MINUTES,
)
from app.db.connection import get_db
from app.db.models import BusinessUnit, PasswordResetToken, RefreshToken, User, UserBUAccess
from app.rate_limit import limiter
from app.schemas.auth import LoginRequest, LoginResponse, RefreshRequest, UserPublic
from app.services.audit import log_audit_event
from app.services.email import send_password_reset_email
from app.services.security import (
    create_access_token,
    expires_at,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    utcnow,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def _set_auth_cookies(response: Response, request: Request, access_token: str, refresh_token: str) -> None:
    secure = request.url.scheme == "https"
    response.set_cookie(
        key="centinell_access",
        value=access_token,
        httponly=True,
        secure=secure,
        samesite="lax",
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
    )
    response.set_cookie(
        key="centinell_refresh",
        value=refresh_token,
        httponly=True,
        secure=secure,
        samesite="lax",
        max_age=REFRESH_TOKEN_EXPIRE_MINUTES * 60,
        path="/auth/refresh",
    )


def _clear_auth_cookies(response: Response, secure: bool) -> None:
    response.delete_cookie("centinell_access", path="/", secure=secure, httponly=True, samesite="lax")
    response.delete_cookie("centinell_refresh", path="/auth/refresh", secure=secure, httponly=True, samesite="lax")


async def _has_active_bu_access(db: AsyncSession, user_id) -> bool:
    stmt = (
        select(UserBUAccess.id)
        .join(BusinessUnit, BusinessUnit.id == UserBUAccess.bu_id)
        .where(
            UserBUAccess.user_id == user_id,
            UserBUAccess.is_active.is_(True),
            BusinessUnit.is_active.is_(True),
        )
        .limit(1)
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none() is not None


@router.post("/login", response_model=LoginResponse)
@limiter.limit("5/minute")
async def login(request: Request, payload: LoginRequest, response: Response, db: AsyncSession = Depends(get_db)):
    email = payload.email.lower().strip()
    if "@" not in email:
        raise HTTPException(status_code=422, detail="Email inválido")

    result = await db.execute(select(User).where(User.email == email))
    user = result.scalars().first()

    if not user or not user.is_active or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Credenciales inválidas")

    if not user.is_global_admin:
        has_access = await _has_active_bu_access(db, user.id)
        if not has_access:
            raise HTTPException(status_code=403, detail="Sin unidad de negocio asignada. Contacta con un administrador.")

    role = "admin_global" if user.is_global_admin else "bu_user"
    access_token = create_access_token(
        subject=str(user.id),
        role=role,
        expires_minutes=ACCESS_TOKEN_EXPIRE_MINUTES,
    )

    await db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=utcnow())
    )

    refresh_token = generate_refresh_token()
    db.add(RefreshToken(
        user_id=user.id,
        token_hash=hash_refresh_token(refresh_token),
        expires_at=expires_at(REFRESH_TOKEN_EXPIRE_MINUTES),
    ))

    user.last_login_at = utcnow()
    db.add(user)

    await log_audit_event(
        db,
        event_type="auth.login",
        actor_user_id=user.id,
        resource_type="user",
        resource_id=str(user.id),
        message="Inicio de sesión",
    )

    _set_auth_cookies(response, request, access_token, refresh_token)

    return LoginResponse(
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=UserPublic(id=user.id, email=user.email, full_name=user.full_name, role=role),
    )


@router.post("/refresh", response_model=LoginResponse)
@limiter.limit("10/minute")
async def refresh(
    request: Request,
    response: Response,
    payload: RefreshRequest = RefreshRequest(),
    centinell_refresh: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    # Cookie tiene prioridad; fallback al body (clientes API)
    raw_token = centinell_refresh or (payload.refresh_token if payload else None)
    if not raw_token:
        raise HTTPException(status_code=401, detail="Refresh token no encontrado")

    token_hash = hash_refresh_token(raw_token)
    result = await db.execute(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
    token_row = result.scalars().first()

    if not token_row:
        raise HTTPException(status_code=401, detail="Refresh token inválido")

    now = expires_at(0)
    token_expires = token_row.expires_at
    if token_expires.tzinfo is None:
        token_expires = token_expires.replace(tzinfo=timezone.utc)

    if token_row.revoked_at is not None or token_expires < now:
        raise HTTPException(status_code=401, detail="Refresh token expirado o revocado")

    user = await db.get(User, token_row.user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Usuario inactivo o inexistente")

    if not user.is_global_admin:
        has_access = await _has_active_bu_access(db, user.id)
        if not has_access:
            raise HTTPException(status_code=403, detail="Sin unidad de negocio asignada. Contacta con un administrador.")

    token_row.revoked_at = now
    db.add(token_row)

    role = "admin_global" if user.is_global_admin else "bu_user"
    new_access_token = create_access_token(
        subject=str(user.id),
        role=role,
        expires_minutes=ACCESS_TOKEN_EXPIRE_MINUTES,
    )
    new_refresh_token = generate_refresh_token()
    db.add(RefreshToken(
        user_id=user.id,
        token_hash=hash_refresh_token(new_refresh_token),
        expires_at=expires_at(REFRESH_TOKEN_EXPIRE_MINUTES),
    ))

    await log_audit_event(
        db,
        event_type="auth.refresh",
        actor_user_id=user.id,
        resource_type="user",
        resource_id=str(user.id),
        message="Renovación de token",
    )

    _set_auth_cookies(response, request, new_access_token, new_refresh_token)

    return LoginResponse(
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=UserPublic(id=user.id, email=user.email, full_name=user.full_name, role=role),
    )


@router.post("/logout", status_code=204)
async def logout(request: Request, response: Response):
    _clear_auth_cookies(response, secure=request.url.scheme == "https")


# ── Password reset ────────────────────────────────────────────────────────────

class ForgotPasswordRequest(BaseModel):
    email: str


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


@router.post("/forgot-password", status_code=204)
@limiter.limit("3/minute")
async def forgot_password(
    request: Request,
    payload: ForgotPasswordRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Genera un token de reset y lo envía por email.

    Devuelve siempre 204 para no revelar si el email existe en el sistema.
    """
    email = payload.email.lower().strip()
    result = await db.execute(select(User).where(User.email == email, User.is_active.is_(True)))
    user = result.scalars().first()

    if user:
        # Invalida tokens anteriores del usuario
        await db.execute(
            update(PasswordResetToken)
            .where(PasswordResetToken.user_id == user.id, PasswordResetToken.used_at.is_(None))
            .values(used_at=utcnow())
        )

        raw_token = secrets.token_urlsafe(32)
        token_hash = hash_refresh_token(raw_token)  # reutiliza HMAC-SHA256
        db.add(PasswordResetToken(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=expires_at(PASSWORD_RESET_EXPIRE_MINUTES),
        ))
        await db.commit()

        background_tasks.add_task(send_password_reset_email, user.email, raw_token)

    # 204 incluso si el email no existe (evita user enumeration)


@router.post("/reset-password", status_code=204)
@limiter.limit("5/minute")
async def reset_password(
    request: Request,
    payload: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    if len(payload.new_password) < 8:
        raise HTTPException(status_code=422, detail="La contraseña debe tener al menos 8 caracteres")

    token_hash = hash_refresh_token(payload.token)
    result = await db.execute(
        select(PasswordResetToken).where(PasswordResetToken.token_hash == token_hash)
    )
    token_row = result.scalars().first()

    now = utcnow()
    token_expires = token_row.expires_at if token_row else None
    if token_expires and token_expires.tzinfo is None:
        token_expires = token_expires.replace(tzinfo=timezone.utc)

    if (
        not token_row
        or token_row.used_at is not None
        or token_expires < now
    ):
        raise HTTPException(status_code=400, detail="Token inválido o expirado")

    user = await db.get(User, token_row.user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=400, detail="Token inválido o expirado")

    user.password_hash = hash_password(payload.new_password)
    token_row.used_at = now
    db.add(user)
    db.add(token_row)

    # Revoca todas las sesiones activas del usuario
    await db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=now)
    )

    await log_audit_event(
        db,
        event_type="auth.password_reset",
        actor_user_id=user.id,
        resource_type="user",
        resource_id=str(user.id),
        message="Contraseña restablecida mediante token de recuperación",
    )
    await db.commit()
