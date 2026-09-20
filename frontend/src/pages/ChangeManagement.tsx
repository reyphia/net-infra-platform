import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import type { ChangePlan, Device } from "../types/api";
import ErrorNotice from "../components/ErrorNotice";

export default function ChangeManagement() {
  const [plans, setPlans] = useState<ChangePlan[] | null>(null);
  const [devices, setDevices] = useState<Device[]>([]);
  const [error, setError] = useState<unknown>(null);
  const [showForm, setShowForm] = useState(false);
  const navigate = useNavigate();

  const [name, setName] = useState("");
  const [operator, setOperator] = useState("");
  const [proposedConfig, setProposedConfig] = useState("");
  const [selectedDevices, setSelectedDevices] = useState<string[]>([]);
  const [saveAfterApply, setSaveAfterApply] = useState(false);
  const [creating, setCreating] = useState(false);

  const load = () => {
    api.listChangePlans().then(setPlans).catch(setError);
    api.listDevices({ online_only: true } as Record<string, boolean>).then(setDevices).catch(() => {});
  };

  useEffect(load, []);

  const createPlan = async () => {
    setCreating(true);
    setError(null);
    try {
      const plan = await api.createChangePlan({
        name,
        operator,
        proposed_config: proposedConfig,
        device_ids: selectedDevices,
        save_after_apply: saveAfterApply,
      });
      navigate(`/changes/${plan.id}`);
    } catch (e) {
      setError(e);
    } finally {
      setCreating(false);
    }
  };

  return (
    <div>
      <h1>Change Management</h1>
      <div className="page-subtitle">
        Every change follows PLAN &rarr; VALIDATE &rarr; PREVIEW &rarr; APPLY &rarr; VERIFY. Nothing is pushed to a
        device without an explicit confirmation after seeing the diff.
      </div>

      <ErrorNotice error={error} />

      <div style={{ marginBottom: 14 }}>
        <button onClick={() => setShowForm((s) => !s)}>{showForm ? "Cancel" : "New Change Plan"}</button>
      </div>

      {showForm && (
        <div className="panel">
          <h2>New Change Plan</h2>
          <div className="form-row">
            <label>Plan Name</label>
            <input value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Fix VLAN on access ports" />
          </div>
          <div className="form-row">
            <label>Operator</label>
            <input value={operator} onChange={(e) => setOperator(e.target.value)} placeholder="your name" />
          </div>
          <div className="form-row">
            <label>Target Devices ({selectedDevices.length} selected)</label>
            <div style={{ maxHeight: 140, overflowY: "auto", border: "1px solid var(--border)", borderRadius: 5, padding: 6 }}>
              {devices.map((d) => (
                <label key={d.id} style={{ display: "flex", gap: 6, fontSize: 12.5, padding: "3px 0" }}>
                  <input
                    type="checkbox"
                    checked={selectedDevices.includes(d.id)}
                    onChange={(e) =>
                      setSelectedDevices((prev) => (e.target.checked ? [...prev, d.id] : prev.filter((id) => id !== d.id)))
                    }
                  />
                  {d.hostname || d.management_ip} <span className="mono" style={{ color: "var(--text-dim)" }}>({d.management_ip})</span>
                </label>
              ))}
            </div>
          </div>
          <div className="form-row">
            <label>Proposed Configuration Lines</label>
            <textarea
              rows={8}
              value={proposedConfig}
              onChange={(e) => setProposedConfig(e.target.value)}
              placeholder={"interface GigabitEthernet1/0/24\n description Updated by change plan\n switchport access vlan 20"}
            />
          </div>
          <label style={{ display: "flex", gap: 6, fontSize: 12.5, marginBottom: 12 }}>
            <input type="checkbox" checked={saveAfterApply} onChange={(e) => setSaveAfterApply(e.target.checked)} />
            Save configuration to startup/flash after a successful apply
          </label>
          <button onClick={createPlan} disabled={creating || !name || !operator || selectedDevices.length === 0 || !proposedConfig}>
            Create Plan
          </button>
        </div>
      )}

      <div className="panel">
        <h2>All Change Plans</h2>
        {plans === null ? (
          <div className="empty-state">Loading&hellip;</div>
        ) : plans.length === 0 ? (
          <div className="empty-state">No change plans yet.</div>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Name</th>
                <th>Operator</th>
                <th>Status</th>
                <th>Created</th>
              </tr>
            </thead>
            <tbody>
              {plans.map((p) => (
                <tr key={p.id} className="clickable" onClick={() => navigate(`/changes/${p.id}`)}>
                  <td>{p.name}</td>
                  <td>{p.operator}</td>
                  <td>
                    <StatusBadge status={p.status} />
                  </td>
                  <td className="mono" style={{ fontSize: 11 }}>
                    {new Date(p.created_at).toLocaleString()}
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

export function StatusBadge({ status }: { status: string }) {
  const cls = status.includes("FAILED")
    ? "badge-red"
    : status === "APPLIED" || status === "VERIFIED"
      ? "badge-green"
      : status === "DRAFT"
        ? "badge-grey"
        : "badge-amber";
  return <span className={`badge ${cls}`}>{status.replace(/_/g, " ")}</span>;
}
