"""Common vendor driver interface and the shared interactive-SSH plumbing
that concrete drivers (Cisco IOS, MikroTik RouterOS, generic SSH) build on.

Real asyncssh connections are made here -- there is no mock transport in the
production code path. Host-key verification is on by default; disabling it
requires `SSH_ALLOW_INSECURE_LAB_MODE=true` to be set explicitly (see
docs/security.md), and every insecure connection is flagged in its audit
record.
"""
from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

import asyncssh

logger = logging.getLogger("app.drivers")


class DriverConnectionError(RuntimeError):
    """Raised when an SSH connection cannot be established. Carries a
    structured `reason` so the API layer can surface a real cause instead of
    a generic 'something went wrong'."""

    def __init__(self, message: str, *, reason: str, host: str) -> None:
        super().__init__(message)
        self.reason = reason
        self.host = host


class DriverCommandError(RuntimeError):
    pass


@dataclass
class SSHCredential:
    username: str
    password: str | None = None
    enable_password: str | None = None
    private_key: str | None = None


@dataclass
class DriverFacts:
    hostname: str | None = None
    vendor: str | None = None
    model: str | None = None
    os_name: str | None = None
    os_version: str | None = None
    uptime_seconds: int | None = None
    serial_number: str | None = None


@dataclass
class DriverInterface:
    name: str
    description: str | None = None
    admin_state: str | None = None
    oper_state: str | None = None
    mac_address: str | None = None
    ipv4_addresses: list[str] = field(default_factory=list)
    vlan: str | None = None
    speed_mbps: int | None = None
    duplex: str | None = None


@dataclass
class DriverVLAN:
    vlan_id: int
    name: str | None = None
    status: str | None = None


@dataclass
class DriverNeighbor:
    local_interface: str
    remote_hostname: str | None
    remote_interface: str | None
    remote_management_address: str | None = None
    source: str = "CLI"


@dataclass
class CommandResult:
    command: str
    output: str
    success: bool
    error: str | None = None


class InteractiveSSHSession:
    """Wraps a single asyncssh interactive shell channel and provides
    prompt-synchronized command execution -- the same pattern real CLI
    automation tools (Netmiko, Scrapli) use, implemented directly on asyncssh
    so the whole stack has no hidden dependency doing the actual I/O.
    """

    def __init__(
        self,
        connection: asyncssh.SSHClientConnection,
        *,
        command_timeout: float,
        prompt_pattern: str,
    ) -> None:
        self._conn = connection
        self._process: asyncssh.SSHClientProcess | None = None
        self._command_timeout = command_timeout
        self._prompt_pattern = prompt_pattern
        self._buffer = ""

    async def start(self) -> None:
        self._process = await self._conn.create_process(term_type="vt100", term_size=(512, 24))
        await self._read_until_prompt(initial=True)

    async def _read_until_prompt(self, initial: bool = False) -> str:
        assert self._process is not None
        import re

        pattern = re.compile(self._prompt_pattern, re.MULTILINE)
        collected = ""
        try:
            async with asyncio.timeout(self._command_timeout):
                while True:
                    chunk = await self._process.stdout.read(4096)
                    if not chunk:
                        break
                    collected += chunk
                    if pattern.search(collected):
                        break
        except TimeoutError as exc:
            raise DriverCommandError(
                f"Timed out waiting for device prompt after {self._command_timeout}s. "
                f"Partial output: {collected[-500:]!r}"
            ) from exc
        return collected

    async def send(self, line: str) -> str:
        assert self._process is not None
        self._process.stdin.write(line + "\n")
        output = await self._read_until_prompt()
        return output

    async def close(self) -> None:
        if self._process is not None:
            self._process.stdin.write_eof()
            self._process.close()


