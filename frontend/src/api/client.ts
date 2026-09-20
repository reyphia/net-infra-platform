import type {
  AuditEvent,
  ChangeExecutionRow,
  ChangePlan,
  ChangePlanDeviceRow,
  ConfigBackup,
  CredentialProfile,
  Device,
  DiscoveryJob,
  HealthSnapshotOut,
  InterfaceOut,
  TopologyGraph,
} from "../types/api";

const BASE = "/api";

export class ApiError extends Error {
  status: number;
  detail: unknown;
  constructor(status: number, detail: unknown) {
    super(typeof detail === "string" ? detail : JSON.stringify(detail));
    this.status = status;
    this.detail = detail;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    let detail: unknown;
    try {
      detail = (await res.json()).detail;
    } catch {
      detail = await res.text();
    }
    throw new ApiError(res.status, detail);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export const api = {
  // Devices
  listDevices: (params?: Record<string, string | boolean>) => {
    const qs = params
      ? "?" + new URLSearchParams(Object.entries(params).map(([k, v]) => [k, String(v)])).toString()
      : "";
    return request<Device[]>(`/devices${qs}`);
  },
  getDevice: (id: string) => request<Device>(`/devices/${id}`),
  getDeviceInterfaces: (id: string) => request<InterfaceOut[]>(`/devices/${id}/interfaces`),
  assignCredential: (deviceId: string, credentialProfileId: string) =>
    request<Device>(`/devices/${deviceId}/credentials`, {
      method: "POST",
      body: JSON.stringify({ credential_profile_id: credentialProfileId }),
    }),
  setDriverType: (deviceId: string, driverType: string) =>
    request<Device>(`/devices/${deviceId}/driver?driver_type=${encodeURIComponent(driverType)}`, {
      method: "POST",
    }),
  deleteDevice: (id: string) => request<void>(`/devices/${id}`, { method: "DELETE" }),

  // Discovery
  startDiscovery: (body: {
    scope_cidrs: string[];
    timeout_seconds?: number;
    max_concurrency?: number;
    retry_count?: number;
    snmp_community?: string;
    snmp_port?: number;
    enable_snmp?: boolean;
    enable_lldp_cdp?: boolean;
  }) => request<DiscoveryJob>("/discovery", { method: "POST", body: JSON.stringify(body) }),
  listDiscoveryJobs: () => request<DiscoveryJob[]>("/discovery"),
  getDiscoveryJob: (id: string) => request<DiscoveryJob>(`/discovery/${id}`),
  cancelDiscoveryJob: (id: string) => request<DiscoveryJob>(`/discovery/${id}/cancel`, { method: "POST" }),

  // Topology
  getTopology: (params?: { device_type?: string; vendor?: string; online_only?: boolean }) => {
    const qs = params
      ? "?" +
        new URLSearchParams(
          Object.entries(params)
            .filter(([, v]) => v !== undefined)
            .map(([k, v]) => [k, String(v)]),
        ).toString()
      : "";
    return request<TopologyGraph>(`/topology${qs}`);
  },

  // Credentials
  listCredentials: () => request<CredentialProfile[]>("/credentials"),
  createSSHCredential: (body: {
    name: string;
    username: string;
    password?: string;
    enable_password?: string;
  }) =>
    request<CredentialProfile>("/credentials", {
      method: "POST",
      body: JSON.stringify({ protocol: "ssh", ...body }),
    }),
  createSNMPCredential: (body: { name: string; snmp_community: string; snmp_version?: string }) =>
    request<CredentialProfile>("/credentials", {
      method: "POST",
      body: JSON.stringify({ protocol: "snmp", ...body }),
    }),
  deleteCredential: (id: string) => request<void>(`/credentials/${id}`, { method: "DELETE" }),

  // Configuration
  getLiveConfig: (deviceId: string, source: "running" | "startup" = "running") =>
    request<{ source: string; config: string; sanitized: boolean }>(
      `/devices/${deviceId}/configuration/live?source=${source}`,
    ),
  createBackup: (deviceId: string, source: "running" | "startup" = "running") =>
    request<ConfigBackup>(`/devices/${deviceId}/configuration/backups?source=${source}`, { method: "POST" }),
  listBackups: (deviceId: string) => request<ConfigBackup[]>(`/devices/${deviceId}/configuration/backups`),
  getBackupContent: (deviceId: string, backupId: string) =>
    request<{ config: string; sanitized: boolean }>(
      `/devices/${deviceId}/configuration/backups/${backupId}/content`,
    ),
  diffBackups: (deviceId: string, beforeId: string, afterId: string) =>
    request<{ raw_diff: string; changes: unknown[]; categories_touched: string[] }>(
      `/devices/${deviceId}/configuration/backups/diff?before_id=${beforeId}&after_id=${afterId}`,
    ),

  // Change management
  createChangePlan: (body: {
    name: string;
    operator: string;
    proposed_config: string;
    device_ids: string[];
    save_after_apply?: boolean;
  }) => request<ChangePlan>("/change-plans", { method: "POST", body: JSON.stringify(body) }),
  listChangePlans: () => request<ChangePlan[]>("/change-plans"),
  getChangePlan: (id: string) => request<ChangePlan>(`/change-plans/${id}`),
  getChangePlanDevices: (id: string) => request<ChangePlanDeviceRow[]>(`/change-plans/${id}/devices`),
  validateChangePlan: (id: string) => request<ChangePlan>(`/change-plans/${id}/validate`, { method: "POST" }),
  previewChangePlan: (id: string) => request<ChangePlan>(`/change-plans/${id}/preview`, { method: "POST" }),
  applyChangePlan: (id: string, confirmedBy: string) =>
    request<ChangePlan>(`/change-plans/${id}/apply`, {
      method: "POST",
      body: JSON.stringify({ confirmed_by: confirmedBy }),
    }),
  getChangePlanExecutions: (id: string) => request<ChangeExecutionRow[]>(`/change-plans/${id}/executions`),
  rollbackExecution: (executionId: string, operator: string) =>
    request<{ id: string; rollback_status: string; rollback_detail: string }>(
      `/change-plans/executions/${executionId}/rollback?operator=${encodeURIComponent(operator)}`,
      { method: "POST" },
    ),

  // Audit
  listAuditEvents: (params?: { device_id?: string; action?: string; operator?: string }) => {
    const qs = params
      ? "?" +
        new URLSearchParams(Object.entries(params).filter(([, v]) => v) as [string, string][]).toString()
      : "";
    return request<AuditEvent[]>(`/audit${qs}`);
  },

  // Monitoring
  pollHealth: (deviceId: string) => request<HealthSnapshotOut>(`/devices/${deviceId}/health/poll`, { method: "POST" }),
  getLatestHealth: (deviceId: string) => request<HealthSnapshotOut>(`/devices/${deviceId}/health/latest`),
};

export function terminalWebSocketUrl(deviceId: string): string {
  const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${proto}//${window.location.host}/api/devices/${deviceId}/terminal/ws`;
}
