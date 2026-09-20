import { useEffect, useRef, useState } from "react";
import { Terminal } from "@xterm/xterm";
import { FitAddon } from "@xterm/addon-fit";
import "@xterm/xterm/css/xterm.css";
import { terminalWebSocketUrl } from "../api/client";

type ConnState = "connecting" | "open" | "closed" | "error";

export default function DeviceTerminal({ deviceId }: { deviceId: string }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const termRef = useRef<Terminal | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const [state, setState] = useState<ConnState>("connecting");
  const [sessionKey, setSessionKey] = useState(0);

  useEffect(() => {
    if (!containerRef.current) return;
    const term = new Terminal({
      convertEol: true,
      fontSize: 13,
      fontFamily: "SF Mono, JetBrains Mono, Consolas, monospace",
      theme: { background: "#000000", foreground: "#d7e1ee" },
      cursorBlink: true,
    });
    const fit = new FitAddon();
    term.loadAddon(fit);
    term.open(containerRef.current);
    fit.fit();
    termRef.current = term;

    const ws = new WebSocket(terminalWebSocketUrl(deviceId));
    wsRef.current = ws;
    setState("connecting");

    ws.onopen = () => setState("open");
    ws.onclose = () => setState("closed");
    ws.onerror = () => setState("error");
    ws.onmessage = (event) => term.write(event.data);

    const onData = term.onData((data) => {
      if (ws.readyState === WebSocket.OPEN) ws.send(data);
    });

    const resizeObserver = new ResizeObserver(() => fit.fit());
    resizeObserver.observe(containerRef.current);

    return () => {
      onData.dispose();
      resizeObserver.disconnect();
      ws.close();
      term.dispose();
    };
  }, [deviceId, sessionKey]);

  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 8 }}>
        <StateBadge state={state} />
        <button className="secondary" onClick={() => setSessionKey((k) => k + 1)}>
          Reconnect
        </button>
        <span style={{ fontSize: 11, color: "var(--text-dim)" }}>
          Real SSH session -- every command reaches the device and is recorded in the audit log.
        </span>
      </div>
      <div className="terminal-container" ref={containerRef} />
    </div>
  );
}

function StateBadge({ state }: { state: ConnState }) {
  const map: Record<ConnState, { cls: string; label: string }> = {
    connecting: { cls: "badge-amber", label: "CONNECTING" },
    open: { cls: "badge-green", label: "CONNECTED" },
    closed: { cls: "badge-grey", label: "DISCONNECTED" },
    error: { cls: "badge-red", label: "ERROR" },
  };
  const { cls, label } = map[state];
  return <span className={`badge ${cls}`}>{label}</span>;
}
