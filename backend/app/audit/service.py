from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AuditEvent

# Redaction is defense-in-depth: callers should never pass secrets into
# `detail`, but if a caller mistake ever put something secret-shaped in
# there, we strip it before it reaches the database.
_SECRET_KEYS = ("password", "secret", "community", "private_key", "enable_password")


def _redact(detail: str | None) -> str | None:
    if detail is None:
        return None
    lowered = detail.lower()
    if any(k in lowered for k in _SECRET_KEYS):
        return "[detail withheld: appeared to contain credential material]"
    return detail


class AuditService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def record(
        self,
        *,
        operator: str,
        action: str,
        success: bool,
        device_id: str | None = None,
        protocol: str | None = None,
        detail: str | None = None,
        error: str | None = None,
        session_id: str | None = None,
    ) -> AuditEvent:
        event = AuditEvent(
            operator=operator,
            action=action,
            device_id=device_id,
            protocol=protocol,
            detail=_redact(detail),
            success=success,
            error=_redact(error),
            source_session_id=session_id,
        )
        self.session.add(event)
        await self.session.commit()
        await self.session.refresh(event)
        return event

    async def list_events(
        self,
        *,
        device_id: str | None = None,
        action: str | None = None,
        operator: str | None = None,
        limit: int = 200,
    ) -> list[AuditEvent]:
        query = select(AuditEvent).order_by(AuditEvent.timestamp.desc()).limit(limit)
        if device_id:
            query = query.where(AuditEvent.device_id == device_id)
        if action:
            query = query.where(AuditEvent.action == action)
        if operator:
            query = query.where(AuditEvent.operator == operator)
        result = await self.session.execute(query)
        return list(result.scalars().all())
