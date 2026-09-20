"""Real ICMP echo probing.

Uses the system `ping` binary via subprocess rather than crafting raw ICMP
sockets, because raw sockets require elevated privileges (CAP_NET_RAW/root,
or Administrator on Windows) that a management workstation may not want to
grant this process. This is a real network operation -- an actual ICMP echo
request is sent to the target and we parse the actual reply -- just
implemented without raw sockets.

`ping`'s command-line syntax differs by platform:
  - Linux/macOS (BSD-style): `ping -c <count> -W <timeout_seconds> <host>`
  - Windows: `ping -n <count> -w <timeout_milliseconds> <host>`
Both the argument construction and the reply-line parsing account for this.
"""
from __future__ import annotations

import asyncio
import platform
import re
from dataclasses import dataclass

# Matches both "time=15.2 ms" / "time=15 ms" (Linux) and "time=15ms" /
# "time<1ms" (Windows) reply lines.
_RTT_RE = re.compile(r"time[=<]([\d.]+)\s*ms")


def is_windows() -> bool:
    return platform.system().lower() == "windows"


@dataclass
class PingResult:
    ip_address: str
    reachable: bool
    rtt_ms: float | None
    error: str | None = None


def _build_ping_args(ip_address: str, timeout_seconds: float, count: int) -> list[str]:
    if is_windows():
        timeout_ms = max(1, int(timeout_seconds * 1000))
        return ["ping", "-n", str(count), "-w", str(timeout_ms), ip_address]
    return ["ping", "-c", str(count), "-W", str(max(1, int(timeout_seconds))), ip_address]


async def ping(ip_address: str, timeout_seconds: float = 2.0, count: int = 1) -> PingResult:
    args = _build_ping_args(ip_address, timeout_seconds, count)
    try:
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, _stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout_seconds + 2)
        except TimeoutError:
            proc.kill()
            await proc.wait()
            return PingResult(ip_address=ip_address, reachable=False, rtt_ms=None, error="probe timed out")
    except (FileNotFoundError, NotImplementedError):
        return PingResult(ip_address=ip_address, reachable=False, rtt_ms=None, error="`ping` binary not found on host")

    output = stdout.decode("utf-8", errors="replace")

    # Windows `ping` can return 0 even on partial loss in some edge cases
    # (rare), and always prints "Request timed out." / "Destination host
    # unreachable." per failed probe, so we check both the return code and
    # those markers rather than trusting returncode alone cross-platform.
    windows_failure_markers = ("request timed out", "destination host unreachable", "could not find host")
    if is_windows() and any(marker in output.lower() for marker in windows_failure_markers):
        return PingResult(ip_address=ip_address, reachable=False, rtt_ms=None, error="no reply")
    if proc.returncode != 0:
        return PingResult(ip_address=ip_address, reachable=False, rtt_ms=None, error="no reply")

    match = _RTT_RE.search(output)
    rtt = float(match.group(1)) if match else None
    return PingResult(ip_address=ip_address, reachable=True, rtt_ms=rtt)


async def ping_sweep(
    ip_addresses: list[str], timeout_seconds: float = 2.0, max_concurrency: int = 50
) -> list[PingResult]:
    semaphore = asyncio.Semaphore(max_concurrency)

    async def _bounded(ip: str) -> PingResult:
        async with semaphore:
            return await ping(ip, timeout_seconds=timeout_seconds)

    return await asyncio.gather(*(_bounded(ip) for ip in ip_addresses))