class NetworkDeviceDriver(ABC):
    """Abstract driver every vendor implementation must satisfy."""

    driver_type: str = "unsupported"
    # Whether apply_config()'s effect can be reliably reversed by negating the
    # exact lines it added/removed (true for Cisco IOS's "no <command>"
    # convention). MikroTik/RouterOS and the generic driver do not support
    # this generically, so rollback for them is UNAVAILABLE rather than
    # attempted-and-assumed-to-work.
    supports_semantic_rollback: bool = False

    def __init__(
        self,
        host: str,
        credential: SSHCredential,
        *,
        port: int = 22,
        connect_timeout: float = 8.0,
        command_timeout: float = 20.0,
        known_hosts_path: str | None = None,
        allow_insecure: bool = False,
    ) -> None:
        self.host = host
        self.credential = credential
        self.port = port
        self.connect_timeout = connect_timeout
        self.command_timeout = command_timeout
        self.known_hosts_path = known_hosts_path
        self.allow_insecure = allow_insecure
        self._connection: asyncssh.SSHClientConnection | None = None
        self.used_insecure_host_key_verification = False

    async def connect(self) -> None:
        known_hosts: asyncssh.SSHKnownHosts | None | object
        if self.allow_insecure:
            known_hosts = None  # explicitly opted into no host-key verification (lab mode only)
            self.used_insecure_host_key_verification = True
            logger.warning("INSECURE: host-key verification disabled for %s (lab mode)", self.host)
        else:
            known_hosts = (self.known_hosts_path,) if self.known_hosts_path else asyncssh.SSHKnownHosts(None)
            if self.known_hosts_path:
                from app.core.fsutil import ensure_known_hosts_file

                ensure_known_hosts_file(self.known_hosts_path)

        try:
            self._connection = await asyncio.wait_for(
                asyncssh.connect(
                    self.host,
                    port=self.port,
                    username=self.credential.username,
                    password=self.credential.password,
                    client_keys=[self.credential.private_key] if self.credential.private_key else None,
                    known_hosts=known_hosts,
                ),
                timeout=self.connect_timeout,
            )
        except TimeoutError as exc:
            raise DriverConnectionError(
                f"Connection to {self.host}:{self.port} timed out after {self.connect_timeout}s",
                reason="timeout",
                host=self.host,
            ) from exc
        except asyncssh.HostKeyNotVerifiable as exc:
            raise DriverConnectionError(
                f"Host key for {self.host} is not in the known_hosts store and could not be verified. "
                "Connect once interactively to trust it, or enable lab mode explicitly if this is a lab.",
                reason="host_key_unverified",
                host=self.host,
            ) from exc
        except asyncssh.PermissionDenied as exc:
            raise DriverConnectionError(
                f"Authentication to {self.host} was rejected (bad username/password/key).",
                reason="auth_failed",
                host=self.host,
            ) from exc
        except (OSError, asyncssh.Error) as exc:
            raise DriverConnectionError(f"SSH connection to {self.host} failed: {exc}", reason="connection_error", host=self.host) from exc

    async def disconnect(self) -> None:
        if self._connection is not None:
            self._connection.close()
            await self._connection.wait_closed()
            self._connection = None

    @property
    def connection(self) -> asyncssh.SSHClientConnection:
        if self._connection is None:
            raise DriverConnectionError(f"Not connected to {self.host}", reason="not_connected", host=self.host)
        return self._connection

    # -- capabilities every concrete driver must implement --
    @abstractmethod
    async def get_facts(self) -> DriverFacts: ...

    @abstractmethod
    async def get_interfaces(self) -> list[DriverInterface]: ...

    @abstractmethod
    async def get_vlans(self) -> list[DriverVLAN]: ...

    @abstractmethod
    async def get_neighbors(self) -> list[DriverNeighbor]: ...

    @abstractmethod
    async def get_config(self, source: str = "running") -> str: ...

    @abstractmethod
    async def execute(self, command: str) -> CommandResult: ...

    @abstractmethod
    async def apply_config(self, lines: list[str]) -> CommandResult: ...

    @abstractmethod
    async def save_config(self) -> CommandResult: ...

    async def __aenter__(self) -> NetworkDeviceDriver:
        await self.connect()
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.disconnect()
