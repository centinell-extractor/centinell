from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import AuditEvent, BusinessUnit, User, UserBUAccess
from app.services.security import create_access_token, hash_password


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _create_user(
    session_maker: async_sessionmaker[AsyncSession],
    *,
    email: str,
    password: str = "TestPassword123!",
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


async def _create_bu(
    session_maker: async_sessionmaker[AsyncSession],
    *,
    name: str,
    code: str,
) -> BusinessUnit:
    async with session_maker() as session:
        bu = BusinessUnit(name=name, code=code, is_active=True)
        session.add(bu)
        await session.commit()
        await session.refresh(bu)
        return bu


async def _grant_bu_access(
    session_maker: async_sessionmaker[AsyncSession],
    *,
    user_id,
    bu_id,
    role: str = "bu_user",
) -> None:
    async with session_maker() as session:
        session.add(UserBUAccess(user_id=user_id, bu_id=bu_id, role=role, is_active=True))
        await session.commit()


@pytest.mark.asyncio
async def test_protected_endpoint_without_token_returns_401(client):
    response = await client.get("/bus/")

    assert response.status_code == 401
    assert response.json()["detail"] == "Falta token de acceso"


@pytest.mark.asyncio
async def test_user_without_bu_access_gets_403_on_prompt_configs(client, session_maker):
    user = await _create_user(session_maker, email="user@test.local")
    bu_allowed = await _create_bu(session_maker, name="Allowed", code="ALLOWED")
    bu_forbidden = await _create_bu(session_maker, name="Forbidden", code="FORBID")
    await _grant_bu_access(session_maker, user_id=user.id, bu_id=bu_allowed.id)

    token = create_access_token(subject=str(user.id), role="bu_user", expires_minutes=30)

    response = await client.get(
        "/prompt-configs/",
        headers={
            **_bearer(token),
            "X-BU-ID": str(bu_forbidden.id),
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Sin acceso a esta BU"


@pytest.mark.asyncio
async def test_user_with_bu_access_can_list_my_business_units(client, session_maker):
    user = await _create_user(session_maker, email="my-access-user@test.local")
    bu = await _create_bu(session_maker, name="MyAccess BU", code=f"MA_{uuid4().hex[:6]}")
    await _grant_bu_access(session_maker, user_id=user.id, bu_id=bu.id, role="bu_user")
    token = create_access_token(subject=str(user.id), role="bu_user", expires_minutes=30)

    response = await client.get("/bus/my-access", headers=_bearer(token))

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["id"] == str(bu.id)


@pytest.mark.asyncio
async def test_user_without_bu_access_gets_empty_my_business_units(client, session_maker):
    user = await _create_user(session_maker, email="my-access-empty@test.local")
    token = create_access_token(subject=str(user.id), role="bu_user", expires_minutes=30)

    response = await client.get("/bus/my-access", headers=_bearer(token))

    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_prompt_configs_are_isolated_by_bu(client, session_maker):
    admin = await _create_user(
        session_maker,
        email="admin@test.local",
        is_global_admin=True,
    )
    bu_a = await _create_bu(session_maker, name="BU A", code=f"A_{uuid4().hex[:6]}")
    bu_b = await _create_bu(session_maker, name="BU B", code=f"B_{uuid4().hex[:6]}")

    token = create_access_token(subject=str(admin.id), role="admin_global", expires_minutes=30)

    payload = {
        "name": "Config A",
        "description": "Solo BU A",
        "base_prompt": "Extrae {{VARIABLE_BLOCK}}",
        "variables": [
            {
                "name": "nif",
                "description": "NIF del documento",
                "required": True,
                "type": "string",
            }
        ],
        "model": "gpt-4o",
        "temperature": 0,
    }

    created = await client.post(
        "/prompt-configs/",
        headers={
            **_bearer(token),
            "X-BU-ID": str(bu_a.id),
            "Content-Type": "application/json",
        },
        json=payload,
    )
    assert created.status_code == 201

    list_a = await client.get(
        "/prompt-configs/",
        headers={
            **_bearer(token),
            "X-BU-ID": str(bu_a.id),
        },
    )
    assert list_a.status_code == 200
    data_a = list_a.json()
    assert len(data_a) == 1
    assert data_a[0]["name"] == "Config A"

    list_b = await client.get(
        "/prompt-configs/",
        headers={
            **_bearer(token),
            "X-BU-ID": str(bu_b.id),
        },
    )
    assert list_b.status_code == 200
    data_b = list_b.json()
    assert data_b == []


@pytest.mark.asyncio
async def test_bu_user_cannot_create_prompt_config(client, session_maker):
    user = await _create_user(session_maker, email="buuser@test.local")
    bu = await _create_bu(session_maker, name="BU User", code=f"U_{uuid4().hex[:6]}")
    await _grant_bu_access(session_maker, user_id=user.id, bu_id=bu.id, role="bu_user")

    token = create_access_token(subject=str(user.id), role="bu_user", expires_minutes=30)
    payload = {
        "name": "Config bloqueada",
        "description": "No deberia crearse",
        "base_prompt": "Extrae {{VARIABLE_BLOCK}}",
        "variables": [
            {
                "name": "campo",
                "description": "Campo",
                "required": True,
                "type": "string",
            }
        ],
        "model": "gpt-4o",
        "temperature": 0,
    }

    response = await client.post(
        "/prompt-configs/",
        headers={
            **_bearer(token),
            "X-BU-ID": str(bu.id),
            "Content-Type": "application/json",
        },
        json=payload,
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "No tienes permisos para configurar prompts en esta BU"


@pytest.mark.asyncio
async def test_bu_admin_can_create_prompt_config(client, session_maker):
    user = await _create_user(session_maker, email="buadmin@test.local")
    bu = await _create_bu(session_maker, name="BU Admin", code=f"A_{uuid4().hex[:6]}")
    await _grant_bu_access(session_maker, user_id=user.id, bu_id=bu.id, role="bu_admin")

    token = create_access_token(subject=str(user.id), role="bu_user", expires_minutes=30)
    payload = {
        "name": "Config permitida",
        "description": "Debe crearse",
        "base_prompt": "Extrae {{VARIABLE_BLOCK}}",
        "variables": [
            {
                "name": "campo",
                "description": "Campo",
                "required": True,
                "type": "string",
            }
        ],
        "model": "gpt-4o",
        "temperature": 0,
    }

    response = await client.post(
        "/prompt-configs/",
        headers={
            **_bearer(token),
            "X-BU-ID": str(bu.id),
            "Content-Type": "application/json",
        },
        json=payload,
    )

    assert response.status_code == 201


@pytest.mark.asyncio
async def test_bu_admin_can_delete_prompt_config(client, session_maker):
    user = await _create_user(session_maker, email="buadmin-delete-prompt@test.local")
    bu = await _create_bu(session_maker, name="BU Admin Delete Prompt", code=f"DP_{uuid4().hex[:6]}")
    await _grant_bu_access(session_maker, user_id=user.id, bu_id=bu.id, role="bu_admin")

    token = create_access_token(subject=str(user.id), role="bu_user", expires_minutes=30)
    payload = {
        "name": "Config eliminable",
        "description": "Debe poder eliminarse",
        "base_prompt": "Extrae {{VARIABLE_BLOCK}}",
        "variables": [
            {
                "name": "campo",
                "description": "Campo",
                "required": True,
                "type": "string",
            }
        ],
        "model": "gpt-4o",
        "temperature": 0,
    }

    created = await client.post(
        "/prompt-configs/",
        headers={
            **_bearer(token),
            "X-BU-ID": str(bu.id),
            "Content-Type": "application/json",
        },
        json=payload,
    )
    assert created.status_code == 201
    config_id = created.json()["id"]

    deleted = await client.delete(
        f"/prompt-configs/{config_id}",
        headers={
            **_bearer(token),
            "X-BU-ID": str(bu.id),
        },
    )
    assert deleted.status_code == 204

    listed = await client.get(
        "/prompt-configs/",
        headers={
            **_bearer(token),
            "X-BU-ID": str(bu.id),
        },
    )
    assert listed.status_code == 200
    assert listed.json() == []


@pytest.mark.asyncio
async def test_bu_user_cannot_delete_prompt_config(client, session_maker):
    admin_user = await _create_user(session_maker, email="admin-create-delete-denied@test.local")
    normal_user = await _create_user(session_maker, email="buuser-delete-prompt@test.local")
    bu = await _create_bu(session_maker, name="BU Delete Prompt Denied", code=f"DD_{uuid4().hex[:6]}")
    await _grant_bu_access(session_maker, user_id=admin_user.id, bu_id=bu.id, role="bu_admin")
    await _grant_bu_access(session_maker, user_id=normal_user.id, bu_id=bu.id, role="bu_user")

    admin_token = create_access_token(subject=str(admin_user.id), role="bu_user", expires_minutes=30)
    user_token = create_access_token(subject=str(normal_user.id), role="bu_user", expires_minutes=30)

    payload = {
        "name": "Config protegida",
        "description": "No debería poder borrarla bu_user",
        "base_prompt": "Extrae {{VARIABLE_BLOCK}}",
        "variables": [
            {
                "name": "campo",
                "description": "Campo",
                "required": True,
                "type": "string",
            }
        ],
        "model": "gpt-4o",
        "temperature": 0,
    }

    created = await client.post(
        "/prompt-configs/",
        headers={
            **_bearer(admin_token),
            "X-BU-ID": str(bu.id),
            "Content-Type": "application/json",
        },
        json=payload,
    )
    assert created.status_code == 201
    config_id = created.json()["id"]

    deleted = await client.delete(
        f"/prompt-configs/{config_id}",
        headers={
            **_bearer(user_token),
            "X-BU-ID": str(bu.id),
        },
    )
    assert deleted.status_code == 403
    assert deleted.json()["detail"] == "No tienes permisos para configurar prompts en esta BU"


@pytest.mark.asyncio
async def test_bu_viewer_cannot_upload_document(client, session_maker):
    user = await _create_user(session_maker, email="viewer-upload@test.local")
    bu = await _create_bu(session_maker, name="Viewer Upload", code=f"VU_{uuid4().hex[:6]}")
    await _grant_bu_access(session_maker, user_id=user.id, bu_id=bu.id, role="bu_viewer")

    token = create_access_token(subject=str(user.id), role="bu_user", expires_minutes=30)
    files = {"file": ("viewer.txt", b"contenido", "text/plain")}

    response = await client.post(
        "/documents/",
        headers={
            **_bearer(token),
            "X-BU-ID": str(bu.id),
        },
        files=files,
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "No tienes permisos para subir documentos en esta BU"


@pytest.mark.asyncio
async def test_bu_viewer_cannot_create_collection(client, session_maker):
    user = await _create_user(session_maker, email="viewer-collection@test.local")
    bu = await _create_bu(session_maker, name="Viewer Collection", code=f"VC_{uuid4().hex[:6]}")
    await _grant_bu_access(session_maker, user_id=user.id, bu_id=bu.id, role="bu_viewer")

    token = create_access_token(subject=str(user.id), role="bu_user", expires_minutes=30)
    payload = {
        "name": "Coleccion Viewer",
        "config_id": str(uuid4()),
    }

    response = await client.post(
        "/collections/",
        headers={
            **_bearer(token),
            "X-BU-ID": str(bu.id),
            "Content-Type": "application/json",
        },
        json=payload,
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "No tienes permisos para crear colecciones en esta BU"


@pytest.mark.asyncio
async def test_bu_viewer_cannot_validate_extraction(client, session_maker):
    user = await _create_user(session_maker, email="viewer-validate@test.local")
    bu = await _create_bu(session_maker, name="Viewer Validate", code=f"VV_{uuid4().hex[:6]}")
    await _grant_bu_access(session_maker, user_id=user.id, bu_id=bu.id, role="bu_viewer")

    token = create_access_token(subject=str(user.id), role="bu_user", expires_minutes=30)
    payload = {
        "result": [],
    }

    response = await client.patch(
        f"/extractions/{uuid4()}/validate",
        headers={
            **_bearer(token),
            "X-BU-ID": str(bu.id),
            "Content-Type": "application/json",
        },
        json=payload,
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "No tienes permisos para validar extracciones en esta BU"


@pytest.mark.asyncio
async def test_bu_admin_can_assign_user_in_same_bu(client, session_maker):
    admin_user = await _create_user(session_maker, email="bu-admin-assign@test.local")
    target_user = await _create_user(session_maker, email="target-user@test.local")
    bu = await _create_bu(session_maker, name="BU Assign", code=f"BA_{uuid4().hex[:6]}")
    await _grant_bu_access(session_maker, user_id=admin_user.id, bu_id=bu.id, role="bu_admin")

    token = create_access_token(subject=str(admin_user.id), role="bu_user", expires_minutes=30)
    response = await client.post(
        f"/bus/{bu.id}/users",
        headers={
            **_bearer(token),
            "X-BU-ID": str(bu.id),
            "Content-Type": "application/json",
        },
        json={"user_id": str(target_user.id), "role": "bu_viewer"},
    )

    assert response.status_code == 201
    assert response.json()["role"] == "bu_viewer"


@pytest.mark.asyncio
async def test_bu_user_cannot_assign_user_in_bu(client, session_maker):
    actor = await _create_user(session_maker, email="bu-user-assign@test.local")
    target_user = await _create_user(session_maker, email="target-user-2@test.local")
    bu = await _create_bu(session_maker, name="BU Assign Denied", code=f"BD_{uuid4().hex[:6]}")
    await _grant_bu_access(session_maker, user_id=actor.id, bu_id=bu.id, role="bu_user")

    token = create_access_token(subject=str(actor.id), role="bu_user", expires_minutes=30)
    response = await client.post(
        f"/bus/{bu.id}/users",
        headers={
            **_bearer(token),
            "X-BU-ID": str(bu.id),
            "Content-Type": "application/json",
        },
        json={"user_id": str(target_user.id), "role": "bu_viewer"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "No tienes permisos para administrar usuarios de esta BU"


@pytest.mark.asyncio
async def test_bu_admin_can_list_and_remove_user_in_same_bu(client, session_maker):
    admin_user = await _create_user(session_maker, email="bu-admin-list-remove@test.local")
    target_user = await _create_user(session_maker, email="target-list-remove@test.local")
    bu = await _create_bu(session_maker, name="BU Users", code=f"UR_{uuid4().hex[:6]}")
    await _grant_bu_access(session_maker, user_id=admin_user.id, bu_id=bu.id, role="bu_admin")
    await _grant_bu_access(session_maker, user_id=target_user.id, bu_id=bu.id, role="bu_user")

    token = create_access_token(subject=str(admin_user.id), role="bu_user", expires_minutes=30)

    list_response = await client.get(
        f"/bus/{bu.id}/users",
        headers={
            **_bearer(token),
            "X-BU-ID": str(bu.id),
        },
    )
    assert list_response.status_code == 200
    listed_ids = [row["user_id"] for row in list_response.json()]
    assert str(target_user.id) in listed_ids

    remove_response = await client.delete(
        f"/bus/{bu.id}/users/{target_user.id}",
        headers={
            **_bearer(token),
            "X-BU-ID": str(bu.id),
        },
    )
    assert remove_response.status_code == 204

    list_after = await client.get(
        f"/bus/{bu.id}/users",
        headers={
            **_bearer(token),
            "X-BU-ID": str(bu.id),
        },
    )
    assert list_after.status_code == 200
    listed_after_ids = [row["user_id"] for row in list_after.json()]
    assert str(target_user.id) not in listed_after_ids


@pytest.mark.asyncio
async def test_cannot_modify_global_admin_access_or_role(client, session_maker):
    actor = await _create_user(session_maker, email="global-mod-actor@test.local", is_global_admin=True)
    target_global = await _create_user(session_maker, email="global-mod-target@test.local", is_global_admin=True)
    bu = await _create_bu(session_maker, name="BU Global Lock", code=f"GL_{uuid4().hex[:6]}")
    token = create_access_token(subject=str(actor.id), role="admin_global", expires_minutes=30)

    assign_response = await client.post(
        f"/bus/{bu.id}/users",
        headers={
            **_bearer(token),
            "X-BU-ID": str(bu.id),
            "Content-Type": "application/json",
        },
        json={"user_id": str(target_global.id), "role": "bu_viewer"},
    )
    assert assign_response.status_code == 400
    assert assign_response.json()["detail"] == "No se puede modificar acceso o rol de un admin_global"

    remove_response = await client.delete(
        f"/bus/{bu.id}/users/{target_global.id}",
        headers={
            **_bearer(token),
            "X-BU-ID": str(bu.id),
        },
    )
    assert remove_response.status_code == 400
    assert remove_response.json()["detail"] == "No se puede modificar acceso o rol de un admin_global"


@pytest.mark.asyncio
async def test_denied_prompt_config_write_creates_audit_event(client, session_maker):
    user = await _create_user(session_maker, email="audit-denied@test.local")
    bu = await _create_bu(session_maker, name="BU Audit", code=f"AU_{uuid4().hex[:6]}")
    await _grant_bu_access(session_maker, user_id=user.id, bu_id=bu.id, role="bu_user")

    token = create_access_token(subject=str(user.id), role="bu_user", expires_minutes=30)
    payload = {
        "name": "Config audit denegada",
        "description": "No deberia crearse",
        "base_prompt": "Extrae {{VARIABLE_BLOCK}}",
        "variables": [
            {
                "name": "campo",
                "description": "Campo",
                "required": True,
                "type": "string",
            }
        ],
        "model": "gpt-4o",
        "temperature": 0,
    }

    response = await client.post(
        "/prompt-configs/",
        headers={
            **_bearer(token),
            "X-BU-ID": str(bu.id),
            "Content-Type": "application/json",
        },
        json=payload,
    )

    assert response.status_code == 403

    async with session_maker() as session:
        result = await session.execute(
            select(AuditEvent).where(
                AuditEvent.actor_user_id == user.id,
                AuditEvent.event_type == "authz.denied",
            )
        )
        event = result.scalars().first()

    assert event is not None
    assert event.bu_id == bu.id
    assert event.message == "No tienes permisos para configurar prompts en esta BU"


@pytest.mark.asyncio
async def test_non_global_admin_denied_dashboard_creates_audit_event(client, session_maker):
    user = await _create_user(session_maker, email="no-global-admin@test.local")
    token = create_access_token(subject=str(user.id), role="bu_user", expires_minutes=30)

    response = await client.get(
        "/admin/dashboard",
        headers=_bearer(token),
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Requiere rol admin_global"

    async with session_maker() as session:
        result = await session.execute(
            select(AuditEvent).where(
                AuditEvent.actor_user_id == user.id,
                AuditEvent.event_type == "authz.denied",
            )
        )
        events = list(result.scalars().all())

    assert any((e.message or "") == "Requiere rol admin_global" for e in events)


@pytest.mark.asyncio
async def test_global_admin_can_read_audit_events(client, session_maker):
    admin = await _create_user(session_maker, email="audit-reader-admin@test.local", is_global_admin=True)
    token = create_access_token(subject=str(admin.id), role="admin_global", expires_minutes=30)

    response = await client.get(
        "/admin/audit-events?event_type=authz.denied&limit=10",
        headers=_bearer(token),
    )

    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.asyncio
async def test_non_global_admin_cannot_read_audit_events(client, session_maker):
    user = await _create_user(session_maker, email="audit-non-admin@test.local")
    token = create_access_token(subject=str(user.id), role="bu_user", expires_minutes=30)

    response = await client.get(
        "/admin/audit-events",
        headers=_bearer(token),
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Requiere rol admin_global"


@pytest.mark.asyncio
async def test_global_admin_audit_events_support_skip_and_limit(client, session_maker):
    admin = await _create_user(session_maker, email="audit-skip-admin@test.local", is_global_admin=True)

    async with session_maker() as session:
        session.add(
            AuditEvent(
                actor_user_id=admin.id,
                event_type="authz.denied",
                message="evento-1",
            )
        )
        session.add(
            AuditEvent(
                actor_user_id=admin.id,
                event_type="authz.denied",
                message="evento-2",
            )
        )
        await session.commit()

    token = create_access_token(subject=str(admin.id), role="admin_global", expires_minutes=30)
    response = await client.get(
        "/admin/audit-events?event_type=authz.denied&skip=1&limit=1",
        headers=_bearer(token),
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
