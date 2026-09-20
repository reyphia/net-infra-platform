from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_audit_service, get_backup_service, get_credential_service, get_db
from app.api.schemas import ConfigBackupOut, ErrorDetail
from app.audit.service import AuditService
from app.configuration.backup import ConfigBackupService
from app.configuration.diff import semantic_diff, semantic_diff_generic
from app.configuration.sanitize import sanitize_config
from app.core.config import get_settings
from app.credentials.service import CredentialService
from app.db.models import ConfigurationBackup, Device
from app.drivers.base import DriverCommandError, DriverConnectionError, SSHCredential
from app.drivers.factory import create_driver

router = APIRouter(prefix="/devices/{device_id}/configuration", tags=["configuration"])


async def _connect_driver(device: Device, credentials: CredentialService):
    if not device.default_credential_profile_id:
        raise HTTPException(
            status_code=400,
            detail="No credential profile assigned to this device. Assign one via POST /devices/{id}/credentials.",
        )
    profile = await credentials.get(device.default_credential_profile_id)
    if profile is None:
        raise HTTPException(status_code=400, detail="Assigned credential profile no longer exists.")
    resolved = credentials.resolve_ssh(profile)
    settings = get_settings()
    driver = create_driver(
        device.driver_type or "generic_ssh",
        device.management_ip,
        SSHCredential(
            username=resolved.username or "",
            password=resolved.password,
            enable_password=resolved.enable_password,
            private_key=resolved.private_key,
        ),
        known_hosts_path=settings.ssh_known_hosts_path,
        allow_insecure=settings.ssh_allow_insecure_lab_mode,
    )
    try:
        await driver.connect()
    except DriverConnectionError as exc:
        raise HTTPException(
            status_code=502,
            detail=ErrorDetail(
                message=str(exc),
                reason=exc.reason,
                possible_causes=[
                    "SSH is not enabled/reachable on the device",
                    "An ACL is blocking management access",
                    "The device is offline",
                    "Incorrect credentials",
                ],
            ).model_dump(),
        ) from exc
    return driver


@router.get("/live")
async def get_live_config(
    device_id: str,
    source: str = "running",
    sanitize: bool = True,
    session: AsyncSession = Depends(get_db),
    credentials: CredentialService = Depends(get_credential_service),
    audit: AuditService = Depends(get_audit_service),
) -> dict:
    device = await session.get(Device, device_id)
    if device is None:
        raise HTTPException(status_code=404, detail=f"No device with id {device_id}")
    driver = await _connect_driver(device, credentials)
    try:
        text = await driver.get_config(source=source)
        await audit.record(
            operator="api", action="config.retrieve", success=True, device_id=device_id, protocol="ssh", detail=source
        )
    except DriverCommandError as exc:
        await audit.record(
            operator="api", action="config.retrieve", success=False, device_id=device_id, protocol="ssh", error=str(exc)
        )
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    finally:
        await driver.disconnect()
    return {"source": source, "config": sanitize_config(text) if sanitize else text, "sanitized": sanitize}


@router.post("/backups", response_model=ConfigBackupOut, status_code=201)
async def create_backup(
    device_id: str,
    source: str = "running",
    operator: str = "api",
    session: AsyncSession = Depends(get_db),
    credentials: CredentialService = Depends(get_credential_service),
    backups: ConfigBackupService = Depends(get_backup_service),
    audit: AuditService = Depends(get_audit_service),
) -> ConfigurationBackup:
    device = await session.get(Device, device_id)
    if device is None:
        raise HTTPException(status_code=404, detail=f"No device with id {device_id}")
    driver = await _connect_driver(device, credentials)
    try:
        text = await driver.get_config(source=source)
    except DriverCommandError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    finally:
        await driver.disconnect()

    backup = await backups.create_backup(
        device=device, config_text=text, source=source, driver_type=device.driver_type or "unknown", operator=operator
    )
    await audit.record(operator=operator, action="config.backup", success=True, device_id=device_id, protocol="ssh")
    return backup


@router.get("/backups", response_model=list[ConfigBackupOut])
async def list_backups(device_id: str, session: AsyncSession = Depends(get_db)) -> list[ConfigurationBackup]:
    result = await session.execute(
        select(ConfigurationBackup)
        .where(ConfigurationBackup.device_id == device_id)
        .order_by(ConfigurationBackup.created_at.desc())
    )
    return list(result.scalars().all())


@router.get("/backups/{backup_id}/content")
async def get_backup_content(
    device_id: str,
    backup_id: str,
    sanitize: bool = True,
    session: AsyncSession = Depends(get_db),
    backups: ConfigBackupService = Depends(get_backup_service),
) -> dict:
    backup = await session.get(ConfigurationBackup, backup_id)
    if backup is None or backup.device_id != device_id:
        raise HTTPException(status_code=404, detail=f"No backup {backup_id} for device {device_id}")
    text = backups.read_backup_text(backup)
    return {"config": sanitize_config(text) if sanitize else text, "sanitized": sanitize}


@router.get("/backups/diff")
async def diff_backups(
    device_id: str,
    before_id: str,
    after_id: str,
    session: AsyncSession = Depends(get_db),
    backups: ConfigBackupService = Depends(get_backup_service),
) -> dict:
    before = await session.get(ConfigurationBackup, before_id)
    after = await session.get(ConfigurationBackup, after_id)
    if before is None or before.device_id != device_id:
        raise HTTPException(status_code=404, detail=f"No backup {before_id} for device {device_id}")
    if after is None or after.device_id != device_id:
        raise HTTPException(status_code=404, detail=f"No backup {after_id} for device {device_id}")

    before_text = backups.read_backup_text(before)
    after_text = backups.read_backup_text(after)
    diff_fn = semantic_diff if before.driver_type == "cisco_ios" else semantic_diff_generic
    report = diff_fn(before_text, after_text)
    return {
        "raw_diff": report.raw_diff,
        "changes": [c.__dict__ for c in report.changes],
        "categories_touched": report.categories_touched,
    }
