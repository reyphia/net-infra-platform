import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { api } from "../api/client";
import type { AuditEvent, Device, HealthSnapshotOut, InterfaceOut } from "../types/api";
import ErrorNotice from "../components/ErrorNotice";
import { ManagementMethodsList, ManagementStateBadge, OnlineDot, ConfidenceBar } from "../components/Badges";
import DeviceTerminal from "../components/DeviceTerminal";
import DeviceConfiguration from "./DeviceConfiguration";

const TABS = ["Overview", "Interfaces", "Configuration", "Terminal", "Audit"] as const;
type Tab = (typeof TABS)[number];

export default function DeviceDetail() {
  const { deviceId } = useParams<{ deviceId: string }>();
  const [device, setDevice] = useState<Device | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [tab, setTab] = useState<Tab>("Overview");

  useEffect(() => {
    if (!deviceId) return;
    api.getDevice(deviceId).then(setDevice).catch(setError);
  }, [deviceId]);

  if (error) return <ErrorNotice error={error} />;
  if (!device || !deviceId) return <div className="empty-state">Loading&hellip;</div>;

  const canManage = device.available_management_methods.includes("SSH");

  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        <OnlineDot online={device.is_online} />
        <h1 style={{ margin: 0 }}>{device.hostname || device.management_ip}</h1>
        <ManagementStateBadge state={device.management_state} />
      </div>
      <div className="page-subtitle mono">
        {device.management_ip} &middot; {device.vendor || "unknown vendor"} {device.model || ""} &middot;{" "}
        {device.device_type}
      </div>

      {!canManage && (
        <div className="warn-box">
          This device is <strong>not remotely manageable</strong> -- no SSH access was detected during discovery.
          {device.available_management_methods.includes("SNMP")
            ? " It can still be monitored via SNMP, and may be reachable through a console server if one is configured."
            : " It is visible on the network but no management or monitoring protocol was detected."}
        </div>
      )}

      <div className="tabs">
        {TABS.map((t) => (
          <div key={t} className={`tab ${tab === t ? "active" : ""}`} onClick={() => setTab(t)}>
            {t}
          </div>
        ))}
      </div>

      {tab === "Overview" && <OverviewTab device={device} />}
      {tab === "Interfaces" && <InterfacesTab deviceId={deviceId} />}
      {tab === "Configuration" &&
        (canManage ? (
          <DeviceConfiguration deviceId={deviceId} />
        ) : (
          <div className="empty-state">Configuration retrieval requires SSH access, which is unavailable for this device.</div>
        ))}
      {tab === "Terminal" &&
        (canManage ? (
          <DeviceTerminal deviceId={deviceId} />
        ) : (
          <div className="empty-state">
            Remote CLI is unavailable for this device (CONSOLE ONLY / SNMP-monitorable). A real terminal session
            cannot be opened without SSH access.
          </div>
        ))}
      {tab === "Audit" && <AuditTab deviceId={deviceId} />}
    </div>
  );
}

function OverviewTab({ device }: { device: Device }) {
  const [health, setHealth] = useState<HealthSnapshotOut | null>(null);
  const [busy, setBusy] = useState(false);

  const poll = async () => {
    setBusy(true);
    try {
      const result = await api.pollHealth(device.id);
      setHealth(result);
    } finally {
      setBusy(false);
    }
  };

  useEffect(() => {
    api.getLatestHealth(device.id).then(setHealth).catch(() => setHealth(null));
  }, [device.id]);

  return (
    <div>
      <div className="panel">
        <h2>Device Facts</h2>
        <table>
          <tbody>
            <Row label="Hostname" value={device.hostname || "--"} />
            <Row label="Management IP" value={device.management_ip} mono />
            <Row label="Vendor" value={device.vendor || "unknown"} />
            <Row label="Model" value={device.model || "unknown"} />
            <Row label="OS" value={`${device.os_name || "unknown"} ${device.os_version || ""}`} />
            <Row label="Uptime" value={device.uptime_seconds ? formatUptime(device.uptime_seconds) : "unavailable"} />
            <Row
              label="Identification Confidence"
              value={<ConfidenceBar value={device.identification_confidence} />}
            />
            <Row label="Identification Sources" value={device.identification_sources.join(", ") || "none"} />
            <Row label="Driver" value={device.driver_type || "not assigned"} />
            <Row label="Management Methods" value={<ManagementMethodsList methods={device.available_management_methods} />} />
            <Row label="First Seen" value={new Date(device.first_seen).toLocaleString()} />
            <Row label="Last Seen" value={new Date(device.last_seen).toLocaleString()} />
          </tbody>
        </table>
      </div>

      <div className="panel">
        <h2>Health</h2>
        <button onClick={poll} disabled={busy} style={{ marginBottom: 10 }}>
          Poll Now
        </button>
        {health && health.available !== false ? (
          <table>
            <tbody>
              <Row label="Online" value={health.is_online ? "yes" : "no"} />
              <Row label="CPU" value={health.cpu_percent != null ? `${health.cpu_percent.toFixed(1)}%` : "unavailable"} />
              <Row
                label="Memory"
                value={health.memory_percent != null ? `${health.memory_percent.toFixed(1)}%` : "unavailable"}
              />
              <Row label="ICMP RTT" value={health.icmp_rtt_ms != null ? `${health.icmp_rtt_ms.toFixed(1)} ms` : "unavailable"} />
              <Row label="Collected" value={health.collected_at ? new Date(health.collected_at).toLocaleString() : "--"} />
            </tbody>
          </table>
        ) : (
          <div className="empty-state">No health data yet -- click Poll Now.</div>
        )}
      </div>
    </div>
  );
}

