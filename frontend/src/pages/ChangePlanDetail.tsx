import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { api } from "../api/client";
import type { ChangeExecutionRow, ChangePlan, ChangePlanDeviceRow } from "../types/api";
import ErrorNotice from "../components/ErrorNotice";
import { StatusBadge } from "./ChangeManagement";
import { DiffView } from "./DeviceConfiguration";

export default function ChangePlanDetail() {
  const { planId } = useParams<{ planId: string }>();
  const [plan, setPlan] = useState<ChangePlan | null>(null);
  const [planDevices, setPlanDevices] = useState<ChangePlanDeviceRow[]>([]);
  const [executions, setExecutions] = useState<ChangeExecutionRow[]>([]);
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const [confirmName, setConfirmName] = useState("");

  const load = () => {
    if (!planId) return;
    api.getChangePlan(planId).then(setPlan).catch(setError);
    api.getChangePlanDevices(planId).then(setPlanDevices).catch(() => {});
    api.getChangePlanExecutions(planId).then(setExecutions).catch(() => {});
  };

  useEffect(load, [planId]);

  if (!planId) return null;
  if (!plan) return <div className="empty-state">Loading&hellip;</div>;

  const run = async (fn: () => Promise<unknown>) => {
    setBusy(true);
    setError(null);
    try {
      await fn();
      load();
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  };

  const canValidate = plan.status === "DRAFT";
  const canPreview = plan.status === "VALIDATED";
  const canApply = plan.status === "PREVIEWED";
  const isTerminal = ["APPLIED", "APPLY_FAILED", "VERIFIED"].includes(plan.status);

  return (
    <div>
      <h1>{plan.name}</h1>
      <div className="page-subtitle">
        Operator: {plan.operator} &middot; <StatusBadge status={plan.status} />
      </div>

      <ErrorNotice error={error} />

      <div className="panel">
        <h2>Proposed Configuration</h2>
        <pre className="config-view">{plan.proposed_config}</pre>
      </div>

      <div className="panel">
        <h2>Target Devices</h2>
        <table>
          <thead>
            <tr>
              <th>Device</th>
              <th>IP</th>
              <th>Eligible</th>
              <th>Reason</th>
            </tr>
          </thead>
          <tbody>
            {planDevices.map((d) => (
              <tr key={d.device_id}>
                <td>{d.hostname || d.device_id}</td>
                <td className="mono">{d.management_ip}</td>
                <td>
                  <span className={`badge ${d.eligible ? "badge-green" : "badge-red"}`}>
                    {d.eligible ? "ELIGIBLE" : "EXCLUDED"}
                  </span>
                </td>
                <td style={{ fontSize: 11, color: "var(--text-dim)" }}>{d.ineligibility_reason || "--"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="panel">
        <h2>Workflow</h2>
        <div style={{ display: "flex", gap: 8, marginBottom: 14 }}>
          <WorkflowStep label="Validate" done={!canValidate && plan.status !== "DRAFT"} />
          <WorkflowStep label="Preview" done={["PREVIEWED", "APPLYING", "APPLIED", "APPLY_FAILED", "VERIFIED"].includes(plan.status)} />
          <WorkflowStep label="Apply" done={isTerminal} />
          <WorkflowStep label="Verify" done={plan.status === "VERIFIED" || plan.status === "APPLIED"} />
        </div>

        {canValidate && (
          <button onClick={() => run(() => api.validateChangePlan(planId))} disabled={busy}>
            Validate
          </button>
        )}

        {canPreview && (
          <button onClick={() => run(() => api.previewChangePlan(planId))} disabled={busy}>
            Preview
          </button>
        )}

        {canApply && (
          <div>
            <div className="warn-box">
              Review the predicted diff below carefully. Applying will connect to each eligible device over SSH,
              create a pre-change backup, push the configuration, and re-verify the result.
            </div>
            <div className="form-row" style={{ maxWidth: 320 }}>
              <label>Type your name to confirm apply</label>
              <input value={confirmName} onChange={(e) => setConfirmName(e.target.value)} placeholder={plan.operator} />
            </div>
            <button
              className="danger"
              disabled={busy || confirmName.trim().length === 0}
              onClick={() => run(() => api.applyChangePlan(planId, confirmName.trim()))}
            >
              Apply to {planDevices.filter((d) => d.eligible).length} Device(s)
            </button>
          </div>
        )}

        {plan.status === "VALIDATION_FAILED" && (
          <div className="error-box">No devices are eligible for this change. See the table above for reasons.</div>
        )}
      </div>

      {plan.validation_report && (
        <div className="panel">
          <h2>Validation Report</h2>
          <div style={{ fontSize: 12.5, marginBottom: 8 }}>
            {plan.validation_report.summary.eligible} / {plan.validation_report.summary.total} devices eligible
          </div>
          {Object.entries(plan.validation_report.per_device).map(([deviceId, report]) => (
            <div key={deviceId} style={{ marginBottom: 8 }}>
              {report.issues.map((issue, i) => (
                <div key={i} className={issue.severity === "blocking" ? "error-box" : "warn-box"} style={{ marginBottom: 4 }}>
                  <span className="mono">{issue.line}</span> -- {issue.message}
                </div>
              ))}
            </div>
          ))}
        </div>
      )}

      {plan.diff_report && Object.keys(plan.diff_report).length > 0 && (
        <div className="panel">
          <h2>Predicted Diff (Preview)</h2>
          {Object.entries(plan.diff_report).map(([deviceId, report]) => (
            <div key={deviceId} style={{ marginBottom: 16 }}>
              <div style={{ fontSize: 11, color: "var(--text-dim)", marginBottom: 6 }}>{report.note}</div>
              <DiffView diff={report} />
            </div>
          ))}
        </div>
      )}

      {executions.length > 0 && (
        <div className="panel">
          <h2>Executions</h2>
          <table>
            <thead>
              <tr>
                <th>Device</th>
                <th>Apply</th>
                <th>Verified</th>
                <th>Error</th>
                <th>Rollback</th>
              </tr>
            </thead>
            <tbody>
              {executions.map((e) => (
                <tr key={e.id}>
                  <td className="mono" style={{ fontSize: 11 }}>
                    {e.device_id}
                  </td>
                  <td>
                    <span className={`badge ${e.apply_success ? "badge-green" : "badge-red"}`}>
                      {e.apply_success ? "SUCCESS" : "FAILED"}
                    </span>
                  </td>
                  <td>{e.verified ? "yes" : "no"}</td>
                  <td style={{ fontSize: 11, color: "var(--red)" }}>{e.apply_error || "--"}</td>
                  <td>
                    {e.rollback_status === "NOT_ATTEMPTED" && !e.apply_success ? (
                      <button
                        className="secondary"
                        disabled={busy}
                        onClick={() => run(() => api.rollbackExecution(e.id, plan.operator))}
                      >
                        Rollback
                      </button>
                    ) : (
                      <span
                        className={`badge ${
                          e.rollback_status === "SUCCESS" ? "badge-green" : e.rollback_status === "UNAVAILABLE" ? "badge-grey" : "badge-red"
                        }`}
                      >
                        {e.rollback_status}
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function WorkflowStep({ label, done }: { label: string; done: boolean }) {
  return (
    <div
      style={{
        padding: "5px 12px",
        borderRadius: 5,
        fontSize: 11.5,
        fontWeight: 600,
        background: done ? "rgba(52,199,123,0.12)" : "var(--bg-panel-alt)",
        color: done ? "var(--green)" : "var(--text-dim)",
        border: `1px solid ${done ? "rgba(52,199,123,0.3)" : "var(--border)"}`,
      }}
    >
      {done ? "\u2713 " : ""}
      {label}
    </div>
  );
}
