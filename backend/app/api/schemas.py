from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class DeviceOut(BaseModel):
    id: str
    management_ip: str
    hostname: str | None
    vendor: str | None
    model: str | None
    os_name: str | None
    os_version: str | None
    uptime_seconds: int | None
    device_type: str
    identification_confidence: float
    identification_sources: list[str]
    management_state: str
    available_management_methods: list[str]
    driver_type: str | None
    is_online: bool
    first_seen: datetime
    last_seen: datetime

    model_config = {"from_attributes": True}


class InterfaceOut(BaseModel):
    id: str
    name: str
    description: str | None
    mac_address: str | None
    admin_state: str | None
    oper_state: str | None
    speed_mbps: int | None
    duplex: str | None
    vlan: str | None
    rx_bytes: int | None
    tx_bytes: int | None
    rx_errors: int | None
    tx_errors: int | None

    model_config = {"from_attributes": True}


class DiscoveryJobCreate(BaseModel):
    scope_cidrs: list[str] = Field(..., min_length=1, description="Explicit authorized CIDR ranges, e.g. ['10.10.0.0/16']")
    timeout_seconds: float = 2.0
    max_concurrency: int = 50
    retry_count: int = 1
    snmp_community: str | None = None
    snmp_port: int = 161
    enable_snmp: bool = True
    enable_lldp_cdp: bool = True


class DiscoveryJobOut(BaseModel):
    id: str
    scope_cidrs: list[str]
    status: str
    total_targets: int
    processed_targets: int
    counts_by_type: dict
    started_at: datetime | None
    finished_at: datetime | None
    error: str | None

    model_config = {"from_attributes": True}


class CredentialProfileCreate(BaseModel):
    name: str
    protocol: str  # ssh | snmp
    username: str | None = None
    password: str | None = None
    enable_password: str | None = None
    private_key: str | None = None
    snmp_version: str = "v2c"
    snmp_community: str | None = None


class CredentialProfileOut(BaseModel):
    """Never includes secret material."""

    id: str
    name: str
    protocol: str
    username: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class DeviceCredentialAssign(BaseModel):
    credential_profile_id: str


class TopologyNodeOut(BaseModel):
    id: str
    hostname: str | None
    management_ip: str
    device_type: str
    vendor: str | None
    management_state: str
    is_online: bool


class TopologyEdgeOut(BaseModel):
    id: str
    source: str
    target: str
    source_interface: str | None
    target_interface: str | None
    discovery_methods: list[str]
    confidence: float


class TopologyGraphOut(BaseModel):
    nodes: list[TopologyNodeOut]
    edges: list[TopologyEdgeOut]
    generated_at: str


class ConfigBackupOut(BaseModel):
    id: str
    device_id: str
    source: str
    driver_type: str
    operator: str
    sha256: str
    byte_size: int
    created_at: datetime
    trigger: str

    model_config = {"from_attributes": True}


class ChangePlanCreate(BaseModel):
    name: str
    operator: str
    proposed_config: str
    device_ids: list[str] = Field(..., min_length=1)
    save_after_apply: bool = False


class ChangePlanOut(BaseModel):
    id: str
    name: str
    operator: str
    status: str
    proposed_config: str
    save_after_apply: bool
    validation_report: dict | None
    diff_report: dict | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ChangeApplyRequest(BaseModel):
    confirmed_by: str = Field(..., description="Operator identity re-confirming they reviewed the preview.")


class ChangeExecutionOut(BaseModel):
    id: str
    plan_id: str
    device_id: str
    apply_success: bool | None
    apply_error: str | None
    verified: bool | None
    rollback_status: str

    model_config = {"from_attributes": True}


class AuditEventOut(BaseModel):
    id: str
    timestamp: datetime
    operator: str
    action: str
    device_id: str | None
    protocol: str | None
    detail: str | None
    success: bool
    error: str | None

    model_config = {"from_attributes": True}


class TerminalCommandRequest(BaseModel):
    command: str


class ErrorDetail(BaseModel):
    message: str
    reason: str | None = None
    possible_causes: list[str] = Field(default_factory=list)
