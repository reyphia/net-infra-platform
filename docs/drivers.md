# Vendor Drivers

## Interface

```python
class NetworkDeviceDriver(ABC):
    async def connect(self) -> None
    async def disconnect(self) -> None
    async def get_facts(self) -> DriverFacts
    async def get_interfaces(self) -> list[DriverInterface]
    async def get_vlans(self) -> list[DriverVLAN]
    async def get_neighbors(self) -> list[DriverNeighbor]
    async def get_config(self, source: str = "running") -> str
    async def execute(self, command: str) -> CommandResult
    async def apply_config(self, lines: list[str]) -> CommandResult
    async def save_config(self) -> CommandResult
```

All connections go through `InteractiveSSHSession`
(`app/drivers/base.py`), a real asyncssh interactive-shell wrapper with
prompt-pattern synchronization -- the same approach tools like Netmiko/
Scrapli use, implemented directly rather than adding another dependency.

## Implemented

| Driver | `driver_type` | Notes |
|---|---|---|
| Cisco IOS/IOS-XE | `cisco_ios` | enable mode, `terminal length 0`, real regex parsing of `show version`/`show interfaces`/`show vlan brief`/`show cdp neighbors detail`; `supports_semantic_rollback = True` |
| MikroTik RouterOS | `mikrotik_routeros` | `/export verbose`, `/interface`, `/ip address`, `/interface vlan`, `/ip neighbor` (MNDP); no separate startup config (RouterOS persists immediately) |
| Generic SSH | `generic_ssh` | `execute()` only; every structured method raises `NotImplementedByDriver` rather than guessing at unknown CLI grammar |

## Adding Juniper / Arista / Fortinet / Palo Alto / Aruba

1. Subclass `NetworkDeviceDriver`, following `cisco.py` or `mikrotik.py` as
   a template (prompt regex, per-command parsers).
2. Register the class in `app/drivers/factory.py`'s `_DRIVERS` dict.
3. Add real CLI-output fixtures under `backend/tests/fixtures/cli_output/`
   and a parsing test file (see `tests/unit/test_cisco_driver_parsing.py`).
4. Add at least one test against `tests/fixtures/fake_ssh_device.py`, the
   real in-process fake-SSH-device harness, to prove the interactive-shell
   plumbing (not just the regexes) works over an actual SSH session.

## Testing philosophy

No driver test requires real vendor hardware. Regex/parsing tests feed
captured (fixture) CLI output through the driver's parsing methods via a
monkeypatched `execute()`. Transport-level tests use a real asyncssh server
(`tests/fixtures/fake_ssh_device.py`) that speaks genuine SSH but has
scripted command responses -- this is the "mocked device" the project's
test plan calls for.
