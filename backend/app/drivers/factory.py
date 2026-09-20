from __future__ import annotations

from app.drivers.base import NetworkDeviceDriver, SSHCredential
from app.drivers.cisco import CiscoIOSDriver
from app.drivers.generic_ssh import GenericSSHDriver
from app.drivers.mikrotik import MikroTikRouterOSDriver

_DRIVERS: dict[str, type[NetworkDeviceDriver]] = {
    "cisco_ios": CiscoIOSDriver,
    "mikrotik_routeros": MikroTikRouterOSDriver,
    "generic_ssh": GenericSSHDriver,
}


class UnknownDriverError(ValueError):
    pass


def create_driver(
    driver_type: str,
    host: str,
    credential: SSHCredential,
    *,
    port: int = 22,
    connect_timeout: float = 8.0,
    command_timeout: float = 20.0,
    known_hosts_path: str | None = None,
    allow_insecure: bool = False,
) -> NetworkDeviceDriver:
    driver_cls = _DRIVERS.get(driver_type)
    if driver_cls is None:
        raise UnknownDriverError(
            f"No driver registered for '{driver_type}'. Supported: {sorted(_DRIVERS)}. "
            "Adding Juniper/Arista/Fortinet/Palo Alto/Aruba support means implementing "
            "NetworkDeviceDriver and registering it here -- see docs/drivers.md."
        )
    return driver_cls(
        host,
        credential,
        port=port,
        connect_timeout=connect_timeout,
        command_timeout=command_timeout,
        known_hosts_path=known_hosts_path,
        allow_insecure=allow_insecure,
    )


def available_driver_types() -> list[str]:
    return sorted(_DRIVERS)
