from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_monitoring_service
from app.core.config import get_settings
from app.db.models import Device
from app.monitoring.service import MonitoringService

router = APIRouter(prefix="/devices/{device_id}/health", tags=["monitoring"])


@router.post("/poll")
async def poll_device_health(
    device_id: str,
    session: AsyncSession = Depends(get_db),
    monitoring: MonitoringService = Depends(get_monitoring_service),
) -> dict:
    device = await session.get(Device, device_id)
    if device is None:
        raise HTTPException(status_code=404, detail=f"No device with id {device_id}")
    settings = get_settings()
    snapshot = await monitoring.poll_device(device, snmp_community=settings.snmp_default_community or None)
    return {
        "is_online": snapshot.is_online,
        "cpu_percent": snapshot.cpu_percent,
        "memory_percent": snapshot.memory_percent,
        "temperature_celsius": snapshot.temperature_celsius,
        "icmp_rtt_ms": snapshot.icmp_rtt_ms,
        "collected_at": snapshot.collected_at.isoformat(),
    }


@router.get("/latest")
async def get_latest_health(
    device_id: str, monitoring: MonitoringService = Depends(get_monitoring_service)
) -> dict:
    snapshot = await monitoring.latest_snapshot(device_id)
    if snapshot is None:
        return {"available": False}
    return {
        "available": True,
        "is_online": snapshot.is_online,
        "cpu_percent": snapshot.cpu_percent,
        "memory_percent": snapshot.memory_percent,
        "temperature_celsius": snapshot.temperature_celsius,
        "icmp_rtt_ms": snapshot.icmp_rtt_ms,
        "collected_at": snapshot.collected_at.isoformat(),
    }


@router.get("/history")
async def get_health_history(
    device_id: str, limit: int = 100, monitoring: MonitoringService = Depends(get_monitoring_service)
) -> list[dict]:
    snapshots = await monitoring.history(device_id, limit=limit)
    return [
        {
            "is_online": s.is_online,
            "cpu_percent": s.cpu_percent,
            "memory_percent": s.memory_percent,
            "icmp_rtt_ms": s.icmp_rtt_ms,
            "collected_at": s.collected_at.isoformat(),
        }
        for s in snapshots
    ]
