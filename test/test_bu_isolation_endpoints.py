from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import BusinessUnit, Collection, Document, Extraction, PromptConfig, User, UserBUAccess
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


async def _create_prompt_config(
    session_maker: async_sessionmaker[AsyncSession],
    *,
    bu_id,
    name: str,
) -> PromptConfig:
    async with session_maker() as session:
        config = PromptConfig(
            bu_id=bu_id,
            name=name,
            description="cfg",
            base_prompt="Extrae {{VARIABLE_BLOCK}}",
            variables=[
                {
                    "name": "field",
                    "description": "Campo",
                    "required": True,
                    "type": "string",
                }
            ],
            model="gpt-4o",
            temperature=0,
            is_active=True,
        )
        session.add(config)
        await session.commit()
        await session.refresh(config)
        return config


async def _create_collection(
    session_maker: async_sessionmaker[AsyncSession],
    *,
    bu_id,
    config_id,
    name: str,
) -> Collection:
    async with session_maker() as session:
        collection = Collection(bu_id=bu_id, name=name, config_id=config_id)
        session.add(collection)
        await session.commit()
        await session.refresh(collection)
        return collection


async def _create_document(
    session_maker: async_sessionmaker[AsyncSession],
    *,
    bu_id,
    created_by,
    title: str,
) -> Document:
    unique = uuid4().hex
    async with session_maker() as session:
        doc = Document(
            bu_id=bu_id,
            title=title,
            filename=f"{title}.txt",
            mime_type="text/plain",
            size_bytes=20,
            sha256=unique,
            storage_key=f"tests/{unique}.txt",
            created_by=created_by,
        )
        session.add(doc)
        await session.commit()
        await session.refresh(doc)
        return doc


async def _create_extraction(
    session_maker: async_sessionmaker[AsyncSession],
    *,
    bu_id,
    config_id,
    document_id,
    document_name: str,
    collection_id=None,
) -> Extraction:
    async with session_maker() as session:
        ext = Extraction(
            prompt_config_id=config_id,
            bu_id=bu_id,
            document_id=document_id,
            collection_id=collection_id,
            document_name=document_name,
            document_hash=uuid4().hex,
            prompt_sent="prompt",
            raw_llm_response='[{"title": "field", "answer": "value"}]',
            status="success",
            retries=0,
        )
        session.add(ext)
        await session.commit()
        await session.refresh(ext)
        return ext


