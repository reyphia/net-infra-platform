from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.api.schemas import DeviceCredentialAssign, DeviceOut, InterfaceOut
from app.db.models import CredentialProfile, Device, Interface

router = APIRouter(prefix="/devices", tags=["devices"])


@router.get("", response_model=list[DeviceOut])
async def list_devices(
    device_type: str | None = None,
    vendor: str | None = None,
    management_state: str | None = None,
    online_only: bool = False,
    q: str | None = None,
    session: AsyncSession = Depends(get_db),
) -> list[Device]:
    query = select(Device)
    if device_type:
        query = query.where(Device.device_type == device_type)
    if vendor:
        query = query.where(Device.vendor == vendor)
    if management_state:
        query = query.where(Device.management_state == management_state)
    if online_only:
        query = query.where(Device.is_online.is_(True))
    if q:
        like = f"%{q}%"
        query = query.where((Device.hostname.ilike(like)) | (Device.management_ip.ilike(like)))
    result = await session.execute(query)
    return list(result.scalars().all())


@router.get("/{device_id}", response_model=DeviceOut)
async def get_device(device_id: str, session: AsyncSession = Depends(get_db)) -> Device:
    device = await session.get(Device, device_id)
    if device is None:
        raise HTTPException(status_code=404, detail=f"No device with id {device_id}")
    return device


@router.get("/{device_id}/interfaces", response_model=list[InterfaceOut])
async def get_device_interfaces(device_id: str, session: AsyncSession = Depends(get_db)) -> list[Interface]:
    device = await session.get(Device, device_id)
    if device is None:
        raise HTTPException(status_code=404, detail=f"No device with id {device_id}")
    result = await session.execute(select(Interface).where(Interface.device_id == device_id))
    return list(result.scalars().all())


@router.post("/{device_id}/credentials", response_model=DeviceOut)
async def assign_credential_profile(
    device_id: str, body: DeviceCredentialAssign, session: AsyncSession = Depends(get_db)
) -> Device:
    device = await session.get(Device, device_id)
    if device is None:
        raise HTTPException(status_code=404, detail=f"No device with id {device_id}")
    profile = await session.get(CredentialProfile, body.credential_profile_id)
    if profile is None:
        raise HTTPException(status_code=404, detail=f"No credential profile with id {body.credential_profile_id}")
    device.default_credential_profile_id = profile.id
    await session.commit()
    await session.refresh(device)
    return device


@router.post("/{device_id}/driver", response_model=DeviceOut)
async def set_driver_type(device_id: str, driver_type: str, session: AsyncSession = Depends(get_db)) -> Device:
    """Override the auto-inferred driver assignment (e.g. correct a
    misidentified vendor, or opt a device into the generic SSH driver)."""
    from app.drivers.factory import available_driver_types

    if driver_type not in available_driver_types():
        raise HTTPException(status_code=400, detail=f"Unknown driver_type. Available: {available_driver_types()}")
    device = await session.get(Device, device_id)
    if device is None:
        raise HTTPException(status_code=404, detail=f"No device with id {device_id}")
    device.driver_type = driver_type
    await session.commit()
    await session.refresh(device)
    return device


@router.delete("/{device_id}", status_code=204)
async def delete_device(device_id: str, session: AsyncSession = Depends(get_db)) -> None:
    device = await session.get(Device, device_id)
    if device is None:
        raise HTTPException(status_code=404, detail=f"No device with id {device_id}")
    await session.delete(device)
    await session.commit()
