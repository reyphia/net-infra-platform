from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings


class Base(DeclarativeBase):
    pass


settings = get_settings()

# SQLite needs check_same_thread=False equivalent handled by aiosqlite driver.
# PostgreSQL-compatible: swapping DATABASE_URL to a postgresql+asyncpg:// DSN
# works without any code changes because all queries use SQLAlchemy Core/ORM,
# no SQLite-specific SQL.
engine = create_async_engine(settings.database_url, echo=False, future=True)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session


async def init_models() -> None:
    """Create tables if they do not exist yet.

    Used for SQLite dev/test bootstrap. In production, use Alembic
    migrations (backend/alembic/) instead of relying on this.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
