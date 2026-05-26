import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import BOOTSTRAP_ADMIN_EMAIL, BOOTSTRAP_ADMIN_NAME, BOOTSTRAP_ADMIN_PASSWORD
from app.db.models import User
from app.services.security import hash_password

logger = logging.getLogger(__name__)


async def ensure_bootstrap_admin(db: AsyncSession) -> None:
    if not BOOTSTRAP_ADMIN_EMAIL or not BOOTSTRAP_ADMIN_PASSWORD:
        logger.info("Bootstrap admin no configurado en env; se omite creación automática")
        return

    result = await db.execute(select(User).where(User.email == BOOTSTRAP_ADMIN_EMAIL))
    existing = result.scalars().first()
    if existing:
        logger.info("Usuario admin bootstrap ya existe")
        return

    user = User(
        email=BOOTSTRAP_ADMIN_EMAIL,
        full_name=BOOTSTRAP_ADMIN_NAME,
        password_hash=hash_password(BOOTSTRAP_ADMIN_PASSWORD),
        is_global_admin=True,
        is_active=True,
    )
    db.add(user)
    await db.commit()
    logger.info("Usuario admin bootstrap creado: %s", BOOTSTRAP_ADMIN_EMAIL)
