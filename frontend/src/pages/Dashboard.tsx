import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import type { AuditEvent, Device, DiscoveryJob } from "../types/api";
import ErrorNotice from "../components/ErrorNotice";
import { OnlineDot, ManagementStateBadge } from "../components/Badges";

export default function Dashboard() {
  const [devices, setDevices] = useState<Device[] | null>(null);
  const [jobs, setJobs] = useState<DiscoveryJob[] | null>(null);
  const [audit, setAudit] = useState<AuditEvent[] | null>(null);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    Promise.all([api.listDevices(), api.listDiscoveryJobs(), api.listAuditEvents()])
      .then(([d, j, a]) => {
        setDevices(d);
        setJobs(j);
        setAudit(a);
      })
      .catch(setError);
  }, []);

  if (error) return <ErrorNotice error={error} />;
  if (!devices || !jobs || !audit) return <div className="empty-state">Loading&hellip;</div>;

  const online = devices.filter((d) => d.is_online).length;
  const manageable = devices.filter((d) => d.available_management_methods.includes("SSH")).length;
  const consoleOnly = devices.filter(
    (d) => !d.available_management_methods.includes("SSH") && d.management_state !== "DISCOVERED",
  ).length;
  const unknownCount = devices.filter((d) => d.device_type === "UNKNOWN").length;
  const runningJobs = jobs.filter((j) => j.status === "RUNNING").length;

  return (
    <div>
      <h1>Dashboard</h1>
      <div className="page-subtitle">Live state of discovered infrastructure -- nothing on this page is sample data.</div>

      <div className="stat-grid">
        <StatCard label="Devices" value={devices.length} />
        <StatCard label="Online" value={online} accent="green" />
        <StatCard label="Offline" value={devices.length - online} accent="red" />
        <StatCard label="Unidentified" value={unknownCount} accent="amber" />
        <StatCard label="SSH-Manageable" value={manageable} accent="green" />
        <StatCard label="Console-only / Monitor-only" value={consoleOnly} accent="amber" />
        <StatCard label="Discovery Jobs Running" value={runningJobs} />
      </div>

      <div className="panel">
        <h2>Recent Discovery Jobs</h2>
        {jobs.length === 0 ? (
          <div className="empty-state">No discovery jobs yet. Start one from Settings.</div>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Scope</th>
                <th>Status</th>
                <th>Progress</th>
                <th>Found (by type)</th>
                <th>Started</th>
              </tr>
            </thead>
            <tbody>
              {jobs.slice(0, 8).map((j) => (
                <tr key={j.id}>
                  <td className="mono">{j.scope_cidrs.join(", ")}</td>
                  <td>
                    <StatusPill status={j.status} />
                  </td>
                  <td className="mono">
                    {j.processed_targets} / {j.total_targets}
                  </td>
                  <td className="mono" style={{ fontSize: 11 }}>
                    {Object.entries(j.counts_by_type)
                      .filter(([, n]) => n > 0)
                      .map(([t, n]) => `${t}:${n}`)
                      .join("  ") || "--"}
                  </td>
                  <td>{j.started_at ? new Date(j.started_at).toLocaleString() : "--"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className="panel">
        <h2>Devices</h2>
        {devices.length === 0 ? (
          <div className="empty-state">No devices discovered yet.</div>
        ) : (
          <table>
            <thead>
              <tr>
                <th></th>
                <th>Hostname</th>
                <th>Management IP</th>
                <th>Type</th>
                <th>Management State</th>
              </tr>
            </thead>
            <tbody>
              {devices.slice(0, 10).map((d) => (
                <tr key={d.id} className="clickable" onClick={() => (window.location.href = `/devices/${d.id}`)}>
                  <td>
                    <OnlineDot online={d.is_online} />
                  </td>
                  <td>{d.hostname || <span style={{ color: "var(--text-faint)" }}>unresolved</span>}</td>
                  <td className="mono">{d.management_ip}</td>
                  <td>{d.device_type}</td>
                  <td>
                    <ManagementStateBadge state={d.management_state} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {devices.length > 10 && (
          <div style={{ marginTop: 8 }}>
            <Link to="/devices">View all {devices.length} devices &rarr;</Link>
          </div>
        )}
      </div>

      <div className="panel">
        <h2>Recent Audit Activity</h2>
        {audit.length === 0 ? (
          <div className="empty-state">No audit events recorded yet.</div>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Time</th>
                <th>Operator</th>
                <th>Action</th>
                <th>Result</th>
              </tr>
            </thead>
            <tbody>
              {audit.slice(0, 8).map((e) => (
                <tr key={e.id}>
                  <td className="mono" style={{ fontSize: 11 }}>
                    {new Date(e.timestamp).toLocaleString()}
                  </td>
                  <td>{e.operator}</td>
                  <td className="mono">{e.action}</td>
                  <td>
                    <span className={`badge ${e.success ? "badge-green" : "badge-red"}`}>
                      {e.success ? "OK" : "FAILED"}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

function StatCard({ label, value, accent }: { label: string; value: number; accent?: string }) {
  return (
    <div className="stat-card">
      <div className="value" style={accent ? { color: `var(--${accent})` } : undefined}>
        {value}
      </div>
      <div className="label">{label}</div>
    </div>
  );
}

function StatusPill({ status }: { status: string }) {
  const cls =
    status === "COMPLETED" ? "badge-green" : status === "RUNNING" ? "badge-amber" : status === "FAILED" ? "badge-red" : "badge-grey";
  return <span className={`badge ${cls}`}>{status}</span>;
}
