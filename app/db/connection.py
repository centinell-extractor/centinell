# app/db/connection.py
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import text
from sqlalchemy.orm import DeclarativeBase
from typing import AsyncGenerator
import logging

from app.config import DATABASE_URL

logger = logging.getLogger(__name__)

# Engine asíncrono para PostgreSQL (Supabase)
engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    pool_size=5,
    max_overflow=10,
    pool_timeout=30,
    pool_recycle=1800,
)

# Base de la que heredarán todos los modelos
class Base(DeclarativeBase):
    pass

# Factoría de sesiones asíncronas
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# Dependencia para usar en las rutas de FastAPI
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            logger.exception("ERROR CRITICO en get_db")
            raise


async def init_models() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def apply_runtime_migrations() -> None:
    """Aplica migraciones ligeras para entornos sin Alembic (dev/local)."""
    dialect = engine.url.get_backend_name()

    async with engine.begin() as conn:
        if dialect == "sqlite":
            result = await conn.execute(text("PRAGMA table_info(prompt_configs)"))
            columns = {row[1] for row in result.fetchall()}

            if "bu_id" not in columns:
                await conn.execute(text("ALTER TABLE prompt_configs ADD COLUMN bu_id TEXT"))

            await conn.execute(text("UPDATE prompt_configs SET bu_id = (SELECT id FROM business_units ORDER BY created_at ASC LIMIT 1) WHERE bu_id IS NULL"))
            await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_prompt_config_bu ON prompt_configs (bu_id)"))

            result = await conn.execute(text("PRAGMA table_info(extractions)"))
            columns = {row[1] for row in result.fetchall()}

            if "bu_id" not in columns:
                await conn.execute(text("ALTER TABLE extractions ADD COLUMN bu_id TEXT"))
            if "document_id" not in columns:
                await conn.execute(text("ALTER TABLE extractions ADD COLUMN document_id TEXT"))

            await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_extraction_bu ON extractions (bu_id)"))
            await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_extraction_document ON extractions (document_id)"))
        else:
            await conn.execute(text("ALTER TABLE prompt_configs ADD COLUMN IF NOT EXISTS bu_id UUID"))
            await conn.execute(text("UPDATE prompt_configs SET bu_id = (SELECT id FROM business_units ORDER BY created_at ASC LIMIT 1) WHERE bu_id IS NULL"))
            await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_prompt_config_bu ON prompt_configs (bu_id)"))

            await conn.execute(text("ALTER TABLE extractions ADD COLUMN IF NOT EXISTS bu_id UUID"))
            await conn.execute(text("ALTER TABLE extractions ADD COLUMN IF NOT EXISTS document_id UUID"))
            await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_extraction_bu ON extractions (bu_id)"))
            await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_extraction_document ON extractions (document_id)"))