function InterfacesTab({ deviceId }: { deviceId: string }) {
  const [interfaces, setInterfaces] = useState<InterfaceOut[] | null>(null);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    api.getDeviceInterfaces(deviceId).then(setInterfaces).catch(setError);
  }, [deviceId]);

  if (error) return <ErrorNotice error={error} />;
  if (!interfaces) return <div className="empty-state">Loading&hellip;</div>;
  if (interfaces.length === 0)
    return (
      <div className="empty-state">
        No interface data stored yet. Interface polling happens via SNMP or the SSH driver's get_interfaces() --
        run a poll or connect once to populate this.
      </div>
    );

  return (
    <div className="panel">
      <table>
        <thead>
          <tr>
            <th>Name</th>
            <th>Description</th>
            <th>Admin</th>
            <th>Oper</th>
            <th>Speed</th>
            <th>Duplex</th>
            <th>MAC</th>
          </tr>
        </thead>
        <tbody>
          {interfaces.map((i) => (
            <tr key={i.id}>
              <td className="mono">{i.name}</td>
              <td>{i.description || "--"}</td>
              <td>
                <span className={`badge ${i.admin_state === "up" ? "badge-green" : "badge-grey"}`}>
                  {i.admin_state || "?"}
                </span>
              </td>
              <td>
                <span className={`badge ${i.oper_state === "up" ? "badge-green" : "badge-red"}`}>
                  {i.oper_state || "?"}
                </span>
              </td>
              <td className="mono">{i.speed_mbps ? `${i.speed_mbps} Mbps` : "--"}</td>
              <td>{i.duplex || "--"}</td>
              <td className="mono">{i.mac_address || "--"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function AuditTab({ deviceId }: { deviceId: string }) {
  const [events, setEvents] = useState<AuditEvent[] | null>(null);

  useEffect(() => {
    api.listAuditEvents({ device_id: deviceId }).then(setEvents);
  }, [deviceId]);

  if (!events) return <div className="empty-state">Loading&hellip;</div>;
  if (events.length === 0) return <div className="empty-state">No audit events for this device yet.</div>;

  return (
    <div className="panel">
      <table>
        <thead>
          <tr>
            <th>Time</th>
            <th>Operator</th>
            <th>Action</th>
            <th>Protocol</th>
            <th>Result</th>
            <th>Detail / Error</th>
          </tr>
        </thead>
        <tbody>
          {events.map((e) => (
            <tr key={e.id}>
              <td className="mono" style={{ fontSize: 11 }}>
                {new Date(e.timestamp).toLocaleString()}
              </td>
              <td>{e.operator}</td>
              <td className="mono">{e.action}</td>
              <td>{e.protocol || "--"}</td>
              <td>
                <span className={`badge ${e.success ? "badge-green" : "badge-red"}`}>{e.success ? "OK" : "FAILED"}</span>
              </td>
              <td style={{ fontSize: 11, color: "var(--text-dim)" }}>{e.error || e.detail || "--"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Row({ label, value, mono }: { label: string; value: React.ReactNode; mono?: boolean }) {
  return (
    <tr>
      <td style={{ color: "var(--text-dim)", width: 220 }}>{label}</td>
      <td className={mono ? "mono" : undefined}>{value}</td>
    </tr>
  );
}

function formatUptime(seconds: number): string {
  const days = Math.floor(seconds / 86400);
  const hours = Math.floor((seconds % 86400) / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  return `${days}d ${hours}h ${minutes}m`;
}
