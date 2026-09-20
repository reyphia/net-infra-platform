from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.api.schemas import AuditEventOut
from app.audit.service import AuditService

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("", response_model=list[AuditEventOut])
async def list_audit_events(
    device_id: str | None = None,
    action: str | None = None,
    operator: str | None = None,
    limit: int = 200,
    session: AsyncSession = Depends(get_db),
) -> list:
    service = AuditService(session)
    return await service.list_events(device_id=device_id, action=action, operator=operator, limit=limit)
