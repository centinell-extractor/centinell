from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import User
from app.services.security import create_access_token, hash_password


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _create_user(
    session_maker: async_sessionmaker[AsyncSession],
    *,
    email: str,
    password: str = "StrongPass123!",
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


@pytest.mark.asyncio
async def test_non_admin_cannot_list_bus(client, session_maker):
    user = await _create_user(session_maker, email="user-bu@test.local", is_global_admin=False)
    token = create_access_token(subject=str(user.id), role="bu_user", expires_minutes=30)

    response = await client.get("/bus/", headers=_bearer(token))

    assert response.status_code == 403
    assert response.json()["detail"] == "Requiere rol admin_global"


@pytest.mark.asyncio
async def test_admin_can_create_and_list_bus(client, session_maker):
    admin = await _create_user(session_maker, email="admin-bu@test.local", is_global_admin=True)
    token = create_access_token(subject=str(admin.id), role="admin_global", expires_minutes=30)

    create_response = await client.post(
        "/bus/",
        headers={**_bearer(token), "Content-Type": "application/json"},
        json={"name": "Business Unit Test", "code": f"BU_{uuid4().hex[:6]}"},
    )
    assert create_response.status_code == 201

    list_response = await client.get("/bus/", headers=_bearer(token))
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1


@pytest.mark.asyncio
async def test_non_admin_cannot_access_admin_dashboard(client, session_maker):
    user = await _create_user(session_maker, email="user-dashboard@test.local", is_global_admin=False)
    token = create_access_token(subject=str(user.id), role="bu_user", expires_minutes=30)

    response = await client.get("/admin/dashboard", headers=_bearer(token))

    assert response.status_code == 403
    assert response.json()["detail"] == "Requiere rol admin_global"


@pytest.mark.asyncio
async def test_admin_can_create_user_and_duplicate_fails(client, session_maker):
    admin = await _create_user(session_maker, email="admin-users@test.local", is_global_admin=True)
    token = create_access_token(subject=str(admin.id), role="admin_global", expires_minutes=30)

    payload = {
        "email": "new-user@test.local",
        "password": "VeryStrongPass123!",
        "full_name": "New User",
        "is_global_admin": False,
    }

    first = await client.post(
        "/admin/users",
        headers={**_bearer(token), "Content-Type": "application/json"},
        json=payload,
    )
    assert first.status_code == 201
    assert first.json()["email"] == "new-user@test.local"

    second = await client.post(
        "/admin/users",
        headers={**_bearer(token), "Content-Type": "application/json"},
        json=payload,
    )
    assert second.status_code == 409
    assert second.json()["detail"] == "Ya existe un usuario con ese email"


@pytest.mark.asyncio
async def test_non_admin_cannot_list_admin_users(client, session_maker):
    user = await _create_user(session_maker, email="users-list-no-admin@test.local", is_global_admin=False)
    token = create_access_token(subject=str(user.id), role="bu_user", expires_minutes=30)

    response = await client.get("/admin/users", headers=_bearer(token))

    assert response.status_code == 403
    assert response.json()["detail"] == "Requiere rol admin_global"


@pytest.mark.asyncio
async def test_admin_can_list_users(client, session_maker):
    admin = await _create_user(session_maker, email="users-list-admin@test.local", is_global_admin=True)
    await _create_user(session_maker, email="users-list-target@test.local", is_global_admin=False)
    token = create_access_token(subject=str(admin.id), role="admin_global", expires_minutes=30)

    response = await client.get("/admin/users", headers=_bearer(token))

    assert response.status_code == 200
    emails = [row["email"] for row in response.json()]
    assert "users-list-admin@test.local" in emails
    assert "users-list-target@test.local" in emails
