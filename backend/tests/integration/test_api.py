"""API-level integration tests via FastAPI's TestClient (in-process, real
routing/validation/DB layer -- httpx makes real ASGI calls, nothing mocked
below the HTTP boundary). Each test gets an isolated in-memory SQLite DB via
a dependency override (not env vars: Settings is cached per-process by
design, matching how a real deployment behaves, so tests override the DB
dependency directly rather than fighting that cache).
"""
from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.deps import get_db
from app.db.session import Base
from app.main import create_app


async def _make_test_client() -> AsyncClient:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async def override_get_db() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


@pytest.mark.asyncio
async def test_health_endpoint():
    async with await _make_test_client() as client:
        response = await client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_devices_empty_list_initially():
    async with await _make_test_client() as client:
        response = await client.get("/api/devices")
        assert response.status_code == 200
        assert response.json() == []


@pytest.mark.asyncio
async def test_discovery_rejects_empty_scope():
    async with await _make_test_client() as client:
        response = await client.post("/api/discovery", json={"scope_cidrs": []})
        assert response.status_code == 422  # pydantic min_length validation


@pytest.mark.asyncio
async def test_discovery_rejects_garbage_cidr():
    async with await _make_test_client() as client:
        response = await client.post("/api/discovery", json={"scope_cidrs": ["not-a-cidr"]})
        assert response.status_code == 400


@pytest.mark.asyncio
async def test_credential_create_never_returns_secret():
    async with await _make_test_client() as client:
        response = await client.post(
            "/api/credentials",
            json={"name": "test", "protocol": "ssh", "username": "admin", "password": "hunter2"},
        )
        assert response.status_code == 201
        body = response.json()
        assert "password" not in body
        assert "hunter2" not in str(body)


@pytest.mark.asyncio
async def test_device_not_found_returns_structured_404():
    async with await _make_test_client() as client:
        response = await client.get("/api/devices/does-not-exist")
        assert response.status_code == 404
        assert "does-not-exist" in response.json()["detail"]


@pytest.mark.asyncio
async def test_change_plan_requires_at_least_one_device():
    async with await _make_test_client() as client:
        response = await client.post(
            "/api/change-plans",
            json={"name": "test", "operator": "alice", "proposed_config": "hostname X", "device_ids": []},
        )
        assert response.status_code == 422
