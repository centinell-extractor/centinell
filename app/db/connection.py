# app/db/connection.py
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
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