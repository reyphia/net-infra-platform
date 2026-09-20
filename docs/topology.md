# Topology

## Model

```
Device --- Connection --- Device
```

A `Connection` (`app/db/models.py`) stores `source_device_id`,
`destination_device_id`, per-side interface names, a `discovery_methods`
list, and a single merged `confidence` score. There is no predefined or
seeded topology anywhere -- every edge is written by
`discovery/engine.py::_discover_topology_edges()` based on real LLDP/CDP
SNMP walks correlated against already-known devices by management IP or
system name.

## Confidence

| Source | Confidence |
|---|---|
| LLDP | 0.98 |
| CDP | 0.90 |

Merging is by device pair (`_merge_connection`): if a second discovery
mechanism corroborates an existing edge, its confidence is added to
`discovery_methods` and the edge's confidence is raised to
`max(existing, new)` rather than creating a duplicate edge.

## What's NOT implemented

- **MAC-table correlation** and **ARP-based inference** edges
  (`DiscoverySource.MAC_TABLE` / `INFERENCE` exist as enum values for future
  use but nothing currently populates a `Connection` from them). Today's
  topology is LLDP/CDP-only, which is direct evidence, not inference --
  the "lower-confidence inferred link" tier described in the product spec
  is architected for (the `confidence` field and `DiscoverySource` enum
  support it) but not yet populated by any discovery routine.
- **VLAN-aware filtering** of the topology graph (device-type/vendor/
  online-only filters are implemented in `topology/service.py` and the UI;
  VLAN filtering is not, since VLAN membership isn't consistently captured
  per-connection yet).

## Why React Flow

See `docs/architecture.md`.
