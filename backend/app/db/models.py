"""ORM models.

These map directly onto the data model described in docs/architecture.md.
Enums are stored as plain strings (SQLite-friendly, Postgres-compatible)
rather than native DB enum types, and validated at the Pydantic schema layer.
"""
from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.utcnow()


# --------------------------------------------------------------------------
# Enums (plain str for storage portability)
# --------------------------------------------------------------------------
class DeviceType(str, enum.Enum):
    ROUTER = "ROUTER"
    SWITCH = "SWITCH"
    FIREWALL = "FIREWALL"
    ACCESS_POINT = "ACCESS_POINT"
    SERVER = "SERVER"
    HOST = "HOST"
    UNKNOWN = "UNKNOWN"


class ManagementState(str, enum.Enum):
    DISCOVERED = "DISCOVERED"
    IDENTIFIED = "IDENTIFIED"
    MONITORABLE = "MONITORABLE"
    REMOTELY_MANAGEABLE = "REMOTELY_MANAGEABLE"
    CONFIGURABLE = "CONFIGURABLE"


class ManagementMethod(str, enum.Enum):
    SSH = "SSH"
    TELNET = "TELNET"
    SNMP = "SNMP"
    HTTPS = "HTTPS"
    REST_API = "REST_API"
    VENDOR_API = "VENDOR_API"
    CONSOLE = "CONSOLE"
    CONSOLE_SERVER = "CONSOLE_SERVER"
    NONE = "NONE"


class DriverType(str, enum.Enum):
    CISCO_IOS = "cisco_ios"
    MIKROTIK_ROUTEROS = "mikrotik_routeros"
    GENERIC_SSH = "generic_ssh"
    UNSUPPORTED = "unsupported"


class DiscoverySource(str, enum.Enum):
    ARP = "ARP"
    ICMP = "ICMP"
    SNMP = "SNMP"
    LLDP = "LLDP"
    CDP = "CDP"
    MAC_TABLE = "MAC_TABLE"
    ROUTING_TABLE = "ROUTING_TABLE"
    INFERENCE = "INFERENCE"
    MANUAL = "MANUAL"


class DiscoveryJobStatus(str, enum.Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"


class ChangePlanStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    VALIDATED = "VALIDATED"
    VALIDATION_FAILED = "VALIDATION_FAILED"
    PREVIEWED = "PREVIEWED"
    CONFIRMED = "CONFIRMED"
    APPLYING = "APPLYING"
    APPLIED = "APPLIED"
    APPLY_FAILED = "APPLY_FAILED"
    VERIFIED = "VERIFIED"
    VERIFY_FAILED = "VERIFY_FAILED"
    ROLLED_BACK = "ROLLED_BACK"
    ROLLBACK_FAILED = "ROLLBACK_FAILED"


class RollbackStatus(str, enum.Enum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    PARTIAL = "PARTIAL"
    UNAVAILABLE = "UNAVAILABLE"
    NOT_ATTEMPTED = "NOT_ATTEMPTED"


# --------------------------------------------------------------------------
# Core inventory
# --------------------------------------------------------------------------
class Device(Base):
    __tablename__ = "devices"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)

    management_ip: Mapped[str] = mapped_column(String(64), index=True)
    hostname: Mapped[str | None] = mapped_column(String(255), nullable=True)

    vendor: Mapped[str | None] = mapped_column(String(128), nullable=True)
    model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    os_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    os_version: Mapped[str | None] = mapped_column(String(128), nullable=True)
    uptime_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)

    device_type: Mapped[str] = mapped_column(String(32), default=DeviceType.UNKNOWN.value)
    identification_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    identification_sources: Mapped[list[str]] = mapped_column(JSON, default=list)

    management_state: Mapped[str] = mapped_column(String(32), default=ManagementState.DISCOVERED.value)
    available_management_methods: Mapped[list[str]] = mapped_column(JSON, default=list)
    driver_type: Mapped[str | None] = mapped_column(String(32), nullable=True)

    sys_object_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    sys_descr: Mapped[str | None] = mapped_column(Text, nullable=True)

    default_credential_profile_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("credential_profiles.id"), nullable=True
    )

    is_online: Mapped[bool] = mapped_column(default=False)
    first_seen: Mapped[datetime] = mapped_column(DateTime, default=_now)
    last_seen: Mapped[datetime] = mapped_column(DateTime, default=_now)

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    interfaces: Mapped[list[Interface]] = relationship(back_populates="device", cascade="all, delete-orphan")
    discovery_events: Mapped[list[DeviceDiscoveryEvent]] = relationship(
        back_populates="device", cascade="all, delete-orphan"
    )

    __table_args__ = (UniqueConstraint("management_ip", name="uq_device_management_ip"),)


class DeviceDiscoveryEvent(Base):
    """Records which discovery mechanism(s) found/confirmed this device, and when."""

    __tablename__ = "device_discovery_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    device_id: Mapped[str] = mapped_column(String(36), ForeignKey("devices.id"), index=True)
    source: Mapped[str] = mapped_column(String(32))
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    discovery_job_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("discovery_jobs.id"), nullable=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    device: Mapped[Device] = relationship(back_populates="discovery_events")


