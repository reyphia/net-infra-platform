"""MikroTik RouterOS driver.

RouterOS's CLI is structurally different from Cisco IOS (path-based menus,
`print` verbs, `/export` for configuration) so this is a separate real
parser, not a thin subclass of the Cisco driver.
"""
from __future__ import annotations

import re

from app.drivers.base import (
    CommandResult,
    DriverCommandError,
    DriverFacts,
    DriverInterface,
    DriverNeighbor,
    DriverVLAN,
    InteractiveSSHSession,
    NetworkDeviceDriver,
)

_PROMPT_PATTERN = r"[\r\n]\[\S*@?\S*\]\s*[/\w]*>\s*$"


class MikroTikRouterOSDriver(NetworkDeviceDriver):
    driver_type = "mikrotik_routeros"

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)  # type: ignore[arg-type]
        self._session: InteractiveSSHSession | None = None

    async def connect(self) -> None:
        await super().connect()
        self._session = InteractiveSSHSession(
            self.connection, command_timeout=self.command_timeout, prompt_pattern=_PROMPT_PATTERN
        )
        await self._session.start()

    async def disconnect(self) -> None:
        if self._session is not None:
            await self._session.close()
            self._session = None
        await super().disconnect()

    def _require_session(self) -> InteractiveSSHSession:
        if self._session is None:
            raise DriverCommandError("Driver is not connected")
        return self._session

    @staticmethod
    def _strip_echo(command: str, output: str) -> str:
        lines = output.splitlines()
        if lines and command.strip() in lines[0]:
            lines = lines[1:]
        if lines and re.match(r"^\[\S*@?\S*\]\s*[/\w]*>\s*$", lines[-1].strip()):
            lines = lines[:-1]
        return "\n".join(lines).strip("\r\n")

    async def execute(self, command: str) -> CommandResult:
        session = self._require_session()
        try:
            raw = await session.send(command)
        except DriverCommandError as exc:
            return CommandResult(command=command, output="", success=False, error=str(exc))
        output = self._strip_echo(command, raw)
        error = "bad command name" in output.lower() or "syntax error" in output.lower()
        return CommandResult(
            command=command, output=output, success=not error, error="RouterOS reported a CLI error" if error else None
        )

    async def get_facts(self) -> DriverFacts:
        identity = await self.execute("/system identity print")
        hostname = None
        if m := re.search(r"name:\s*(\S+)", identity.output):
            hostname = m.group(1)

        resource = await self.execute("/system resource print")
        model = None
        os_version = None
        uptime_seconds = None
        if m := re.search(r"board-name:\s*(\S+)", resource.output):
            model = m.group(1)
        if m := re.search(r"version:\s*(\S+)", resource.output):
            os_version = m.group(1)
        if m := re.search(r"uptime:\s*(\S+)", resource.output):
            uptime_seconds = _parse_routeros_uptime(m.group(1))

        routerboard = await self.execute("/system routerboard print")
        serial = None
        if m := re.search(r"serial-number:\s*(\S+)", routerboard.output):
            serial = m.group(1)

        return DriverFacts(
            hostname=hostname,
            vendor="MikroTik",
            model=model,
            os_name="RouterOS",
            os_version=os_version,
            uptime_seconds=uptime_seconds,
            serial_number=serial,
        )

    async def get_interfaces(self) -> list[DriverInterface]:
        result = await self.execute("/interface print detail without-paging")
        interfaces: list[DriverInterface] = []
        for block in re.split(r"\n(?=\s*\d+\s+)", result.output):
            name_match = re.search(r"name=\"?([\w\-./]+)\"?", block)
            if not name_match:
                continue
            disabled = "disabled=yes" in block
            running = "running" in block or "R " in block[:6]
            mac_match = re.search(r"mac-address=([0-9A-Fa-f:]+)", block)
            comment_match = re.search(r'comment="([^"]*)"', block)
            interfaces.append(
                DriverInterface(
                    name=name_match.group(1),
                    description=comment_match.group(1) if comment_match else None,
                    admin_state="down" if disabled else "up",
                    oper_state="up" if running else "down",
                    mac_address=mac_match.group(1) if mac_match else None,
                )
            )

        addr_result = await self.execute("/ip address print detail without-paging")
        for block in re.split(r"\n(?=\s*\d+\s+)", addr_result.output):
            iface_match = re.search(r"interface=([\w\-./]+)", block)
            addr_match = re.search(r"address=(\d+\.\d+\.\d+\.\d+/\d+)", block)
            if iface_match and addr_match:
                for iface in interfaces:
                    if iface.name == iface_match.group(1):
                        iface.ipv4_addresses.append(addr_match.group(1))
        return interfaces

    async def get_vlans(self) -> list[DriverVLAN]:
        result = await self.execute("/interface vlan print detail without-paging")
        vlans: list[DriverVLAN] = []
        for block in re.split(r"\n(?=\s*\d+\s+)", result.output):
            vid_match = re.search(r"vlan-id=(\d+)", block)
            name_match = re.search(r"name=\"?([\w\-./]+)\"?", block)
            if vid_match:
                vlans.append(
                    DriverVLAN(
                        vlan_id=int(vid_match.group(1)),
                        name=name_match.group(1) if name_match else None,
                        status="disabled" if "disabled=yes" in block else "active",
                    )
                )
        return vlans

    async def get_neighbors(self) -> list[DriverNeighbor]:
        """RouterOS's own neighbor-discovery protocol (MNDP, plus optional
        LLDP/CDP listening if enabled) via `/ip neighbor print`."""
        result = await self.execute("/ip neighbor print detail without-paging")
        neighbors: list[DriverNeighbor] = []
        for block in re.split(r"\n(?=\s*\d+\s+)", result.output):
            iface_match = re.search(r"interface=([\w\-./]+)", block)
            identity_match = re.search(r"identity=\"?([\w\-./]+)\"?", block)
            address_match = re.search(r"address=(\d+\.\d+\.\d+\.\d+)", block)
            if iface_match and identity_match:
                neighbors.append(
                    DriverNeighbor(
                        local_interface=iface_match.group(1),
                        remote_hostname=identity_match.group(1),
                        remote_interface=None,
                        remote_management_address=address_match.group(1) if address_match else None,
                        source="MNDP",
                    )
                )
        return neighbors

    async def get_config(self, source: str = "running") -> str:
        if source != "running":
            raise DriverCommandError(
                "RouterOS does not expose a separate startup configuration; "
                "the active configuration IS the persisted configuration."
            )
        result = await self.execute("/export verbose")
        if not result.success:
            raise DriverCommandError(f"Failed to export configuration: {result.error}")
        return result.output

    async def apply_config(self, lines: list[str]) -> CommandResult:
        session = self._require_session()
        transcript: list[str] = []
        had_error = False
        for line in lines:
            output = await session.send(line)
            transcript.append(output)
            if "bad command" in output.lower() or "syntax error" in output.lower() or "failure:" in output.lower():
                had_error = True
        full_output = "\n".join(transcript)
        return CommandResult(
            command="\n".join(lines),
            output=full_output,
            success=not had_error,
            error="RouterOS rejected one or more lines; see output" if had_error else None,
        )

    async def save_config(self) -> CommandResult:
        # RouterOS applies configuration immediately and persists it to flash
        # automatically -- there is no separate "write memory" step like IOS.
        return CommandResult(
            command="(implicit)",
            output="RouterOS persists configuration changes immediately; no explicit save step exists.",
            success=True,
        )


def _parse_routeros_uptime(text: str) -> int | None:
    # e.g. "3w4d5h6m7s"
    units = {"w": 7 * 86400, "d": 86400, "h": 3600, "m": 60, "s": 1}
    total = 0
    found = False
    for value, unit in re.findall(r"(\d+)([wdhms])", text):
        total += int(value) * units[unit]
        found = True
    return total if found else None
