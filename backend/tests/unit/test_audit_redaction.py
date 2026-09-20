import pytest

from app.audit.service import AuditService


@pytest.mark.asyncio
async def test_audit_record_stores_normal_detail(db_session):
    service = AuditService(db_session)
    event = await service.record(operator="alice", action="config.backup", success=True, detail="source=running")
    assert event.detail == "source=running"


@pytest.mark.asyncio
async def test_audit_redacts_detail_that_looks_like_a_secret(db_session):
    service = AuditService(db_session)
    event = await service.record(
        operator="alice", action="credential.create", success=True, detail="password=hunter2"
    )
    assert "hunter2" not in event.detail
    assert "withheld" in event.detail


@pytest.mark.asyncio
async def test_audit_list_filters_by_device(db_session):
    service = AuditService(db_session)
    await service.record(operator="alice", action="a", success=True, device_id="dev-1")
    await service.record(operator="alice", action="a", success=True, device_id="dev-2")
    results = await service.list_events(device_id="dev-1")
    assert len(results) == 1
    assert results[0].device_id == "dev-1"