class Interface(Base):
    __tablename__ = "interfaces"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    device_id: Mapped[str] = mapped_column(String(36), ForeignKey("devices.id"), index=True)

    name: Mapped[str] = mapped_column(String(128))
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    mac_address: Mapped[str | None] = mapped_column(String(32), nullable=True)

    admin_state: Mapped[str | None] = mapped_column(String(16), nullable=True)  # up|down|unknown
    oper_state: Mapped[str | None] = mapped_column(String(16), nullable=True)

    speed_mbps: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duplex: Mapped[str | None] = mapped_column(String(16), nullable=True)

    vlan: Mapped[str | None] = mapped_column(String(32), nullable=True)  # access vlan id or "trunk"

    rx_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tx_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rx_errors: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tx_errors: Mapped[int | None] = mapped_column(Integer, nullable=True)
    in_discards: Mapped[int | None] = mapped_column(Integer, nullable=True)
    out_discards: Mapped[int | None] = mapped_column(Integer, nullable=True)

    if_index: Mapped[int | None] = mapped_column(Integer, nullable=True)  # SNMP ifIndex, used for correlation
    last_polled: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    device: Mapped[Device] = relationship(back_populates="interfaces")
    ip_addresses: Mapped[list[IPAddress]] = relationship(back_populates="interface", cascade="all, delete-orphan")

    __table_args__ = (UniqueConstraint("device_id", "name", name="uq_interface_device_name"),)


class IPAddress(Base):
    __tablename__ = "ip_addresses"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    interface_id: Mapped[str] = mapped_column(String(36), ForeignKey("interfaces.id"), index=True)
    address: Mapped[str] = mapped_column(String(64))
    prefix_length: Mapped[int | None] = mapped_column(Integer, nullable=True)
    family: Mapped[str] = mapped_column(String(8), default="ipv4")  # ipv4 | ipv6

    interface: Mapped[Interface] = relationship(back_populates="ip_addresses")


class VLAN(Base):
    __tablename__ = "vlans"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    device_id: Mapped[str] = mapped_column(String(36), ForeignKey("devices.id"), index=True)
    vlan_id: Mapped[int] = mapped_column(Integer)
    name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[str | None] = mapped_column(String(32), nullable=True)

    __table_args__ = (UniqueConstraint("device_id", "vlan_id", name="uq_vlan_device_vlanid"),)


class Route(Base):
    __tablename__ = "routes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    device_id: Mapped[str] = mapped_column(String(36), ForeignKey("devices.id"), index=True)
    destination: Mapped[str] = mapped_column(String(64))
    prefix_length: Mapped[int] = mapped_column(Integer)
    next_hop: Mapped[str | None] = mapped_column(String(64), nullable=True)
    interface_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    protocol: Mapped[str | None] = mapped_column(String(32), nullable=True)  # connected|static|ospf|bgp|...
    metric: Mapped[int | None] = mapped_column(Integer, nullable=True)


class Connection(Base):
    """A topology edge between two devices, derived from real discovery evidence."""

    __tablename__ = "connections"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)

    source_device_id: Mapped[str] = mapped_column(String(36), ForeignKey("devices.id"), index=True)
    source_interface_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    destination_device_id: Mapped[str] = mapped_column(String(36), ForeignKey("devices.id"), index=True)
    destination_interface_name: Mapped[str | None] = mapped_column(String(128), nullable=True)

    discovery_methods: Mapped[list[str]] = mapped_column(JSON, default=list)  # merged sources
    confidence: Mapped[float] = mapped_column(Float, default=0.0)

    first_observed: Mapped[datetime] = mapped_column(DateTime, default=_now)
    last_observed: Mapped[datetime] = mapped_column(DateTime, default=_now)

    __table_args__ = (
        Index("ix_connection_pair", "source_device_id", "destination_device_id"),
    )


# --------------------------------------------------------------------------
# Credentials
# --------------------------------------------------------------------------
class CredentialProfile(Base):
    """Stores encrypted credentials. Secret fields are never returned by the API."""

    __tablename__ = "credential_profiles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(128), unique=True)
    protocol: Mapped[str] = mapped_column(String(16))  # ssh | snmp
    username: Mapped[str | None] = mapped_column(String(128), nullable=True)

    # Fernet-encrypted blobs (never plaintext at rest). NULL when not applicable.
    encrypted_password: Mapped[bytes | None] = mapped_column(nullable=True)
    encrypted_enable_password: Mapped[bytes | None] = mapped_column(nullable=True)
    encrypted_ssh_private_key: Mapped[bytes | None] = mapped_column(nullable=True)
    encrypted_snmp_community: Mapped[bytes | None] = mapped_column(nullable=True)

    snmp_version: Mapped[str | None] = mapped_column(String(8), nullable=True)  # v2c | v3
    snmp_v3_auth_protocol: Mapped[str | None] = mapped_column(String(16), nullable=True)
    snmp_v3_priv_protocol: Mapped[str | None] = mapped_column(String(16), nullable=True)
    encrypted_snmp_v3_auth_key: Mapped[bytes | None] = mapped_column(nullable=True)
    encrypted_snmp_v3_priv_key: Mapped[bytes | None] = mapped_column(nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)


