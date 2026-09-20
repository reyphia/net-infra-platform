# Discovery

## Mechanisms, and what each actually proves

| Source | What it does | What it proves |
|---|---|---|
| ARP (`app/discovery/arp.py`) | Reads the real OS neighbor table: `ip neighbor show` on Linux (falling back to `/proc/net/arp`), `arp -a` on Windows | The management host has an L2-resolved neighbor -- local segment only |
| ICMP (`app/discovery/icmp.py`) | Real `ping` subprocess (BSD-style `-c/-W` flags on Linux/macOS, `-n/-w` on Windows), real echo request/reply | Host responds to ICMP right now |
| TCP probe (`app/discovery/tcp_probe.py`) | Real TCP connect to SSH/Telnet/HTTPS/HTTP only -- never an arbitrary port range | A specific management service is listening |
| SNMP (`app/snmp/`) | Real SNMPv2c GET/WALK via pysnmp | Device answers SNMP; sysDescr/sysObjectID/interfaces available |
| LLDP/CDP (`app/snmp/lldp_cdp.py`) | Real SNMP walk of LLDP-MIB / CISCO-CDP-MIB | Direct, vendor-reported neighbor adjacency |

## Cross-platform discovery (Linux + Windows)

`app/discovery/arp.py` and `app/discovery/icmp.py` both detect the OS
(`platform.system()`) and switch command syntax and output parsing
accordingly -- there is no separate Windows build of the discovery engine,
the same code path branches internally. This is covered by unit tests using
captured real command output for both platforms
(`tests/unit/test_arp_parsing.py`, `tests/unit/test_icmp_cross_platform.py`),
so the Windows-specific regexes are verified without needing a Windows
machine to run the test suite itself -- only to run the *application*,
which is what `.github/workflows/release.yml`'s `windows-latest` job does.

## What's NOT implemented

- **SNMPv3** -- the credential model and `SNMPCredential.version` field exist,
  but `SNMPClient._auth_data()` raises `SNMPError` for anything other than
  `v2c`. See `app/snmp/client.py`.
- **IPv6 Neighbor Discovery** -- the ARP reader only parses IPv4 neighbor
  entries today.
- **Port scanning** -- deliberately absent. `tcp_probe.py` only ever probes
  the fixed `MANAGEMENT_PORTS` set (SSH/Telnet/HTTPS/HTTP).

## Scope safety

`app/discovery/scope.py` requires an explicit list of CIDRs (`DiscoveryScope`
raises `InvalidScopeError` on an empty list) and caps any single CIDR at
65,536 addresses, so a mistyped `/8` can't silently queue 16 million probes.
There is no default scope anywhere in the codebase.

## Concurrency

Every discovery job uses a bounded `asyncio.Semaphore` (default 50,
operator-configurable per job) -- see `run_discovery()` in
`app/discovery/engine.py`. Per-host timeout and retry count are also
per-job settings, never hardcoded.

## Known packaging issue this project worked around

`pysnmp` >= 7.0 (the current PyPI package) has a broken `hlapi.v3arch.asyncio`
import chain against current `pyasn1` releases (confirmed by direct testing,
not assumption: it references `pyasn1.compat.octets`, removed since
`pyasn1` 0.5, and `pysnmp.entity.config.USM_AUTH_NONE`, which doesn't exist
in that build). This project pins `pysnmp==6.1.4` + `pyasn1<0.5.0` and uses
the `hlapi.asyncio` (camelCase `getCmd`/`bulkCmd`) API instead, which was
verified end-to-end against a real UDP listener. If upstream fixes this,
revisiting the pin is a reasonable future improvement.
