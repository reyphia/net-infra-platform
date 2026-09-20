"""Detect known management services via targeted TCP connect probes.

This is NOT a port scanner: it only ever probes a fixed, small set of
well-known management ports (SSH, Telnet, HTTPS, HTTP) required to populate
the management-accessibility model. It never sweeps arbitrary port ranges.
"""
from __future__ import annotations

import asyncio
import contextlib
from dataclasses import dataclass

MANAGEMENT_PORTS: dict[str, int] = {
    "SSH": 22,
    "TELNET": 23,
    "HTTPS": 443,
    "HTTP": 80,
}


@dataclass
class PortProbeResult:
    ip_address: str
    service: str
    port: int
    open: bool
    banner: str | None = None


async def probe_port(ip_address: str, service: str, port: int, timeout_seconds: float = 2.0) -> PortProbeResult:
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(ip_address, port), timeout=timeout_seconds
        )
    except (TimeoutError, OSError, ConnectionRefusedError):
        return PortProbeResult(ip_address=ip_address, service=service, port=port, open=False)

    banner = None
    try:
        if service == "SSH":
            # SSH servers send their identification string immediately on connect.
            try:
                data = await asyncio.wait_for(reader.read(256), timeout=1.5)
                banner = data.decode("utf-8", errors="replace").strip() or None
            except TimeoutError:
                banner = None
    finally:
        writer.close()
        with contextlib.suppress(Exception):
            await writer.wait_closed()

    return PortProbeResult(ip_address=ip_address, service=service, port=port, open=True, banner=banner)


async def probe_management_services(
    ip_address: str, timeout_seconds: float = 2.0
) -> list[PortProbeResult]:
    return await asyncio.gather(
        *(probe_port(ip_address, svc, port, timeout_seconds) for svc, port in MANAGEMENT_PORTS.items())
    )
