"""Discovery engine: orchestrates ICMP, ARP correlation, TCP probes, and SNMP
(facts + LLDP/CDP) across a bounded-concurrency pool, and persists real
results as Device / Interface / Connection / DeviceDiscoveryEvent rows.

Nothing here invents a device that wasn't actually observed. A host only
becomes a `Device` row if it responded to at least one probe (ICMP, an open
management TCP port, or SNMP).
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    Connection,
    Device,
    DeviceDiscoveryEvent,
    DeviceType,
    DiscoveryJob,
    DiscoveryJobStatus,
    DiscoverySource,
    ManagementMethod,
    ManagementState,
)
from app.discovery import identification
from app.discovery.arp import ARPEntry, read_arp_table
from app.discovery.icmp import PingResult, ping
from app.discovery.scope import DiscoveryScope
from app.discovery.tcp_probe import probe_management_services
from app.snmp.client import SNMPClient, SNMPCredential, SNMPError
from app.snmp.facts import get_system_facts
from app.snmp.lldp_cdp import discover_cdp_neighbors, discover_lldp_neighbors

logger = logging.getLogger("app.discovery.engine")


@dataclass
class DiscoveryConfig:
    timeout_seconds: float = 2.0
    max_concurrency: int = 50
    retry_count: int = 1
    snmp_community: str | None = None
    snmp_port: int = 161
    enable_snmp: bool = True
    enable_lldp_cdp: bool = True


@dataclass
class HostResult:
    ip_address: str
    ping: PingResult
    open_management_services: list[str] = field(default_factory=list)
    ssh_banner: str | None = None
    snmp_reachable: bool = False
    sys_name: str | None = None
    sys_descr: str | None = None
    sys_object_id: str | None = None
    uptime_seconds: int | None = None
    arp_mac: str | None = None


async def probe_host(ip: str, config: DiscoveryConfig, arp_by_ip: dict[str, ARPEntry]) -> HostResult:
    ping_result = await ping(ip, timeout_seconds=config.timeout_seconds)
    result = HostResult(ip_address=ip, ping=ping_result, arp_mac=arp_by_ip.get(ip, ARPEntry("", "", None, "")).mac_address or None)

    tcp_results = await probe_management_services(ip, timeout_seconds=config.timeout_seconds)
    result.open_management_services = [r.service for r in tcp_results if r.open]
    ssh = next((r for r in tcp_results if r.service == "SSH" and r.open), None)
    if ssh:
        result.ssh_banner = ssh.banner

    if config.enable_snmp and config.snmp_community:
        client = SNMPClient(
            ip,
            SNMPCredential(version="v2c", community=config.snmp_community, port=config.snmp_port),
            timeout=config.timeout_seconds,
            retries=config.retry_count,
        )
        try:
            facts = await get_system_facts(client)
            result.snmp_reachable = True
            result.sys_name = facts.sys_name
            result.sys_descr = facts.sys_descr
            result.sys_object_id = facts.sys_object_id
            result.uptime_seconds = facts.uptime_seconds
        except SNMPError as exc:
            logger.debug("SNMP unreachable for %s: %s", ip, exc)

    return result


async def run_discovery(
    session: AsyncSession,
    job: DiscoveryJob,
    scope: DiscoveryScope,
    config: DiscoveryConfig,
) -> None:
    """Runs a discovery job to completion, updating `job` progress as it goes.
    Caller is responsible for committing `job` state before/after as needed.
    """
    job.status = DiscoveryJobStatus.RUNNING.value
    job.started_at = datetime.utcnow()
    targets = scope.host_addresses()
    job.total_targets = len(targets)
    await session.commit()

    arp_entries = await read_arp_table()
    arp_by_ip = {e.ip_address: e for e in arp_entries}

    semaphore = asyncio.Semaphore(config.max_concurrency)
    results: list[HostResult] = []
    processed = 0
    lock = asyncio.Lock()

    async def _bounded(ip: str) -> None:
        nonlocal processed
        async with semaphore:
            try:
                res = await probe_host(ip, config, arp_by_ip)
            except Exception as exc:  # noqa: BLE001 - a single host failure must not abort the job
                logger.warning("Discovery probe failed for %s: %s", ip, exc)
                res = HostResult(ip_address=ip, ping=PingResult(ip, False, None, str(exc)))
            results.append(res)
        async with lock:
            processed += 1
            job.processed_targets = processed

    try:
        await asyncio.gather(*(_bounded(ip) for ip in targets))
    except asyncio.CancelledError:
        job.status = DiscoveryJobStatus.CANCELLED.value
        job.finished_at = datetime.utcnow()
        await session.commit()
        raise

    counts: dict[str, int] = {t.value: 0 for t in DeviceType}
    for res in results:
        responded = res.ping.reachable or bool(res.open_management_services) or res.snmp_reachable
        if not responded:
            continue
        device_type = await _persist_device(session, job, res, config)
        counts[device_type.value] = counts.get(device_type.value, 0) + 1

    job.counts_by_type = counts
    job.status = DiscoveryJobStatus.COMPLETED.value
    job.finished_at = datetime.utcnow()
    await session.commit()

    if config.enable_lldp_cdp and config.snmp_community:
        await _discover_topology_edges(session, job, config)


async def _persist_device(
    session: AsyncSession, job: DiscoveryJob, res: HostResult, config: DiscoveryConfig
) -> DeviceType:
    existing = (
        await session.execute(select(Device).where(Device.management_ip == res.ip_address))
    ).scalar_one_or_none()

    evidence: list[identification.IdentificationEvidence] = []
    if desc_evidence := identification.identify_from_sys_descr(res.sys_descr):
        evidence.append(desc_evidence)
    if banner_evidence := identification.identify_from_ssh_banner(res.ssh_banner):
        evidence.append(banner_evidence)
    vendor_hint, _ = identification.identify_from_sys_object_id(res.sys_object_id)
    id_result = identification.combine_evidence(evidence)

    management_methods: list[str] = []
    if "SSH" in res.open_management_services:
        management_methods.append(ManagementMethod.SSH.value)
    if "TELNET" in res.open_management_services:
        management_methods.append(ManagementMethod.TELNET.value)
    if "HTTPS" in res.open_management_services:
        management_methods.append(ManagementMethod.HTTPS.value)
    if res.snmp_reachable:
        management_methods.append(ManagementMethod.SNMP.value)
    if not management_methods:
        management_methods.append(ManagementMethod.NONE.value)

    if ManagementMethod.SSH.value in management_methods:
        management_state = ManagementState.REMOTELY_MANAGEABLE.value
    elif res.snmp_reachable:
        management_state = ManagementState.MONITORABLE.value
    elif id_result.device_type != DeviceType.UNKNOWN:
        management_state = ManagementState.IDENTIFIED.value
    else:
        management_state = ManagementState.DISCOVERED.value

    driver_type = None
    if ManagementMethod.SSH.value in management_methods:
        if vendor_hint == "Cisco":
            driver_type = "cisco_ios"
        elif vendor_hint == "MikroTik":
            driver_type = "mikrotik_routeros"
        else:
            driver_type = "generic_ssh"  # best-effort default; operator can override

    now = datetime.utcnow()
    if existing:
        existing.hostname = res.sys_name or existing.hostname
        existing.vendor = vendor_hint or existing.vendor
        existing.sys_descr = res.sys_descr or existing.sys_descr
        existing.sys_object_id = res.sys_object_id or existing.sys_object_id
        existing.uptime_seconds = res.uptime_seconds if res.uptime_seconds is not None else existing.uptime_seconds
        existing.device_type = id_result.device_type.value if id_result.confidence > 0 else existing.device_type
        existing.identification_confidence = max(existing.identification_confidence, id_result.confidence)
        existing.identification_sources = sorted(set(existing.identification_sources) | set(id_result.sources))
        existing.management_state = management_state
        existing.available_management_methods = management_methods
        existing.driver_type = driver_type or existing.driver_type
        existing.is_online = res.ping.reachable
        existing.last_seen = now
        device = existing
    else:
        device = Device(
            management_ip=res.ip_address,
            hostname=res.sys_name,
            vendor=vendor_hint,
            sys_descr=res.sys_descr,
            sys_object_id=res.sys_object_id,
            uptime_seconds=res.uptime_seconds,
            device_type=id_result.device_type.value,
            identification_confidence=id_result.confidence,
            identification_sources=id_result.sources,
            management_state=management_state,
            available_management_methods=management_methods,
            driver_type=driver_type,
            is_online=res.ping.reachable,
            first_seen=now,
            last_seen=now,
        )
        session.add(device)
        await session.flush()

    sources_hit: list[DiscoverySource] = []
    if res.ping.reachable:
        sources_hit.append(DiscoverySource.ICMP)
    if res.arp_mac:
        sources_hit.append(DiscoverySource.ARP)
    if res.snmp_reachable:
        sources_hit.append(DiscoverySource.SNMP)
    for source in sources_hit:
        session.add(
            DeviceDiscoveryEvent(
                device_id=device.id,
                source=source.value,
                detail=None,
                discovery_job_id=job.id,
                observed_at=now,
            )
        )

    await session.commit()
    return DeviceType(device.device_type)


async def _discover_topology_edges(session: AsyncSession, job: DiscoveryJob, config: DiscoveryConfig) -> None:
    """For every SNMP-reachable device found in this job, query LLDP/CDP and
    merge neighbor relationships into `connections`, matching remote peers by
    management IP or system name against devices already in the database.
    """
    devices = (await session.execute(select(Device))).scalars().all()
    by_ip = {d.management_ip: d for d in devices}
    by_name = {d.hostname: d for d in devices if d.hostname}

    for device in devices:
        if ManagementMethod.SNMP.value not in device.available_management_methods:
            continue
        client = SNMPClient(
            device.management_ip,
            SNMPCredential(version="v2c", community=config.snmp_community, port=config.snmp_port),
            timeout=config.timeout_seconds,
            retries=config.retry_count,
        )
        try:
            lldp_neighbors = await discover_lldp_neighbors(client)
        except SNMPError:
            lldp_neighbors = []
        try:
            cdp_neighbors = await discover_cdp_neighbors(client)
        except SNMPError:
            cdp_neighbors = []

        for neighbor in [*lldp_neighbors, *cdp_neighbors]:
            peer = None
            if neighbor.remote_management_address:
                peer = by_ip.get(neighbor.remote_management_address)
            if peer is None and neighbor.remote_system_name:
                peer = by_name.get(neighbor.remote_system_name)
            if peer is None or peer.id == device.id:
                continue  # neighbor not (yet) a known device in this job's discovery scope

            confidence = 0.98 if neighbor.source == "LLDP" else 0.9
            await _merge_connection(
                session,
                source_device_id=device.id,
                source_interface=neighbor.local_port_name,
                dest_device_id=peer.id,
                dest_interface=neighbor.remote_port_id,
                method=neighbor.source,
                confidence=confidence,
            )
    await session.commit()


async def _merge_connection(
    session: AsyncSession,
    *,
    source_device_id: str,
    source_interface: str | None,
    dest_device_id: str,
    dest_interface: str | None,
    method: str,
    confidence: float,
) -> None:
    """Merge into an existing edge (in either direction) rather than duplicating it."""
    existing = (
        await session.execute(
            select(Connection).where(
                (
                    (Connection.source_device_id == source_device_id)
                    & (Connection.destination_device_id == dest_device_id)
                )
                | (
                    (Connection.source_device_id == dest_device_id)
                    & (Connection.destination_device_id == source_device_id)
                )
            )
        )
    ).scalars().first()

    now = datetime.utcnow()
    if existing:
        if method not in existing.discovery_methods:
            existing.discovery_methods = [*existing.discovery_methods, method]
        existing.confidence = max(existing.confidence, confidence)
        existing.last_observed = now
        return

    session.add(
        Connection(
            source_device_id=source_device_id,
            source_interface_name=source_interface,
            destination_device_id=dest_device_id,
            destination_interface_name=dest_interface,
            discovery_methods=[method],
            confidence=confidence,
            first_observed=now,
            last_observed=now,
        )
    )
