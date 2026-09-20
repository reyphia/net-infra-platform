"""Gather system facts, interfaces, and health metrics over SNMP.

Every function here talks to a real device via `SNMPClient`. If a MIB is
unsupported the underlying OID simply won't resolve (`get()` returns None /
`walk()` returns []); callers must not fabricate values for missing data.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.snmp import oids
from app.snmp.client import SNMPClient, SNMPError

_IF_ADMIN_STATUS = {"1": "up", "2": "down", "3": "testing"}
_IF_OPER_STATUS = {"1": "up", "2": "down", "3": "testing", "4": "unknown", "5": "dormant", "6": "notPresent"}


@dataclass
class SystemFacts:
    sys_name: str | None = None
    sys_descr: str | None = None
    sys_object_id: str | None = None
    uptime_ticks: int | None = None  # centiseconds, per RFC 1213

    @property
    def uptime_seconds(self) -> int | None:
        return int(self.uptime_ticks / 100) if self.uptime_ticks is not None else None


@dataclass
class InterfaceFacts:
    if_index: str
    name: str | None = None
    description: str | None = None
    mac_address: str | None = None
    admin_state: str | None = None
    oper_state: str | None = None
    speed_mbps: int | None = None
    in_octets: int | None = None
    out_octets: int | None = None
    in_errors: int | None = None
    out_errors: int | None = None
    in_discards: int | None = None
    out_discards: int | None = None


@dataclass
class HealthFacts:
    cpu_percent: float | None = None
    memory_percent: float | None = None


async def get_system_facts(client: SNMPClient) -> SystemFacts:
    facts = SystemFacts()
    try:
        if r := await client.get(oids.SYS_NAME):
            facts.sys_name = r.value
        if r := await client.get(oids.SYS_DESCR):
            facts.sys_descr = r.value
        if r := await client.get(oids.SYS_OBJECT_ID):
            facts.sys_object_id = r.value
        if r := await client.get(oids.SYS_UPTIME):
            facts.uptime_ticks = int(r.value)
    except SNMPError:
        raise
    return facts


def _mac_from_snmp_octets(raw: str) -> str | None:
    """pysnmp OctetString.prettyPrint() for a MAC returns a hex string like '0x0011223344ff'."""
    cleaned = raw.lower().replace("0x", "")
    if len(cleaned) != 12:
        return None
    return ":".join(cleaned[i : i + 2] for i in range(0, 12, 2))


async def get_interfaces(client: SNMPClient) -> list[InterfaceFacts]:
    columns = {
        "descr": oids.IF_DESCR,
        "name": oids.IF_NAME,
        "phys_address": oids.IF_PHYS_ADDRESS,
        "admin_status": oids.IF_ADMIN_STATUS,
        "oper_status": oids.IF_OPER_STATUS,
        "high_speed": oids.IF_HIGH_SPEED,
        "in_octets": oids.IF_IN_OCTETS,
        "out_octets": oids.IF_OUT_OCTETS,
        "in_errors": oids.IF_IN_ERRORS,
        "out_errors": oids.IF_OUT_ERRORS,
        "in_discards": oids.IF_IN_DISCARDS,
        "out_discards": oids.IF_OUT_DISCARDS,
    }
    table = await client.walk_table(columns)
    interfaces: list[InterfaceFacts] = []
    for if_index, row in sorted(table.items(), key=lambda kv: int(kv[0]) if kv[0].isdigit() else 0):
        interfaces.append(
            InterfaceFacts(
                if_index=if_index,
                name=row.get("name") or row.get("descr"),
                description=row.get("descr"),
                mac_address=_mac_from_snmp_octets(row["phys_address"]) if row.get("phys_address") else None,
                admin_state=_IF_ADMIN_STATUS.get(row.get("admin_status", "")),
                oper_state=_IF_OPER_STATUS.get(row.get("oper_status", "")),
                speed_mbps=int(row["high_speed"]) if row.get("high_speed", "").isdigit() else None,
                in_octets=int(row["in_octets"]) if row.get("in_octets", "").isdigit() else None,
                out_octets=int(row["out_octets"]) if row.get("out_octets", "").isdigit() else None,
                in_errors=int(row["in_errors"]) if row.get("in_errors", "").isdigit() else None,
                out_errors=int(row["out_errors"]) if row.get("out_errors", "").isdigit() else None,
                in_discards=int(row["in_discards"]) if row.get("in_discards", "").isdigit() else None,
                out_discards=int(row["out_discards"]) if row.get("out_discards", "").isdigit() else None,
            )
        )
    return interfaces


async def get_health(client: SNMPClient) -> HealthFacts:
    """Best-effort CPU/memory via HOST-RESOURCES-MIB and Cisco's CPU MIB.

    Returns None fields (never fabricated numbers) when the agent doesn't
    expose these objects — which is common on many switches/routers.
    """
    health = HealthFacts()
    try:
        cisco_cpu = await client.get(oids.CISCO_CPU_5MIN)
        if cisco_cpu and cisco_cpu.value.isdigit():
            health.cpu_percent = float(cisco_cpu.value)
        else:
            loads = await client.walk(oids.HR_PROCESSOR_LOAD, max_rows=32)
            numeric = [float(r.value) for r in loads if r.value.lstrip("-").isdigit()]
            if numeric:
                health.cpu_percent = sum(numeric) / len(numeric)
    except SNMPError:
        pass  # leave as None -- unavailable, not zero

    try:
        descrs = await client.walk(oids.HR_STORAGE_DESCR, max_rows=64)
        ram_row = next((r for r in descrs if "ram" in r.value.lower() or "physical memory" in r.value.lower()), None)
        if ram_row:
            suffix = ram_row.oid[len(oids.HR_STORAGE_DESCR) + 1 :]
            size = await client.get(f"{oids.HR_STORAGE_SIZE}.{suffix}")
            used = await client.get(f"{oids.HR_STORAGE_USED}.{suffix}")
            if size and used and size.value.isdigit() and used.value.isdigit() and int(size.value) > 0:
                health.memory_percent = round(100.0 * int(used.value) / int(size.value), 1)
    except SNMPError:
        pass

    return health
