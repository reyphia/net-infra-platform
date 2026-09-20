"""Real LLDP and CDP neighbor discovery via SNMP.

Both LLDP-MIB (vendor-neutral, IEEE 802.1AB) and CISCO-CDP-MIB (Cisco-only,
proprietary but public) are queried. A device may support one, both, or
neither -- callers must treat empty results as "no neighbor data available",
not as "device has no neighbors".
"""
from __future__ import annotations

from dataclasses import dataclass

from app.snmp import oids
from app.snmp.client import SNMPClient, SNMPError


@dataclass
class Neighbor:
    local_if_index: str
    local_port_name: str | None
    remote_chassis_id: str | None
    remote_port_id: str | None
    remote_port_descr: str | None
    remote_system_name: str | None
    remote_management_address: str | None
    source: str  # "LLDP" | "CDP"


async def _local_port_names(client: SNMPClient) -> dict[str, str]:
    """LLDP-MIB indexes remote-neighbor rows by lldpLocPortNum, not ifIndex directly;
    lldpLocPortId gives us a human string (often the ifIndex or an interface alias)."""
    try:
        rows = await client.walk(oids.LLDP_LOC_PORT_ID)
    except SNMPError:
        return {}
    mapping: dict[str, str] = {}
    for row in rows:
        local_port_num = row.oid[len(oids.LLDP_LOC_PORT_ID) + 1 :]
        mapping[local_port_num] = row.value
    return mapping


async def discover_lldp_neighbors(client: SNMPClient) -> list[Neighbor]:
    try:
        chassis = await client.walk(oids.LLDP_REM_CHASSIS_ID)
    except SNMPError:
        return []
    if not chassis:
        return []

    local_ports = await _local_port_names(client)
    port_ids = {r.oid[len(oids.LLDP_REM_PORT_ID) + 1 :]: r.value for r in await client.walk(oids.LLDP_REM_PORT_ID)}
    port_descrs = {
        r.oid[len(oids.LLDP_REM_PORT_DESCR) + 1 :]: r.value for r in await client.walk(oids.LLDP_REM_PORT_DESCR)
    }
    sys_names = {r.oid[len(oids.LLDP_REM_SYS_NAME) + 1 :]: r.value for r in await client.walk(oids.LLDP_REM_SYS_NAME)}
    mgmt_addrs = {
        r.oid[len(oids.LLDP_REM_MGMT_ADDR) + 1 :]: r.value for r in await client.walk(oids.LLDP_REM_MGMT_ADDR)
    }

    neighbors: list[Neighbor] = []
    for row in chassis:
        # lldpRemEntry index is: lldpRemTimeMark.lldpRemLocalPortNum.lldpRemIndex
        suffix_parts = row.oid[len(oids.LLDP_REM_CHASSIS_ID) + 1 :].split(".")
        if len(suffix_parts) < 3:
            continue
        _time_mark, local_port_num, rem_index = suffix_parts[0], suffix_parts[1], suffix_parts[2]
        key = f"{_time_mark}.{local_port_num}.{rem_index}"
        neighbors.append(
            Neighbor(
                local_if_index=local_port_num,
                local_port_name=local_ports.get(local_port_num),
                remote_chassis_id=row.value,
                remote_port_id=port_ids.get(key),
                remote_port_descr=port_descrs.get(key),
                remote_system_name=sys_names.get(key),
                remote_management_address=_extract_mgmt_ip(mgmt_addrs, key),
                source="LLDP",
            )
        )
    return neighbors


def _extract_mgmt_ip(mgmt_addrs: dict[str, str], key_prefix: str) -> str | None:
    for suffix, value in mgmt_addrs.items():
        if suffix.startswith(key_prefix):
            return value
    return None


async def discover_cdp_neighbors(client: SNMPClient) -> list[Neighbor]:
    try:
        device_ids = await client.walk(oids.CDP_CACHE_DEVICE_ID)
    except SNMPError:
        return []
    if not device_ids:
        return []

    ports = {r.oid[len(oids.CDP_CACHE_DEVICE_PORT) + 1 :]: r.value for r in await client.walk(oids.CDP_CACHE_DEVICE_PORT)}
    addresses = {r.oid[len(oids.CDP_CACHE_ADDRESS) + 1 :]: r.value for r in await client.walk(oids.CDP_CACHE_ADDRESS)}

    neighbors: list[Neighbor] = []
    for row in device_ids:
        # cdpCacheEntry index is: cdpCacheIfIndex.cdpCacheDeviceIndex
        suffix = row.oid[len(oids.CDP_CACHE_DEVICE_ID) + 1 :]
        parts = suffix.split(".")
        local_if_index = parts[0] if parts else suffix
        neighbors.append(
            Neighbor(
                local_if_index=local_if_index,
                local_port_name=None,  # requires correlating ifIndex -> ifName from IF-MIB separately
                remote_chassis_id=None,
                remote_port_id=ports.get(suffix),
                remote_port_descr=None,
                remote_system_name=row.value,
                remote_management_address=addresses.get(suffix),
                source="CDP",
            )
        )
    return neighbors
