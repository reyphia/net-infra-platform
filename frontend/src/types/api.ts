// Mirrors backend/app/api/schemas.py. Kept hand-in-sync rather than
// generated, since the project has no codegen step yet (see docs/roadmap in
// the README for "generate from OpenAPI" as a future improvement).

export type DeviceType =
  | "ROUTER"
  | "SWITCH"
  | "FIREWALL"
  | "ACCESS_POINT"
  | "SERVER"
  | "HOST"
  | "UNKNOWN";

export type ManagementState =
  | "DISCOVERED"
  | "IDENTIFIED"
  | "MONITORABLE"
  | "REMOTELY_MANAGEABLE"
  | "CONFIGURABLE";

export type ManagementMethod =
  | "SSH"
  | "TELNET"
  | "SNMP"
  | "HTTPS"
  | "REST_API"
  | "VENDOR_API"
  | "CONSOLE"
  | "CONSOLE_SERVER"
  | "NONE";

export interface Device {
  id: string;
  management_ip: string;
  hostname: string | null;
  vendor: string | null;
  model: string | null;
  os_name: string | null;
  os_version: string | null;
  uptime_seconds: number | null;
  device_type: DeviceType;
  identification_confidence: number;
  identification_sources: string[];
  management_state: ManagementState;
  available_management_methods: ManagementMethod[];
  driver_type: string | null;
  is_online: boolean;
  first_seen: string;
  last_seen: string;
}

export interface InterfaceOut {
  id: string;
  name: string;
  description: string | null;
  mac_address: string | null;
  admin_state: string | null;
  oper_state: string | null;
  speed_mbps: number | null;
  duplex: string | null;
  vlan: string | null;
  rx_bytes: number | null;
  tx_bytes: number | null;
  rx_errors: number | null;
  tx_errors: number | null;
}

export interface DiscoveryJob {
  id: string;
  scope_cidrs: string[];
  status: "PENDING" | "RUNNING" | "COMPLETED" | "CANCELLED" | "FAILED";
  total_targets: number;
  processed_targets: number;
  counts_by_type: Record<string, number>;
  started_at: string | null;
  finished_at: string | null;
  error: string | null;
}

export interface CredentialProfile {
  id: string;
  name: string;
  protocol: "ssh" | "snmp";
  username: string | null;
  created_at: string;
}

export interface TopologyNode {
  id: string;
  hostname: string | null;
  management_ip: string;
  device_type: DeviceType;
  vendor: string | null;
  management_state: ManagementState;
  is_online: boolean;
}

export interface TopologyEdge {
  id: string;
  source: string;
  target: string;
  source_interface: string | null;
  target_interface: string | null;
  discovery_methods: string[];
  confidence: number;
}

export interface TopologyGraph {
  nodes: TopologyNode[];
  edges: TopologyEdge[];
  generated_at: string;
}

export interface ConfigBackup {
  id: string;
  device_id: string;
  source: string;
  driver_type: string;
  operator: string;
  sha256: string;
  byte_size: number;
  created_at: string;
  trigger: string;
}

export interface ChangePlan {
  id: string;
  name: string;
  operator: string;
  status: string;
  proposed_config: string;
  save_after_apply: boolean;
  validation_report: {
    summary: { total: number; eligible: number; ineligible: number };
    per_device: Record<string, { ok: boolean; issues: ValidationIssue[] }>;
  } | null;
  diff_report: Record<string, DevicePreviewDiff> | null;
  created_at: string;
  updated_at: string;
}

export interface ValidationIssue {
  severity: "blocking" | "warning";
  line: string;
  message: string;
}

export interface DevicePreviewDiff {
  predicted: boolean;
  note: string;
  raw_diff: string;
  changes: SemanticChange[];
  categories_touched: string[];
}

export interface SemanticChange {
  category: string;
  entity: string;
  change_type: "added" | "removed" | "modified";
  added_lines: string[];
  removed_lines: string[];
}

export interface ChangePlanDeviceRow {
  device_id: string;
  hostname: string | null;
  management_ip: string;
  eligible: boolean;
  ineligibility_reason: string | null;
}

export interface ChangeExecutionRow {
  id: string;
  device_id: string;
  apply_success: boolean | null;
  apply_error: string | null;
  verified: boolean | null;
  rollback_status: string;
  rollback_detail: string | null;
}

export interface AuditEvent {
  id: string;
  timestamp: string;
  operator: string;
  action: string;
  device_id: string | null;
  protocol: string | null;
  detail: string | null;
  success: boolean;
  error: string | null;
}

export interface HealthSnapshotOut {
  available: boolean;
  is_online?: boolean;
  cpu_percent?: number | null;
  memory_percent?: number | null;
  temperature_celsius?: number | null;
  icmp_rtt_ms?: number | null;
  collected_at?: string;
}
