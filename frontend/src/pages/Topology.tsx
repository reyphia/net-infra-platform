import { useCallback, useEffect, useMemo, useState } from "react";
import ReactFlow, {
  Background,
  Controls,
  MiniMap,
  type Edge,
  type Node,
  MarkerType,
  useEdgesState,
  useNodesState,
} from "reactflow";
import "reactflow/dist/style.css";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import type { TopologyGraph } from "../types/api";
import ErrorNotice from "../components/ErrorNotice";

const TYPE_COLOR: Record<string, string> = {
  ROUTER: "#3b82f6",
  SWITCH: "#34c77b",
  FIREWALL: "#f0576a",
  ACCESS_POINT: "#a78bfa",
  SERVER: "#e8b339",
  HOST: "#7c8ba1",
  UNKNOWN: "#4d5b70",
};

function layoutNodes(graph: TopologyGraph): Node[] {
  // Simple deterministic grid layout grouped by device type -- no external
  // layout dependency needed for a discovery-sized topology. Operators can
  // drag nodes afterward (React Flow persists position in-session).
  const byType = new Map<string, typeof graph.nodes>();
  for (const n of graph.nodes) {
    const list = byType.get(n.device_type) ?? [];
    list.push(n);
    byType.set(n.device_type, list);
  }
  const nodes: Node[] = [];
  let rowIndex = 0;
  for (const [type, group] of byType) {
    group.forEach((n, col) => {
      nodes.push({
        id: n.id,
        position: { x: col * 190, y: rowIndex * 140 },
        data: { label: n.hostname || n.management_ip, node: n },
        style: {
          background: "#161d29",
          border: `1.5px solid ${TYPE_COLOR[type] ?? "#4d5b70"}`,
          borderRadius: 6,
          color: "#d7e1ee",
          fontSize: 11,
          padding: 8,
          width: 170,
        },
      });
    });
    rowIndex += 1;
  }
  return nodes;
}

function edgeColor(confidence: number): string {
  if (confidence >= 0.95) return "#34c77b";
  if (confidence >= 0.8) return "#3b82f6";
  return "#e8b339";
}

export default function Topology() {
  const [graph, setGraph] = useState<TopologyGraph | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [deviceType, setDeviceType] = useState("");
  const [onlineOnly, setOnlineOnly] = useState(false);
  const navigate = useNavigate();

  const load = useCallback(() => {
    api
      .getTopology({ device_type: deviceType || undefined, online_only: onlineOnly })
      .then(setGraph)
      .catch(setError);
  }, [deviceType, onlineOnly]);

  useEffect(load, [load]);

  const initialNodes = useMemo(() => (graph ? layoutNodes(graph) : []), [graph]);
  const initialEdges = useMemo<Edge[]>(
    () =>
      graph
        ? graph.edges.map((e) => ({
            id: e.id,
            source: e.source,
            target: e.target,
            label: `${e.discovery_methods.join("+")} (${Math.round(e.confidence * 100)}%)`,
            labelStyle: { fontSize: 9, fill: "#7c8ba1" },
            style: { stroke: edgeColor(e.confidence), strokeWidth: 1.5 },
            markerEnd: { type: MarkerType.ArrowClosed, color: edgeColor(e.confidence) },
          }))
        : [],
    [graph],
  );

  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);

  useEffect(() => setNodes(initialNodes), [initialNodes, setNodes]);
  useEffect(() => setEdges(initialEdges), [initialEdges, setEdges]);

  if (error) return <ErrorNotice error={error} />;

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "calc(100vh - 40px)" }}>
      <h1>Topology</h1>
      <div className="page-subtitle">
        Built entirely from observed discovery evidence (LLDP/CDP/SNMP). Edge color reflects confidence, not just
        presence of a link.
      </div>

      <div style={{ display: "flex", gap: 10, marginBottom: 12, alignItems: "center" }}>
        <select value={deviceType} onChange={(e) => setDeviceType(e.target.value)}>
          <option value="">All device types</option>
          {["ROUTER", "SWITCH", "FIREWALL", "ACCESS_POINT", "SERVER", "HOST", "UNKNOWN"].map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
        <label style={{ display: "flex", alignItems: "center", gap: 5, fontSize: 12.5 }}>
          <input type="checkbox" checked={onlineOnly} onChange={(e) => setOnlineOnly(e.target.checked)} />
          Online only
        </label>
        <button className="secondary" onClick={load}>
          Refresh
        </button>
        {graph && (
          <span style={{ fontSize: 11, color: "var(--text-dim)" }}>
            {graph.nodes.length} devices &middot; {graph.edges.length} links &middot; generated{" "}
            {new Date(graph.generated_at).toLocaleTimeString()}
          </span>
        )}
      </div>

      {graph && graph.nodes.length === 0 ? (
        <div className="empty-state">No devices to show. Run a discovery job first.</div>
      ) : (
        <div style={{ flex: 1, border: "1px solid var(--border)", borderRadius: 6, overflow: "hidden" }}>
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onNodeClick={(_, node) => navigate(`/devices/${node.id}`)}
            fitView
            proOptions={{ hideAttribution: true }}
          >
            <Background color="#263041" gap={18} />
            <Controls />
            <MiniMap
              nodeColor={(n) => TYPE_COLOR[(n.data as { node?: { device_type?: string } }).node?.device_type ?? ""] ?? "#4d5b70"}
              maskColor="rgba(13,17,23,0.85)"
              style={{ background: "#161d29" }}
            />
          </ReactFlow>
        </div>
      )}
    </div>
  );
}
