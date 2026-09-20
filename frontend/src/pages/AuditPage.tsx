import { useEffect, useState } from "react";
import { api } from "../api/client";
import type { AuditEvent } from "../types/api";
import ErrorNotice from "../components/ErrorNotice";

export default function AuditPage() {
  const [events, setEvents] = useState<AuditEvent[] | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [action, setAction] = useState("");
  const [operator, setOperator] = useState("");

  useEffect(() => {
    api
      .listAuditEvents({ action: action || undefined, operator: operator || undefined })
      .then(setEvents)
      .catch(setError);
  }, [action, operator]);

  return (
    <div>
      <h1>Audit Log</h1>
      <div className="page-subtitle">
        Every sensitive operation -- discovery, config retrieval, backups, changes, rollbacks, terminal sessions --
        is recorded here. Secrets are never logged.
      </div>

      <div style={{ display: "flex", gap: 10, marginBottom: 14 }}>
        <input placeholder="Filter by action&hellip;" value={action} onChange={(e) => setAction(e.target.value)} />
        <input placeholder="Filter by operator&hellip;" value={operator} onChange={(e) => setOperator(e.target.value)} />
      </div>

      <ErrorNotice error={error} />

      <div className="panel">
        {events === null ? (
          <div className="empty-state">Loading&hellip;</div>
        ) : events.length === 0 ? (
          <div className="empty-state">No matching audit events.</div>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Time</th>
                <th>Operator</th>
                <th>Action</th>
                <th>Device</th>
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
                  <td className="mono" style={{ fontSize: 11 }}>
                    {e.device_id ? e.device_id.slice(0, 8) : "--"}
                  </td>
                  <td>{e.protocol || "--"}</td>
                  <td>
                    <span className={`badge ${e.success ? "badge-green" : "badge-red"}`}>{e.success ? "OK" : "FAILED"}</span>
                  </td>
                  <td style={{ fontSize: 11, color: "var(--text-dim)" }}>{e.error || e.detail || "--"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
