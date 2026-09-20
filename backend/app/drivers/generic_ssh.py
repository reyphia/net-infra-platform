"""Generic SSH driver.

Used for devices where no vendor-specific parsing exists yet. Provides raw
command execution over a real SSH session but cannot structurally parse
interfaces/VLANs/neighbors/config -- those methods are explicitly
NOT IMPLEMENTED rather than guessing at a command syntax that may not exist
on the target device.
"""
from __future__ import annotations

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

_PROMPT_PATTERN = r"[\r\n].*[$#>]\s*$"


class NotImplementedByDriver(DriverCommandError):
    pass


class GenericSSHDriver(NetworkDeviceDriver):
    """Raw command execution only. Structured facts/interfaces/VLANs/neighbors
    are NOT IMPLEMENTED for arbitrary devices -- there is no reliable way to
    parse `show`-style output without knowing the vendor's CLI grammar."""

    driver_type = "generic_ssh"

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

    async def execute(self, command: str) -> CommandResult:
        if self._session is None:
            raise DriverCommandError("Driver is not connected")
        output = await self._session.send(command)
        lines = output.splitlines()
        if lines and command.strip() in lines[0]:
            lines = lines[1:]
        if lines:
            lines = lines[:-1]
        return CommandResult(command=command, output="\n".join(lines).strip(), success=True)

    async def get_facts(self) -> DriverFacts:
        return DriverFacts()  # NOT IMPLEMENTED: no generic way to parse arbitrary CLI banners into facts

    async def get_interfaces(self) -> list[DriverInterface]:
        raise NotImplementedByDriver("Interface parsing is NOT IMPLEMENTED for the generic SSH driver.")

    async def get_vlans(self) -> list[DriverVLAN]:
        raise NotImplementedByDriver("VLAN parsing is NOT IMPLEMENTED for the generic SSH driver.")

    async def get_neighbors(self) -> list[DriverNeighbor]:
        raise NotImplementedByDriver("Neighbor discovery is NOT IMPLEMENTED for the generic SSH driver.")

    async def get_config(self, source: str = "running") -> str:
        raise NotImplementedByDriver(
            "Configuration retrieval is NOT IMPLEMENTED for the generic SSH driver -- "
            "use `execute()` with a device-specific command if you know it."
        )

    async def apply_config(self, lines: list[str]) -> CommandResult:
        raise NotImplementedByDriver(
            "Structured configuration apply is NOT IMPLEMENTED for the generic SSH driver -- "
            "use `execute()` for one-off commands instead."
        )

    async def save_config(self) -> CommandResult:
        raise NotImplementedByDriver("Save is NOT IMPLEMENTED for the generic SSH driver.")
