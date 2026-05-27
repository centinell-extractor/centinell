from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from uuid import uuid4

from app.db.models import BusinessUnit, RefreshToken, User, UserBUAccess
from app.services.security import hash_password


async def _create_user(
    session_maker: async_sessionmaker[AsyncSession],
    *,
    email: str,
    password: str,
    is_global_admin: bool = False,
) -> User:
    async with session_maker() as session:
        user = User(
            email=email,
            full_name=email.split("@")[0],
            password_hash=hash_password(password),
            is_global_admin=is_global_admin,
            is_active=True,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user


async def _grant_default_bu_access(
    session_maker: async_sessionmaker[AsyncSession],
    *,
    user_id,
    bu_active: bool = True,
) -> None:
    async with session_maker() as session:
        bu = BusinessUnit(name="Auth Flow BU", code=f"AF_{uuid4().hex[:6]}", is_active=bu_active)
        session.add(bu)
        await session.flush()
        session.add(UserBUAccess(user_id=user_id, bu_id=bu.id, role="bu_user", is_active=True))
        await session.commit()


@pytest.mark.asyncio
async def test_login_success_returns_user_and_sets_cookies(client, session_maker):
    """Login exitoso: respuesta con user + cookies httpOnly con tokens."""
    user = await _create_user(
        session_maker,
        email="auth-ok@test.local",
        password="StrongPass123!",
    )
    await _grant_default_bu_access(session_maker, user_id=user.id)

    response = await client.post(
        "/auth/login",
        json={"email": "auth-ok@test.local", "password": "StrongPass123!"},
    )

    assert response.status_code == 200
    body = response.json()
    # Tokens van en cookies httpOnly, no en el body
    assert body["user"]["email"] == "auth-ok@test.local"
    assert body["user"]["role"] == "bu_user"
    assert "expires_in" in body
    # Las cookies de sesión están presentes
    assert "centinell_access" in response.cookies
    assert "centinell_refresh" in response.cookies


@pytest.mark.asyncio
async def test_login_invalid_credentials_returns_401(client, session_maker):
    await _create_user(
        session_maker,
        email="auth-bad@test.local",
        password="StrongPass123!",
    )

    response = await client.post(
        "/auth/login",
        json={"email": "auth-bad@test.local", "password": "WrongPassword123!"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Credenciales inválidas"


@pytest.mark.asyncio
async def test_login_user_without_bu_assignment_returns_403(client, session_maker):
    password = "StrongPass123!"
    await _create_user(session_maker, email="nobu-login@test.local", password=password)

    response = await client.post(
        "/auth/login",
        json={"email": "nobu-login@test.local", "password": password},
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_login_user_with_only_inactive_bu_assignment_returns_403(client, session_maker):
    password = "StrongPass123!"
    user = await _create_user(session_maker, email="inactive-bu-login@test.local", password=password)
    await _grant_default_bu_access(session_maker, user_id=user.id, bu_active=False)

    response = await client.post(
        "/auth/login",
        json={"email": "inactive-bu-login@test.local", "password": password},
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_refresh_rotation_revokes_previous_refresh_token(client, session_maker):
    """Refresh rotation: el token anterior queda revocado tras rotación."""
    user = await _create_user(
        session_maker,
        email="auth-refresh@test.local",
        password="StrongPass123!",
    )
    await _grant_default_bu_access(session_maker, user_id=user.id)

    login = await client.post(
        "/auth/login",
        json={"email": "auth-refresh@test.local", "password": "StrongPass123!"},
    )
    assert login.status_code == 200
    # El refresh token está en la cookie httpOnly
    first_refresh = login.cookies.get("centinell_refresh")
    assert first_refresh

    # Usar el refresh token como body (fallback para clientes API sin cookie)
    first_refresh_call = await client.post(
        "/auth/refresh",
        json={"refresh_token": first_refresh},
    )
    assert first_refresh_call.status_code == 200
    second_refresh = first_refresh_call.cookies.get("centinell_refresh")
    assert second_refresh and second_refresh != first_refresh

    # Reutilizar el primer token debe fallar (revocado).
    # Limpiamos las cookies del cliente para evitar que la nueva cookie de sesión
    # tome prioridad sobre el token revocado que enviamos en el body.
    client.cookies.clear()
    reuse_old = await client.post(
        "/auth/refresh",
        json={"refresh_token": first_refresh},
    )
    assert reuse_old.status_code == 401
    assert reuse_old.json()["detail"] == "Refresh token expirado o revocado"


@pytest.mark.asyncio
async def test_refresh_invalid_token_returns_401(client):
    response = await client.post(
        "/auth/refresh",
        json={"refresh_token": "invalid-token"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Refresh token inválido"


@pytest.mark.asyncio
async def test_login_creates_refresh_token_record(client, session_maker):
    user = await _create_user(
        session_maker,
        email="auth-db@test.local",
        password="StrongPass123!",
    )
    await _grant_default_bu_access(session_maker, user_id=user.id)

    response = await client.post(
        "/auth/login",
        json={"email": "auth-db@test.local", "password": "StrongPass123!"},
    )
    assert response.status_code == 200

    async with session_maker() as session:
        refresh_rows = (await session.execute(select(RefreshToken))).scalars().all()

    assert len(refresh_rows) == 1
    assert refresh_rows[0].revoked_at is None
