import { useEffect, useState } from "react";
import { api } from "../api/client";
import type { ConfigBackup } from "../types/api";
import ErrorNotice from "../components/ErrorNotice";

interface DiffResult {
  raw_diff: string;
  changes: { category: string; entity: string; change_type: string; added_lines: string[]; removed_lines: string[] }[];
  categories_touched: string[];
}

export default function DeviceConfiguration({ deviceId }: { deviceId: string }) {
  const [backups, setBackups] = useState<ConfigBackup[] | null>(null);
  const [liveConfig, setLiveConfig] = useState<string | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const [beforeId, setBeforeId] = useState("");
  const [afterId, setAfterId] = useState("");
  const [diff, setDiff] = useState<DiffResult | null>(null);

  const refreshBackups = () => api.listBackups(deviceId).then(setBackups).catch(setError);

  useEffect(() => {
    refreshBackups();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [deviceId]);

  const fetchLive = async () => {
    setBusy(true);
    setError(null);
    try {
      const result = await api.getLiveConfig(deviceId, "running");
      setLiveConfig(result.config);
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  };

  const createBackup = async () => {
    setBusy(true);
    setError(null);
    try {
      await api.createBackup(deviceId, "running");
      await refreshBackups();
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  };

  const runDiff = async () => {
    if (!beforeId || !afterId) return;
    setBusy(true);
    setError(null);
    try {
      const result = await api.diffBackups(deviceId, beforeId, afterId);
      setDiff(result as DiffResult);
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div>
      <ErrorNotice error={error} />

      <div className="panel">
        <h2>Live Configuration</h2>
        <div style={{ display: "flex", gap: 8, marginBottom: 10 }}>
          <button onClick={fetchLive} disabled={busy}>
            Retrieve Running Config
          </button>
          <button className="secondary" onClick={createBackup} disabled={busy}>
            Create Backup
          </button>
        </div>
        {liveConfig !== null && (
          <pre className="config-view">
            {liveConfig}
            {"\n\n"}
            <span style={{ color: "var(--text-faint)" }}>
              -- secrets redacted for display; the stored backup preserves the original for restoration --
            </span>
          </pre>
        )}
      </div>

      <div className="panel">
        <h2>Backups</h2>
        {backups === null ? (
          <div className="empty-state">Loading&hellip;</div>
        ) : backups.length === 0 ? (
          <div className="empty-state">No backups yet. Create one above, or via a change plan.</div>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Created</th>
                <th>Source</th>
                <th>Trigger</th>
                <th>Operator</th>
                <th>SHA-256</th>
                <th>Size</th>
              </tr>
            </thead>
            <tbody>
              {backups.map((b) => (
                <tr key={b.id}>
                  <td className="mono" style={{ fontSize: 11 }}>
                    {new Date(b.created_at).toLocaleString()}
                  </td>
                  <td>{b.source}</td>
                  <td>
                    <span className="badge badge-grey">{b.trigger}</span>
                  </td>
                  <td>{b.operator}</td>
                  <td className="mono" style={{ fontSize: 10 }}>
                    {b.sha256.slice(0, 12)}&hellip;
                  </td>
                  <td className="mono">{b.byte_size}B</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {backups && backups.length >= 2 && (
        <div className="panel">
          <h2>Compare Backups (Semantic Diff)</h2>
          <div style={{ display: "flex", gap: 8, marginBottom: 10, alignItems: "center" }}>
            <select value={beforeId} onChange={(e) => setBeforeId(e.target.value)}>
              <option value="">Before&hellip;</option>
              {backups.map((b) => (
                <option key={b.id} value={b.id}>
                  {new Date(b.created_at).toLocaleString()} ({b.trigger})
                </option>
              ))}
            </select>
            <span style={{ color: "var(--text-dim)" }}>&rarr;</span>
            <select value={afterId} onChange={(e) => setAfterId(e.target.value)}>
              <option value="">After&hellip;</option>
              {backups.map((b) => (
                <option key={b.id} value={b.id}>
                  {new Date(b.created_at).toLocaleString()} ({b.trigger})
                </option>
              ))}
            </select>
            <button onClick={runDiff} disabled={!beforeId || !afterId || busy}>
              Diff
            </button>
          </div>
          {diff && <DiffView diff={diff} />}
        </div>
      )}
    </div>
  );
}

export function DiffView({ diff }: { diff: DiffResult }) {
  if (diff.changes.length === 0) {
    return <div className="empty-state">No semantic differences detected.</div>;
  }
  const byCategory = new Map<string, typeof diff.changes>();
  for (const c of diff.changes) {
    const list = byCategory.get(c.category) ?? [];
    list.push(c);
    byCategory.set(c.category, list);
  }
  return (
    <div>
      {[...byCategory.entries()].map(([category, changes]) => (
        <div key={category} style={{ marginBottom: 14 }}>
          <div style={{ fontWeight: 700, fontSize: 12, marginBottom: 6, color: "var(--purple)" }}>{category}</div>
          {changes.map((c, i) => (
            <div key={i} style={{ marginBottom: 8 }}>
              <div className="mono" style={{ fontSize: 12, marginBottom: 2 }}>
                <span
                  className={`badge ${c.change_type === "added" ? "badge-green" : c.change_type === "removed" ? "badge-red" : "badge-amber"}`}
                  style={{ marginRight: 6 }}
                >
                  {c.change_type}
                </span>
                {c.entity}
              </div>
              {c.removed_lines.map((l, j) => (
                <span key={`r${j}`} className="diff-line-removed">
                  - {l}
                </span>
              ))}
              {c.added_lines.map((l, j) => (
                <span key={`a${j}`} className="diff-line-added">
                  + {l}
                </span>
              ))}
            </div>
          ))}
        </div>
      ))}
    </div>
  );
}