@pytest.mark.asyncio
async def test_documents_list_is_isolated_by_bu(client, session_maker):
    user = await _create_user(session_maker, email="docs-user@test.local")
    bu_a = await _create_bu(session_maker, name="Docs A", code=f"DA_{uuid4().hex[:6]}")
    bu_b = await _create_bu(session_maker, name="Docs B", code=f"DB_{uuid4().hex[:6]}")
    await _grant_bu_access(session_maker, user_id=user.id, bu_id=bu_a.id)
    await _grant_bu_access(session_maker, user_id=user.id, bu_id=bu_b.id)

    await _create_document(session_maker, bu_id=bu_a.id, created_by=user.id, title="Doc A")
    await _create_document(session_maker, bu_id=bu_b.id, created_by=user.id, title="Doc B")

    token = create_access_token(subject=str(user.id), role="bu_user", expires_minutes=30)

    response = await client.get(
        "/documents/",
        headers={
            **_bearer(token),
            "X-BU-ID": str(bu_a.id),
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert len(body["items"]) == 1
    assert body["items"][0]["title"] == "Doc A"


@pytest.mark.asyncio
async def test_extractions_list_is_isolated_by_bu(client, session_maker):
    user = await _create_user(session_maker, email="ext-user@test.local")
    bu_a = await _create_bu(session_maker, name="Ext A", code=f"EA_{uuid4().hex[:6]}")
    bu_b = await _create_bu(session_maker, name="Ext B", code=f"EB_{uuid4().hex[:6]}")
    await _grant_bu_access(session_maker, user_id=user.id, bu_id=bu_a.id)
    await _grant_bu_access(session_maker, user_id=user.id, bu_id=bu_b.id)

    config_a = await _create_prompt_config(session_maker, bu_id=bu_a.id, name="Cfg A")
    config_b = await _create_prompt_config(session_maker, bu_id=bu_b.id, name="Cfg B")
    doc_a = await _create_document(session_maker, bu_id=bu_a.id, created_by=user.id, title="ExtDoc A")
    doc_b = await _create_document(session_maker, bu_id=bu_b.id, created_by=user.id, title="ExtDoc B")
    await _create_extraction(
        session_maker,
        bu_id=bu_a.id,
        config_id=config_a.id,
        document_id=doc_a.id,
        document_name="ExtDoc A",
    )
    await _create_extraction(
        session_maker,
        bu_id=bu_b.id,
        config_id=config_b.id,
        document_id=doc_b.id,
        document_name="ExtDoc B",
    )

    token = create_access_token(subject=str(user.id), role="bu_user", expires_minutes=30)

    response = await client.get(
        "/extractions/",
        headers={
            **_bearer(token),
            "X-BU-ID": str(bu_a.id),
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["document_name"] == "ExtDoc A"


@pytest.mark.asyncio
async def test_collections_list_is_isolated_by_bu(client, session_maker):
    user = await _create_user(session_maker, email="col-user@test.local")
    bu_a = await _create_bu(session_maker, name="Col A", code=f"CA_{uuid4().hex[:6]}")
    bu_b = await _create_bu(session_maker, name="Col B", code=f"CB_{uuid4().hex[:6]}")
    await _grant_bu_access(session_maker, user_id=user.id, bu_id=bu_a.id)
    await _grant_bu_access(session_maker, user_id=user.id, bu_id=bu_b.id)

    config_a = await _create_prompt_config(session_maker, bu_id=bu_a.id, name="Cfg Col A")
    config_b = await _create_prompt_config(session_maker, bu_id=bu_b.id, name="Cfg Col B")
    await _create_collection(session_maker, bu_id=bu_a.id, config_id=config_a.id, name="Collection A")
    await _create_collection(session_maker, bu_id=bu_b.id, config_id=config_b.id, name="Collection B")

    token = create_access_token(subject=str(user.id), role="bu_user", expires_minutes=30)

    response = await client.get(
        "/collections/",
        headers={
            **_bearer(token),
            "X-BU-ID": str(bu_a.id),
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["name"] == "Collection A"


@pytest.mark.asyncio
async def test_document_detail_from_other_bu_returns_404(client, session_maker):
    user = await _create_user(session_maker, email="doc-detail-user@test.local")
    bu_a = await _create_bu(session_maker, name="DocDetail A", code=f"DDA_{uuid4().hex[:6]}")
    bu_b = await _create_bu(session_maker, name="DocDetail B", code=f"DDB_{uuid4().hex[:6]}")
    await _grant_bu_access(session_maker, user_id=user.id, bu_id=bu_a.id)
    await _grant_bu_access(session_maker, user_id=user.id, bu_id=bu_b.id)

    doc_b = await _create_document(session_maker, bu_id=bu_b.id, created_by=user.id, title="Hidden Doc")
    token = create_access_token(subject=str(user.id), role="bu_user", expires_minutes=30)

    response = await client.get(
        f"/documents/{doc_b.id}",
        headers={
            **_bearer(token),
            "X-BU-ID": str(bu_a.id),
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Documento no encontrado"


@pytest.mark.asyncio
async def test_extraction_detail_from_other_bu_returns_404(client, session_maker):
    user = await _create_user(session_maker, email="ext-detail-user@test.local")
    bu_a = await _create_bu(session_maker, name="ExtDetail A", code=f"EDA_{uuid4().hex[:6]}")
    bu_b = await _create_bu(session_maker, name="ExtDetail B", code=f"EDB_{uuid4().hex[:6]}")
    await _grant_bu_access(session_maker, user_id=user.id, bu_id=bu_a.id)
    await _grant_bu_access(session_maker, user_id=user.id, bu_id=bu_b.id)

    config_b = await _create_prompt_config(session_maker, bu_id=bu_b.id, name="Cfg Ext Detail B")
    doc_b = await _create_document(session_maker, bu_id=bu_b.id, created_by=user.id, title="ExtDetailDoc B")
    extraction_b = await _create_extraction(
        session_maker,
        bu_id=bu_b.id,
        config_id=config_b.id,
        document_id=doc_b.id,
        document_name="ExtDetailDoc B",
    )

    token = create_access_token(subject=str(user.id), role="bu_user", expires_minutes=30)
    response = await client.get(
        f"/extractions/{extraction_b.id}",
        headers={
            **_bearer(token),
            "X-BU-ID": str(bu_a.id),
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Extracción no encontrada"


@pytest.mark.asyncio
async def test_collection_detail_from_other_bu_returns_404(client, session_maker):
    user = await _create_user(session_maker, email="col-detail-user@test.local")
    bu_a = await _create_bu(session_maker, name="ColDetail A", code=f"CDA_{uuid4().hex[:6]}")
    bu_b = await _create_bu(session_maker, name="ColDetail B", code=f"CDB_{uuid4().hex[:6]}")
    await _grant_bu_access(session_maker, user_id=user.id, bu_id=bu_a.id)
    await _grant_bu_access(session_maker, user_id=user.id, bu_id=bu_b.id)

    config_b = await _create_prompt_config(session_maker, bu_id=bu_b.id, name="Cfg Col Detail B")
    collection_b = await _create_collection(session_maker, bu_id=bu_b.id, config_id=config_b.id, name="Hidden Collection")

    token = create_access_token(subject=str(user.id), role="bu_user", expires_minutes=30)
    response = await client.get(
        f"/collections/{collection_b.id}",
        headers={
            **_bearer(token),
            "X-BU-ID": str(bu_a.id),
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Colección no encontrada"


@pytest.mark.asyncio
async def test_collection_extractions_from_other_bu_returns_404(client, session_maker):
    user = await _create_user(session_maker, email="col-ext-user@test.local")
    bu_a = await _create_bu(session_maker, name="ColExt A", code=f"CEA_{uuid4().hex[:6]}")
    bu_b = await _create_bu(session_maker, name="ColExt B", code=f"CEB_{uuid4().hex[:6]}")
    await _grant_bu_access(session_maker, user_id=user.id, bu_id=bu_a.id)
    await _grant_bu_access(session_maker, user_id=user.id, bu_id=bu_b.id)

    config_b = await _create_prompt_config(session_maker, bu_id=bu_b.id, name="Cfg Col Ext B")
    collection_b = await _create_collection(session_maker, bu_id=bu_b.id, config_id=config_b.id, name="Collection Ext B")
    doc_b = await _create_document(session_maker, bu_id=bu_b.id, created_by=user.id, title="Doc Col Ext B")
    await _create_extraction(
        session_maker,
        bu_id=bu_b.id,
        config_id=config_b.id,
        document_id=doc_b.id,
        document_name="Doc Col Ext B",
        collection_id=collection_b.id,
    )

    token = create_access_token(subject=str(user.id), role="bu_user", expires_minutes=30)
    response = await client.get(
        f"/collections/{collection_b.id}/extractions",
        headers={
            **_bearer(token),
            "X-BU-ID": str(bu_a.id),
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Colección no encontrada"


@pytest.mark.asyncio
async def test_collection_export_from_other_bu_returns_404(client, session_maker):
    user = await _create_user(session_maker, email="col-export-user@test.local")
    bu_a = await _create_bu(session_maker, name="ColExport A", code=f"CXA_{uuid4().hex[:6]}")
    bu_b = await _create_bu(session_maker, name="ColExport B", code=f"CXB_{uuid4().hex[:6]}")
    await _grant_bu_access(session_maker, user_id=user.id, bu_id=bu_a.id)
    await _grant_bu_access(session_maker, user_id=user.id, bu_id=bu_b.id)

    config_b = await _create_prompt_config(session_maker, bu_id=bu_b.id, name="Cfg Col Export B")
    collection_b = await _create_collection(session_maker, bu_id=bu_b.id, config_id=config_b.id, name="Collection Export B")

    token = create_access_token(subject=str(user.id), role="bu_user", expires_minutes=30)
    response = await client.get(
        f"/collections/{collection_b.id}/export/xlsx",
        headers={
            **_bearer(token),
            "X-BU-ID": str(bu_a.id),
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Colección no encontrada"


@pytest.mark.asyncio
async def test_collections_list_without_bu_header_returns_422(client, session_maker):
    user = await _create_user(session_maker, email="col-header-user@test.local")
    bu = await _create_bu(session_maker, name="ColHeader", code=f"CH_{uuid4().hex[:6]}")
    await _grant_bu_access(session_maker, user_id=user.id, bu_id=bu.id)

    token = create_access_token(subject=str(user.id), role="bu_user", expires_minutes=30)
    response = await client.get(
        "/collections/",
        headers={
            **_bearer(token),
        },
    )

    assert response.status_code == 422
