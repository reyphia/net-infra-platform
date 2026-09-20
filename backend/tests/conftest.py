from __future__ import annotations

import os
from collections.abc import AsyncIterator

import asyncssh
import pytest
import pytest_asyncio
from cryptography.fernet import Fernet
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

os.environ.setdefault("ENCRYPTION_KEY", Fernet.generate_key().decode())
os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("ENVIRONMENT", "test")

from app.db.session import Base  # noqa: E402


@pytest.fixture()
def tmp_host_key(tmp_path) -> str:
    key = asyncssh.generate_private_key("ssh-ed25519")
    path = tmp_path / "fake_device_host_key"
    key.write_private_key(str(path))
    return str(path)


@pytest_asyncio.fixture()
async def db_session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as session:
        yield session
    await engine.dispose()
