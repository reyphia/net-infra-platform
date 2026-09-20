"""Real interactive terminal over WebSocket.

The browser's WebSocket is bridged directly to a live asyncssh interactive
shell channel on the target device -- every byte sent by the operator is
written to the real SSH stdin, and every byte the device sends back is
forwarded to the browser. There is no simulated/fake terminal output path.
"""
from __future__ import annotations

import asyncio
import logging

import asyncssh
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_audit_service, get_credential_service, get_db
from app.audit.service import AuditService
from app.core.config import get_settings
from app.credentials.service import CredentialService
from app.db.models import Device

logger = logging.getLogger("app.terminal")

router = APIRouter(prefix="/devices/{device_id}/terminal", tags=["terminal"])


@router.websocket("/ws")
async def terminal_ws(
    websocket: WebSocket,
    device_id: str,
    session: AsyncSession = Depends(get_db),
    credentials: CredentialService = Depends(get_credential_service),
    audit: AuditService = Depends(get_audit_service),
) -> None:
    await websocket.accept()

    device = await session.get(Device, device_id)
    if device is None:
        await websocket.send_text(f"\r\n*** No device with id {device_id} ***\r\n")
        await websocket.close(code=4404)
        return

    if not device.default_credential_profile_id:
        await websocket.send_text("\r\n*** No credential profile assigned to this device. ***\r\n")
        await websocket.close(code=4400)
        return
    profile = await credentials.get(device.default_credential_profile_id)
    if profile is None:
        await websocket.send_text("\r\n*** Assigned credential profile no longer exists. ***\r\n")
        await websocket.close(code=4400)
        return
    resolved = credentials.resolve_ssh(profile)
    settings = get_settings()

    known_hosts = None if settings.ssh_allow_insecure_lab_mode else (settings.ssh_known_hosts_path,)
    if settings.ssh_allow_insecure_lab_mode:
        await websocket.send_text(
            "\r\n*** WARNING: SSH_ALLOW_INSECURE_LAB_MODE is enabled -- host key verification is OFF. ***\r\n"
        )
    else:
        from app.core.fsutil import ensure_known_hosts_file

        ensure_known_hosts_file(settings.ssh_known_hosts_path)

    try:
        conn = await asyncio.wait_for(
            asyncssh.connect(
                device.management_ip,
                username=resolved.username,
                password=resolved.password,
                known_hosts=known_hosts,
            ),
            timeout=settings.ssh_connect_timeout_seconds,
        )
    except Exception as exc:  # noqa: BLE001 - surface the real error to the operator's terminal
        await websocket.send_text(f"\r\n*** SSH connection to {device.management_ip} failed: {exc} ***\r\n")
        await audit.record(
            operator="terminal-session", action="terminal.connect", success=False, device_id=device_id,
            protocol="ssh", error=str(exc),
        )
        await websocket.close(code=4502)
        return

    await audit.record(
        operator="terminal-session", action="terminal.connect", success=True, device_id=device_id, protocol="ssh"
    )

    process = await conn.create_process(term_type="xterm", term_size=(120, 32))

    async def _pump_device_to_browser() -> None:
        try:
            while True:
                chunk = await process.stdout.read(4096)
                if not chunk:
                    break
                await websocket.send_text(chunk)
        except (asyncssh.Error, ConnectionError):
            pass

    reader_task = asyncio.create_task(_pump_device_to_browser())

    try:
        while True:
            data = await websocket.receive_text()
            process.stdin.write(data)
    except WebSocketDisconnect:
        pass
    except Exception as exc:  # noqa: BLE001
        logger.warning("Terminal session error for %s: %s", device_id, exc)
    finally:
        reader_task.cancel()
        process.stdin.write_eof()
        process.close()
        conn.close()
        await audit.record(
            operator="terminal-session", action="terminal.disconnect", success=True, device_id=device_id, protocol="ssh"
        )
