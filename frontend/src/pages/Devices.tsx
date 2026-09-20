import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import type { Device } from "../types/api";
import ErrorNotice from "../components/ErrorNotice";
import { DeviceTypeBadge, ManagementMethodsList, ManagementStateBadge, OnlineDot } from "../components/Badges";

export default function Devices() {
  const [devices, setDevices] = useState<Device[] | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [query, setQuery] = useState("");
  const [typeFilter, setTypeFilter] = useState("");
  const navigate = useNavigate();

  useEffect(() => {
    api
      .listDevices({ q: query || undefined, device_type: typeFilter || undefined } as Record<string, string>)
      .then(setDevices)
      .catch(setError);
  }, [query, typeFilter]);

  return (
    <div>
      <h1>Devices</h1>
      <div className="page-subtitle">Every device the platform has discovered -- not all are remotely manageable.</div>

      <div style={{ display: "flex", gap: 10, marginBottom: 14 }}>
        <input
          placeholder="Search hostname or IP&hellip;"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          style={{ width: 260 }}
        />
        <select value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)}>
          <option value="">All types</option>
          {["ROUTER", "SWITCH", "FIREWALL", "ACCESS_POINT", "SERVER", "HOST", "UNKNOWN"].map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
      </div>

      <ErrorNotice error={error} />

      <div className="panel">
        {devices === null ? (
          <div className="empty-state">Loading&hellip;</div>
        ) : devices.length === 0 ? (
          <div className="empty-state">No devices match. Try running a discovery job from Settings.</div>
        ) : (
          <table>
            <thead>
              <tr>
                <th></th>
                <th>Hostname</th>
                <th>IP</th>
                <th>Vendor</th>
                <th>Type</th>
                <th>ID Confidence</th>
                <th>Management</th>
                <th>State</th>
                <th>Last Seen</th>
              </tr>
            </thead>
            <tbody>
              {devices.map((d) => (
                <tr key={d.id} className="clickable" onClick={() => navigate(`/devices/${d.id}`)}>
                  <td>
                    <OnlineDot online={d.is_online} />
                  </td>
                  <td>{d.hostname || <span style={{ color: "var(--text-faint)" }}>--</span>}</td>
                  <td className="mono">{d.management_ip}</td>
                  <td>{d.vendor || "--"}</td>
                  <td>
                    <DeviceTypeBadge type={d.device_type} />
                  </td>
                  <td className="mono">{Math.round(d.identification_confidence * 100)}%</td>
                  <td>
                    <ManagementMethodsList methods={d.available_management_methods} />
                  </td>
                  <td>
                    <ManagementStateBadge state={d.management_state} />
                  </td>
                  <td className="mono" style={{ fontSize: 11 }}>
                    {new Date(d.last_seen).toLocaleString()}
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