# --------------------------------------------------------------------------
# Configuration management
# --------------------------------------------------------------------------
class ConfigurationBackup(Base):
    __tablename__ = "configuration_backups"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    device_id: Mapped[str] = mapped_column(String(36), ForeignKey("devices.id"), index=True)

    source: Mapped[str] = mapped_column(String(16))  # running | startup
    driver_type: Mapped[str] = mapped_column(String(32))
    operator: Mapped[str] = mapped_column(String(128))

    file_path: Mapped[str] = mapped_column(String(512))  # sanitized-for-display copy lives alongside
    sha256: Mapped[str] = mapped_column(String(64))
    byte_size: Mapped[int] = mapped_column(Integer)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    trigger: Mapped[str] = mapped_column(String(32), default="manual")  # manual | pre_change | scheduled


# --------------------------------------------------------------------------
# Change management
# --------------------------------------------------------------------------
class ChangePlan(Base):
    __tablename__ = "change_plans"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(255))
    operator: Mapped[str] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(32), default=ChangePlanStatus.DRAFT.value)

    proposed_config: Mapped[str] = mapped_column(Text)  # raw config lines/commands to apply
    save_after_apply: Mapped[bool] = mapped_column(default=False)

    validation_report: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    diff_report: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    pre_change_backup_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("configuration_backups.id"), nullable=True
    )
    post_change_backup_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("configuration_backups.id"), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)

    executions: Mapped[list[ChangeExecution]] = relationship(back_populates="plan", cascade="all, delete-orphan")


class ChangePlanDevice(Base):
    """Join table: which devices are targeted by a (possibly batch) change plan."""

    __tablename__ = "change_plan_devices"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    plan_id: Mapped[str] = mapped_column(String(36), ForeignKey("change_plans.id"), index=True)
    device_id: Mapped[str] = mapped_column(String(36), ForeignKey("devices.id"), index=True)
    eligible: Mapped[bool] = mapped_column(default=True)
    ineligibility_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)

    __table_args__ = (UniqueConstraint("plan_id", "device_id", name="uq_plan_device"),)


class ChangeExecution(Base):
    """One per-device execution attempt (apply -> verify -> optional rollback) for a plan."""

    __tablename__ = "change_executions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    plan_id: Mapped[str] = mapped_column(String(36), ForeignKey("change_plans.id"), index=True)
    device_id: Mapped[str] = mapped_column(String(36), ForeignKey("devices.id"), index=True)

    apply_started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    apply_finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    apply_success: Mapped[bool | None] = mapped_column(nullable=True)
    apply_output: Mapped[str | None] = mapped_column(Text, nullable=True)
    apply_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    verified: Mapped[bool | None] = mapped_column(nullable=True)
    verification_detail: Mapped[str | None] = mapped_column(Text, nullable=True)

    rollback_status: Mapped[str] = mapped_column(String(32), default=RollbackStatus.NOT_ATTEMPTED.value)
    rollback_detail: Mapped[str | None] = mapped_column(Text, nullable=True)

    plan: Mapped[ChangePlan] = relationship(back_populates="executions")


# --------------------------------------------------------------------------
# Discovery jobs
# --------------------------------------------------------------------------
class DiscoveryJob(Base):
    __tablename__ = "discovery_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    scope_cidrs: Mapped[list[str]] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(16), default=DiscoveryJobStatus.PENDING.value)

    config: Mapped[dict] = mapped_column(JSON)  # timeout, concurrency, retries, snmp settings (no secrets)

    total_targets: Mapped[int] = mapped_column(Integer, default=0)
    processed_targets: Mapped[int] = mapped_column(Integer, default=0)

    counts_by_type: Mapped[dict] = mapped_column(JSON, default=dict)

    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


# --------------------------------------------------------------------------
# Monitoring
# --------------------------------------------------------------------------
class HealthSnapshot(Base):
    __tablename__ = "health_snapshots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    device_id: Mapped[str] = mapped_column(String(36), ForeignKey("devices.id"), index=True)

    is_online: Mapped[bool] = mapped_column()
    cpu_percent: Mapped[float | None] = mapped_column(Float, nullable=True)  # None == unavailable, never fabricated
    memory_percent: Mapped[float | None] = mapped_column(Float, nullable=True)
    temperature_celsius: Mapped[float | None] = mapped_column(Float, nullable=True)
    uptime_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)

    icmp_rtt_ms: Mapped[float | None] = mapped_column(Float, nullable=True)

    collected_at: Mapped[datetime] = mapped_column(DateTime, default=_now, index=True)


# --------------------------------------------------------------------------
# Audit
# --------------------------------------------------------------------------
class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=_now, index=True)

    operator: Mapped[str] = mapped_column(String(128))
    action: Mapped[str] = mapped_column(String(64), index=True)  # e.g. "ssh.connect", "config.backup"
    device_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("devices.id"), nullable=True)

    protocol: Mapped[str | None] = mapped_column(String(16), nullable=True)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)  # redacted, never contains secrets
    success: Mapped[bool] = mapped_column()
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    source_session_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
