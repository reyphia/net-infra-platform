"""Layer 2 / local discovery: read the host's real ARP (IPv4 neighbor) table.

This reads the operating system's actual neighbor cache -- it does not send
gratuitous ARP floods or spoof anything. It only reveals hosts the
management workstation has already resolved on its local L2 segment(s); it
is complementary to, not a replacement for, ICMP/SNMP/LLDP discovery of
remote segments.

Platform behavior:
  - Linux: `ip neighbor show` (iproute2), falling back to `/proc/net/arp`.
  - Windows: `arp -a`, which is the only portable option (there is no
    Windows equivalent of `/proc/net/arp`, and `Get-NetNeighbor` is
    PowerShell-only and not guaranteed present on older Windows/Server
    Core installs, so the `arp` console tool -- present since Windows XP --
    is the most broadly compatible choice).
  - Any other OS: returns [] rather than guessing at a command that may not
    exist; ARP-based discovery is simply skipped, and ICMP/SNMP/LLDP
    discovery still work normally.
"""
from __future__ import annotations

import asyncio
import platform
import re
from dataclasses import dataclass


@dataclass
class ARPEntry:
    ip_address: str
    mac_address: str
    interface: str | None
    state: str  # REACHABLE, STALE, PERMANENT, FAILED, DYNAMIC, STATIC, ... (varies by OS)


_IP_NEIGH_LINE = re.compile(
    r"^(?P<ip>[0-9a-fA-F:.]+)\s+dev\s+(?P<dev>\S+)\s+lladdr\s+(?P<mac>[0-9a-fA-F:]+)\s+(?P<state>\S+)"
)
_PROC_NET_ARP_LINE = re.compile(
    r"^(?P<ip>\S+)\s+0x\S+\s+0x(?P<flags>\S+)\s+(?P<mac>\S+)\s+\S+\s+(?P<dev>\S+)"
)
# Windows `arp -a` data row, e.g.:
#   192.168.1.1           00-11-22-33-44-55     dynamic
_WINDOWS_ARP_LINE = re.compile(
    r"^\s*(?P<ip>\d{1,3}(?:\.\d{1,3}){3})\s+(?P<mac>[0-9a-fA-F]{2}(?:-[0-9a-fA-F]{2}){5})\s+(?P<type>\S+)"
)
# Windows `arp -a` interface header, e.g.:
#   Interface: 192.168.1.5 --- 0x3
_WINDOWS_INTERFACE_HEADER = re.compile(r"^Interface:\s*(?P<iface_ip>\S+)\s*---\s*(?P<iface_id>\S+)")


def is_windows() -> bool:
    return platform.system().lower() == "windows"


async def read_arp_table() -> list[ARPEntry]:
    """Read the real OS neighbor table. Returns [] (never fake entries) on failure."""
    if is_windows():
        return await _read_via_windows_arp()
    entries = await _read_via_ip_command()
    if entries:
        return entries
    return await _read_via_proc_net_arp()


async def _run(*args: str, timeout: float = 5.0) -> str | None:
    try:
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except (FileNotFoundError, TimeoutError, NotImplementedError):
        # NotImplementedError can be raised by asyncio subprocess creation on
        # Windows under the wrong event loop policy; callers on Windows
        # should be running under ProactorEventLoop (the default since
        # Python 3.8), but we fail closed rather than crash discovery.
        return None
    return stdout.decode("utf-8", errors="replace")


async def _read_via_ip_command() -> list[ARPEntry]:
    output = await _run("ip", "neighbor", "show")
    if output is None:
        return []

    entries: list[ARPEntry] = []
    for line in output.splitlines():
        m = _IP_NEIGH_LINE.match(line.strip())
        if not m:
            continue
        entries.append(
            ARPEntry(
                ip_address=m.group("ip"),
                mac_address=m.group("mac").lower(),
                interface=m.group("dev"),
                state=m.group("state").upper(),
            )
        )
    return entries


async def _read_via_proc_net_arp() -> list[ARPEntry]:
    def _read_lines() -> list[str]:
        with open("/proc/net/arp") as fh:
            return fh.readlines()[1:]  # skip header

    try:
        lines = await asyncio.to_thread(_read_lines)
    except OSError:
        return []

    entries: list[ARPEntry] = []
    for line in lines:
        m = _PROC_NET_ARP_LINE.match(line.strip())
        if not m or m.group("mac") == "00:00:00:00:00:00":
            continue
        entries.append(
            ARPEntry(
                ip_address=m.group("ip"),
                mac_address=m.group("mac").lower(),
                interface=m.group("dev"),
                state="COMPLETE" if int(m.group("flags"), 16) & 0x2 else "INCOMPLETE",
            )
        )
    return entries


async def _read_via_windows_arp() -> list[ARPEntry]:
    output = await _run("arp", "-a")
    if output is None:
        return []
    return parse_windows_arp_output(output)


def parse_windows_arp_output(output: str) -> list[ARPEntry]:
    """Pure parsing function, split out from the subprocess call so it can be
    unit-tested on any OS with a captured `arp -a` transcript -- no actual
    Windows machine required to test the parsing logic itself."""
    entries: list[ARPEntry] = []
    current_interface: str | None = None

    for raw_line in output.splitlines():
        line = raw_line.rstrip()
        if not line.strip():
            continue

        header = _WINDOWS_INTERFACE_HEADER.match(line.strip())
        if header:
            current_interface = header.group("iface_ip")
            continue

        m = _WINDOWS_ARP_LINE.match(line)
        if not m:
            continue  # skip the "Internet Address / Physical Address / Type" column header row

        mac = m.group("mac").lower().replace("-", ":")
        if mac in ("ff:ff:ff:ff:ff:ff", "00:00:00:00:00:00"):
            continue  # broadcast / incomplete entries aren't useful discovery signal

        entries.append(
            ARPEntry(
                ip_address=m.group("ip"),
                mac_address=mac,
                interface=current_interface,
                state=m.group("type").upper(),
            )
        )
    return entries
