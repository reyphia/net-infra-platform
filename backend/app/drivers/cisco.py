"""Cisco IOS / IOS-XE driver.

Talks to a real device over SSH using an interactive shell (matching how a
human operator's terminal session behaves): enters enable mode if an enable
password is configured, disables output paging, and parses real `show`
command output. No output is fabricated -- if a `show` command errors or a
section is absent, the corresponding fields are left empty/None.
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

_PROMPT_PATTERN = r"[\r\n][\w\-.]+[#>]\s*$"


class CiscoIOSDriver(NetworkDeviceDriver):
    driver_type = "cisco_ios"
    supports_semantic_rollback = True

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)  # type: ignore[arg-type]
        self._session: InteractiveSSHSession | None = None
        self._in_enable_mode = False

    async def connect(self) -> None:
        await super().connect()
        self._session = InteractiveSSHSession(
            self.connection, command_timeout=self.command_timeout, prompt_pattern=_PROMPT_PATTERN
        )
        await self._session.start()
        await self._session.send("terminal length 0")

        if self.credential.enable_password:
            output = await self._session.send("enable")
            if "password" in output.lower():
                output = await self._session.send(self.credential.enable_password)
            self._in_enable_mode = output.rstrip().endswith("#")

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
        if lines and re.match(r"^[\w\-.]+[#>]\s*$", lines[-1].strip()):
            lines = lines[:-1]
        return "\n".join(lines).strip("\r\n")

    async def execute(self, command: str) -> CommandResult:
        session = self._require_session()
        try:
            raw = await session.send(command)
        except DriverCommandError as exc:
            return CommandResult(command=command, output="", success=False, error=str(exc))
        output = self._strip_echo(command, raw)
        error = None
        if re.search(r"% *Invalid input|% *Incomplete command|% *Ambiguous command", output, re.IGNORECASE):
            error = "Device reported a CLI syntax error"
        return CommandResult(command=command, output=output, success=error is None, error=error)

    async def get_facts(self) -> DriverFacts:
        version_result = await self.execute("show version")
        text = version_result.output

        hostname = None
        if m := re.search(r"^(\S+)\s+uptime is", text, re.MULTILINE):
            hostname = m.group(1)

        model = None
        if m := re.search(r"[Cc]isco\s+(\S+[\w-]*)\s*\(.+?\)\s*processor", text):
            model = m.group(1)

        os_version = None
        if m := re.search(r"Version\s+([\w.()]+)", text):
            os_version = m.group(1)

        uptime_seconds = None
        if m := re.search(r"uptime is (.+)", text):
            uptime_seconds = _parse_cisco_uptime(m.group(1))

        serial = None
        if m := re.search(r"[Ss]ystem serial number\s*:\s*(\S+)", text):
            serial = m.group(1)

        return DriverFacts(
            hostname=hostname,
            vendor="Cisco",
            model=model,
            os_name="IOS-XE" if "IOS-XE" in text else "IOS",
            os_version=os_version,
            uptime_seconds=uptime_seconds,
            serial_number=serial,
        )

    async def get_interfaces(self) -> list[DriverInterface]:
        result = await self.execute("show interfaces")
        interfaces: list[DriverInterface] = []
        blocks = re.split(r"\n(?=\S)", result.output)
        for block in blocks:
            header = re.match(
                r"^(\S+) is (administratively down|up|down),\s*line protocol is (up|down)", block
            )
            if not header:
                continue
            name, admin_raw, oper = header.groups()
            admin = "down" if "administratively down" in admin_raw else "up"

            mac = None
            if m := re.search(r"address is ([0-9a-fA-F.]+)", block):
                mac = m.group(1)
            descr = None
            if m := re.search(r"Description:\s*(.+)", block):
                descr = m.group(1).strip()
            speed = None
            if m := re.search(r"BW\s+(\d+)\s*Kbit", block):
                speed = int(int(m.group(1)) / 1000)
            duplex = None
            if m := re.search(r"(Full|Half)-duplex", block):
                duplex = m.group(1).lower()
            ipv4 = re.findall(r"Internet address is (\d+\.\d+\.\d+\.\d+/\d+)", block)

            interfaces.append(
                DriverInterface(
                    name=name,
                    description=descr,
                    admin_state=admin,
                    oper_state=oper,
                    mac_address=mac,
                    ipv4_addresses=ipv4,
                    speed_mbps=speed,
                    duplex=duplex,
                )
            )
        return interfaces

    async def get_vlans(self) -> list[DriverVLAN]:
        result = await self.execute("show vlan brief")
        vlans: list[DriverVLAN] = []
        for line in result.output.splitlines():
            m = re.match(r"^(\d+)\s+(\S+)\s+(active|suspended|act/unsup)", line)
            if m:
                vlans.append(DriverVLAN(vlan_id=int(m.group(1)), name=m.group(2), status=m.group(3)))
        return vlans

    async def get_neighbors(self) -> list[DriverNeighbor]:
        result = await self.execute("show cdp neighbors detail")
        neighbors: list[DriverNeighbor] = []
        for entry in result.output.split("-------------------------"):
            if "Device ID" not in entry:
                continue
            hostname = None
            if m := re.search(r"Device ID:\s*(\S+)", entry):
                hostname = m.group(1)
            local_if = None
            remote_if = None
            if m := re.search(r"Interface:\s*(\S+),\s*Port ID \(outgoing port\):\s*(\S+)", entry):
                local_if, remote_if = m.group(1), m.group(2)
            mgmt_ip = None
            if m := re.search(r"IP address:\s*(\d+\.\d+\.\d+\.\d+)", entry):
                mgmt_ip = m.group(1)
            if hostname and local_if:
                neighbors.append(
                    DriverNeighbor(
                        local_interface=local_if,
                        remote_hostname=hostname,
                        remote_interface=remote_if,
                        remote_management_address=mgmt_ip,
                        source="CDP",
                    )
                )
        return neighbors

    async def get_config(self, source: str = "running") -> str:
        command = "show running-config" if source == "running" else "show startup-config"
        result = await self.execute(command)
        if not result.success:
            raise DriverCommandError(f"Failed to retrieve {source} config: {result.error}")
        return result.output

    async def apply_config(self, lines: list[str]) -> CommandResult:
        session = self._require_session()
        transcript: list[str] = []
        try:
            transcript.append(await session.send("configure terminal"))
            for line in lines:
                transcript.append(await session.send(line))
            transcript.append(await session.send("end"))
        except DriverCommandError as exc:
            return CommandResult(command="\n".join(lines), output="\n".join(transcript), success=False, error=str(exc))

        full_output = "\n".join(transcript)
        error = None
        if re.search(r"% *Invalid input|% *Incomplete command", full_output, re.IGNORECASE):
            error = "Device rejected one or more configuration lines; see output"
        return CommandResult(command="\n".join(lines), output=full_output, success=error is None, error=error)

    async def save_config(self) -> CommandResult:
        result = await self.execute("write memory")
        if not result.success and "[OK]" in result.output:
            result.success = True
            result.error = None
        return result


_UPTIME_UNITS = {"year": 365 * 86400, "week": 7 * 86400, "day": 86400, "hour": 3600, "minute": 60}


def _parse_cisco_uptime(text: str) -> int | None:
    total = 0
    found = False
    for m in re.finditer(r"(\d+)\s+(year|week|day|hour|minute)s?", text):
        total += int(m.group(1)) * _UPTIME_UNITS[m.group(2)]
        found = True
    return total if found else None
