import { useEffect, useState } from "react";
import { api } from "../api/client";
import type { CredentialProfile, DiscoveryJob } from "../types/api";
import ErrorNotice from "../components/ErrorNotice";

export default function Settings() {
  return (
    <div>
      <h1>Settings</h1>
      <div className="page-subtitle">Discovery scope, credential profiles, and system configuration.</div>
      <DiscoverySection />
      <CredentialsSection />
    </div>
  );
}

function DiscoverySection() {
  const [cidrs, setCidrs] = useState("");
  const [timeout, setTimeoutSeconds] = useState(2);
  const [maxConcurrency, setMaxConcurrency] = useState(50);
  const [snmpCommunity, setSnmpCommunity] = useState("");
  const [enableSnmp, setEnableSnmp] = useState(true);
  const [enableLldpCdp, setEnableLldpCdp] = useState(true);
  const [jobs, setJobs] = useState<DiscoveryJob[]>([]);
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);

  const refresh = () => api.listDiscoveryJobs().then(setJobs).catch(() => {});

  useEffect(() => {
    refresh();
    const interval = setInterval(refresh, 4000);
    return () => clearInterval(interval);
  }, []);

  const start = async () => {
    setBusy(true);
    setError(null);
    try {
      const scopeCidrs = cidrs
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean);
      await api.startDiscovery({
        scope_cidrs: scopeCidrs,
        timeout_seconds: timeout,
        max_concurrency: maxConcurrency,
        snmp_community: enableSnmp ? snmpCommunity || undefined : undefined,
        enable_snmp: enableSnmp,
        enable_lldp_cdp: enableLldpCdp,
      });
      refresh();
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="panel">
      <h2>Discovery</h2>
      <div className="warn-box">
        Only scan networks you are authorized to discover. Each job requires an explicit CIDR scope -- there is no
        default or implicit range.
      </div>
      <ErrorNotice error={error} />
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginBottom: 12 }}>
        <div className="form-row">
          <label>Scope (comma-separated CIDRs)</label>
          <input value={cidrs} onChange={(e) => setCidrs(e.target.value)} placeholder="10.10.0.0/24, 10.10.1.0/24" />
        </div>
        <div className="form-row">
          <label>SNMP Community (v2c, optional)</label>
          <input
            type="password"
            value={snmpCommunity}
            onChange={(e) => setSnmpCommunity(e.target.value)}
            placeholder="never logged or displayed again"
          />
        </div>
        <div className="form-row">
          <label>Per-host timeout (seconds)</label>
          <input type="number" value={timeout} onChange={(e) => setTimeoutSeconds(Number(e.target.value))} />
        </div>
        <div className="form-row">
          <label>Max concurrent probes</label>
          <input type="number" value={maxConcurrency} onChange={(e) => setMaxConcurrency(Number(e.target.value))} />
        </div>
      </div>
      <div style={{ display: "flex", gap: 16, marginBottom: 12 }}>
        <label style={{ display: "flex", gap: 6, fontSize: 12.5 }}>
          <input type="checkbox" checked={enableSnmp} onChange={(e) => setEnableSnmp(e.target.checked)} />
          Enable SNMP queries
        </label>
        <label style={{ display: "flex", gap: 6, fontSize: 12.5 }}>
          <input type="checkbox" checked={enableLldpCdp} onChange={(e) => setEnableLldpCdp(e.target.checked)} />
          Enable LLDP/CDP topology discovery
        </label>
      </div>
      <button onClick={start} disabled={busy || !cidrs.trim()}>
        Start Discovery
      </button>

      {jobs.length > 0 && (
        <table style={{ marginTop: 16 }}>
          <thead>
            <tr>
              <th>Scope</th>
              <th>Status</th>
              <th>Progress</th>
            </tr>
          </thead>
          <tbody>
            {jobs.slice(0, 5).map((j) => (
              <tr key={j.id}>
                <td className="mono">{j.scope_cidrs.join(", ")}</td>
                <td>
                  <span
                    className={`badge ${j.status === "COMPLETED" ? "badge-green" : j.status === "RUNNING" ? "badge-amber" : j.status === "FAILED" ? "badge-red" : "badge-grey"}`}
                  >
                    {j.status}
                  </span>
                </td>
                <td className="mono">
                  {j.processed_targets}/{j.total_targets}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

function CredentialsSection() {
  const [profiles, setProfiles] = useState<CredentialProfile[]>([]);
  const [error, setError] = useState<unknown>(null);
  const [protocol, setProtocol] = useState<"ssh" | "snmp">("ssh");
  const [name, setName] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [enablePassword, setEnablePassword] = useState("");
  const [community, setCommunity] = useState("");
  const [busy, setBusy] = useState(false);

  const refresh = () => {
    api.listCredentials().then(setProfiles).catch(setError);
  };
  useEffect(refresh, []);

  const create = async () => {
    setBusy(true);
    setError(null);
    try {
      if (protocol === "ssh") {
        await api.createSSHCredential({ name, username, password: password || undefined, enable_password: enablePassword || undefined });
      } else {
        await api.createSNMPCredential({ name, snmp_community: community });
      }
      setName("");
      setUsername("");
      setPassword("");
      setEnablePassword("");
      setCommunity("");
      refresh();
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  };

  const remove = async (id: string) => {
    await api.deleteCredential(id);
    refresh();
  };

  return (
    <div className="panel">
      <h2>Credential Profiles</h2>
      <div className="page-subtitle" style={{ marginTop: -4 }}>
        Secrets are encrypted at rest and never returned by the API after creation.
      </div>
      <ErrorNotice error={error} />

      <div style={{ display: "flex", gap: 10, marginBottom: 10, flexWrap: "wrap", alignItems: "flex-end" }}>
        <div className="form-row">
          <label>Protocol</label>
          <select value={protocol} onChange={(e) => setProtocol(e.target.value as "ssh" | "snmp")}>
            <option value="ssh">SSH</option>
            <option value="snmp">SNMP (v2c)</option>
          </select>
        </div>
        <div className="form-row">
          <label>Profile Name</label>
          <input value={name} onChange={(e) => setName(e.target.value)} placeholder="lab-admin" />
        </div>
        {protocol === "ssh" ? (
          <>
            <div className="form-row">
              <label>Username</label>
              <input value={username} onChange={(e) => setUsername(e.target.value)} />
            </div>
            <div className="form-row">
              <label>Password</label>
              <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
            </div>
            <div className="form-row">
              <label>Enable Password (optional)</label>
              <input type="password" value={enablePassword} onChange={(e) => setEnablePassword(e.target.value)} />
            </div>
          </>
        ) : (
          <div className="form-row">
            <label>Community String</label>
            <input type="password" value={community} onChange={(e) => setCommunity(e.target.value)} />
          </div>
        )}
        <button onClick={create} disabled={busy || !name}>
          Create Profile
        </button>
      </div>

      <table>
        <thead>
          <tr>
            <th>Name</th>
            <th>Protocol</th>
            <th>Username</th>
            <th>Created</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {profiles.map((p) => (
            <tr key={p.id}>
              <td>{p.name}</td>
              <td>{p.protocol.toUpperCase()}</td>
              <td>{p.username || "--"}</td>
              <td className="mono" style={{ fontSize: 11 }}>
                {new Date(p.created_at).toLocaleString()}
              </td>
              <td>
                <button className="secondary" onClick={() => remove(p.id)}>
                  Delete
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
