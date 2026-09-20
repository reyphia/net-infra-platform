import type { ManagementMethod, ManagementState } from "../types/api";

export function OnlineDot({ online }: { online: boolean }) {
  return <span className={`dot ${online ? "dot-green" : "dot-red"}`} title={online ? "Online" : "Offline"} />;
}

const STATE_COLOR: Record<ManagementState, string> = {
  DISCOVERED: "badge-grey",
  IDENTIFIED: "badge-blue",
  MONITORABLE: "badge-amber",
  REMOTELY_MANAGEABLE: "badge-green",
  CONFIGURABLE: "badge-green",
};

export function ManagementStateBadge({ state }: { state: ManagementState }) {
  return <span className={`badge ${STATE_COLOR[state] ?? "badge-grey"}`}>{state.replace(/_/g, " ")}</span>;
}

export function ManagementMethodsList({ methods }: { methods: ManagementMethod[] }) {
  if (methods.length === 0 || (methods.length === 1 && methods[0] === "NONE")) {
    return <span className="badge badge-red">NONE DETECTED</span>;
  }
  return (
    <span style={{ display: "inline-flex", gap: 4, flexWrap: "wrap" }}>
      {methods
        .filter((m) => m !== "NONE")
        .map((m) => (
          <span key={m} className="badge badge-blue">
            {m}
          </span>
        ))}
    </span>
  );
}

export function ConfidenceBar({ value }: { value: number }) {
  const pct = Math.round(value * 100);
  return (
    <span style={{ display: "inline-flex", alignItems: "center" }}>
      <span className="confidence-bar">
        <span className="confidence-fill" style={{ width: `${pct}%` }} />
      </span>
      <span className="mono" style={{ fontSize: 11, color: "var(--text-dim)" }}>
        {pct}%
      </span>
    </span>
  );
}

export function DeviceTypeBadge({ type }: { type: string }) {
  return <span className="badge badge-grey">{type}</span>;
}
