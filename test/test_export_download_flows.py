from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import BusinessUnit, Document, Extraction, PromptConfig, User, UserBUAccess
from app.services.security import create_access_token, hash_password


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _create_user(
    session_maker: async_sessionmaker[AsyncSession],
    *,
    email: str,
    password: str = "StrongPass123!",
) -> User:
    async with session_maker() as session:
        user = User(
            email=email,
            full_name=email.split("@")[0],
            password_hash=hash_password(password),
            is_global_admin=False,
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
) -> None:
    async with session_maker() as session:
        session.add(UserBUAccess(user_id=user_id, bu_id=bu_id, role="bu_user", is_active=True))
        await session.commit()


async def _create_prompt_config(
    session_maker: async_sessionmaker[AsyncSession],
    *,
    bu_id,
) -> PromptConfig:
    async with session_maker() as session:
        config = PromptConfig(
            bu_id=bu_id,
            name="Cfg Export",
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


async def _create_document(
    session_maker: async_sessionmaker[AsyncSession],
    *,
    bu_id,
    created_by,
    storage_key: str,
) -> Document:
    async with session_maker() as session:
        doc = Document(
            bu_id=bu_id,
            title="Doc",
            filename="doc.txt",
            mime_type="text/plain",
            size_bytes=20,
            sha256=uuid4().hex,
            storage_key=storage_key,
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
) -> Extraction:
    async with session_maker() as session:
        ext = Extraction(
            prompt_config_id=config_id,
            bu_id=bu_id,
            document_id=document_id,
            document_name="doc.txt",
            document_hash=uuid4().hex,
            prompt_sent="prompt",
            raw_llm_response='[{"title":"field","answer":"value"}]',
            status="success",
            retries=0,
        )
        session.add(ext)
        await session.commit()
        await session.refresh(ext)
        return ext


@pytest.mark.asyncio
async def test_extractions_bulk_invalid_format_returns_400(client, session_maker):
    user = await _create_user(session_maker, email="export-format@test.local")
    bu = await _create_bu(session_maker, name="Export BU", code=f"EX_{uuid4().hex[:6]}")
    await _grant_bu_access(session_maker, user_id=user.id, bu_id=bu.id)
    token = create_access_token(subject=str(user.id), role="bu_user", expires_minutes=30)

    response = await client.get(
        "/extractions/export/bulk?format=xml",
        headers={**_bearer(token), "X-BU-ID": str(bu.id)},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Formato debe ser csv, xlsx o json"


@pytest.mark.asyncio
async def test_extraction_export_xlsx_returns_file(client, session_maker):
    user = await _create_user(session_maker, email="export-xlsx@test.local")
    bu = await _create_bu(session_maker, name="Export XLSX BU", code=f"EXX_{uuid4().hex[:6]}")
    await _grant_bu_access(session_maker, user_id=user.id, bu_id=bu.id)

    config = await _create_prompt_config(session_maker, bu_id=bu.id)
    doc = await _create_document(
        session_maker,
        bu_id=bu.id,
        created_by=user.id,
        storage_key=f"tests/{uuid4().hex}.txt",
    )
    extraction = await _create_extraction(
        session_maker,
        bu_id=bu.id,
        config_id=config.id,
        document_id=doc.id,
    )

    token = create_access_token(subject=str(user.id), role="bu_user", expires_minutes=30)
    response = await client.get(
        f"/extractions/{extraction.id}/export/xlsx",
        headers={**_bearer(token), "X-BU-ID": str(bu.id)},
    )

    assert response.status_code == 200
    assert "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" in response.headers["content-type"]
    assert response.content


@pytest.mark.asyncio
async def test_document_download_missing_file_returns_404(client, session_maker):
    user = await _create_user(session_maker, email="download-missing@test.local")
    bu = await _create_bu(session_maker, name="Download BU", code=f"DL_{uuid4().hex[:6]}")
    await _grant_bu_access(session_maker, user_id=user.id, bu_id=bu.id)

    missing_storage_key = f"tests/not-found-{uuid4().hex}.txt"
    doc = await _create_document(
        session_maker,
        bu_id=bu.id,
        created_by=user.id,
        storage_key=missing_storage_key,
    )

    token = create_access_token(subject=str(user.id), role="bu_user", expires_minutes=30)
    response = await client.get(
        f"/documents/{doc.id}/download",
        headers={**_bearer(token), "X-BU-ID": str(bu.id)},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Archivo no encontrado en storage"
