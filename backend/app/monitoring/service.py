from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Device, HealthSnapshot, ManagementMethod
from app.discovery.icmp import ping
from app.snmp.client import SNMPClient, SNMPCredential, SNMPError
from app.snmp.facts import get_health


class MonitoringService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def poll_device(self, device: Device, *, snmp_community: str | None, timeout: float = 2.0) -> HealthSnapshot:
        ping_result = await ping(device.management_ip, timeout_seconds=timeout)

        cpu_percent: float | None = None
        memory_percent: float | None = None
        if ManagementMethod.SNMP.value in device.available_management_methods and snmp_community:
            client = SNMPClient(device.management_ip, SNMPCredential(community=snmp_community), timeout=timeout)
            try:
                health = await get_health(client)
                cpu_percent = health.cpu_percent
                memory_percent = health.memory_percent
            except SNMPError:
                pass  # leave as None -- unavailable, not fabricated

        snapshot = HealthSnapshot(
            device_id=device.id,
            is_online=ping_result.reachable,
            cpu_percent=cpu_percent,
            memory_percent=memory_percent,
            temperature_celsius=None,  # NOT IMPLEMENTED: no widely-portable temperature OID wired up yet
            uptime_seconds=device.uptime_seconds,
            icmp_rtt_ms=ping_result.rtt_ms,
        )
        self.session.add(snapshot)
        device.is_online = ping_result.reachable
        await self.session.commit()
        await self.session.refresh(snapshot)
        return snapshot

    async def latest_snapshot(self, device_id: str) -> HealthSnapshot | None:
        result = await self.session.execute(
            select(HealthSnapshot)
            .where(HealthSnapshot.device_id == device_id)
            .order_by(HealthSnapshot.collected_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def history(self, device_id: str, limit: int = 100) -> list[HealthSnapshot]:
        result = await self.session.execute(
            select(HealthSnapshot)
            .where(HealthSnapshot.device_id == device_id)
            .order_by(HealthSnapshot.collected_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())
