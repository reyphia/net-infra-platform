# Changelog

## [0.1.0] - 2026-09-19

Initial public release.

### Added
- **Cross-platform discovery**: `app/discovery/arp.py` and `icmp.py` now
  detect the OS and use the correct command syntax/parser for both Linux
  (`ip neighbor` / `/proc/net/arp`, BSD-style `ping -c/-W`) and Windows
  (`arp -a`, `ping -n/-w`), covered by unit tests against captured real
  output from both platforms.
- **Standalone executable packaging**: `backend/run.py` +
  `backend/net-infra-platform.spec` (PyInstaller) bundle the backend and
  built frontend into a single double-click executable with first-run key
  generation and auto browser-launch. `app/main.py` now optionally serves
  the built frontend (with SPA-fallback routing) from the same process.
- **Release automation**: `scripts/build_release_linux.sh` and
  `scripts/build_release_windows.ps1` (+ a `.bat` double-click wrapper)
  build, test-gate, and package a release for each platform;
  `.github/workflows/release.yml` runs both on real `ubuntu-latest` /
  `windows-latest` GitHub Actions runners on every `vX.Y.Z` tag push and
  publishes the results as a GitHub Release.
- Discovery engine: ARP/ICMP local discovery, targeted TCP management-port
  probing, SNMPv2c facts and interfaces, LLDP-MIB and CISCO-CDP-MIB neighbor
  discovery, bounded-concurrency async orchestration, explicit CIDR scoping.
- Multi-signal device identification with explicit confidence scoring.
- Management-accessibility model distinguishing discovered / identified /
  monitorable / remotely-manageable / configurable devices, including
  explicit console-only handling.
- Topology engine building a graph purely from observed evidence, with
  per-edge confidence and source merging.
- Vendor driver architecture (`NetworkDeviceDriver`) with real Cisco IOS/
  IOS-XE and MikroTik RouterOS SSH drivers (asyncssh-based), plus a generic
  SSH driver with explicitly NOT IMPLEMENTED structured parsing.
- Real-time SSH terminal over WebSocket.
- Configuration retrieval, hashed/metadata'd backups, secret sanitization for
  display, and a semantic (block-level, not just line-diff) configuration
  diff engine with categorization.
- Full change-management workflow: PLAN -> VALIDATE -> PREVIEW -> APPLY ->
  VERIFY, with a Cisco-only best-effort semantic ROLLBACK and honest
  UNAVAILABLE/FAILED/PARTIAL/SUCCESS reporting for other drivers.
- Encrypted credential profiles (Fernet), never returned by the API.
- Full audit trail with secret redaction.
- SNMP/ICMP-based health monitoring; never fabricates unavailable metrics.
- FastAPI REST API with OpenAPI docs; React + TypeScript frontend
  (React Flow topology, xterm.js terminal).
- Docker Compose, GitHub Actions CI (pytest/ruff/mypy + npm lint/typecheck/
  build), pytest suite including a real in-process fake-SSH-device
  integration harness and real-transport SNMP tests.

### Known limitations (see README for the full list)
- SNMPv3 not implemented.
- Discovery job cancellation is not cooperative mid-batch.
- Rollback is Cisco-IOS-only.
- Console-server-mediated management is architected for but not implemented.
