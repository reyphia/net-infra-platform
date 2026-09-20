"""A real SSH server (real asyncssh transport, real TCP socket, real auth)
that impersonates a network device's CLI for testing.

This is the "mocked device" the test plan calls for: the SSH *protocol*
layer is completely real (this is exactly what our drivers talk to in
production); only the remote device's command responses are scripted.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import asyncssh


@dataclass
class FakeDeviceScript:
    prompt: str  # e.g. "CORE-SW01#"
    responses: dict[str, str] = field(default_factory=dict)  # command -> output (no prompt, no echo)
    username: str = "testadmin"
    password: str = "testpass123"


class _FakeServer(asyncssh.SSHServer):
    def __init__(self, script: FakeDeviceScript) -> None:
        self.script = script

    def connection_made(self, conn: asyncssh.SSHServerConnection) -> None:
        self._conn = conn

    def begin_auth(self, username: str) -> bool:
        return True  # require password auth

    def password_auth_supported(self) -> bool:
        return True

    def validate_password(self, username: str, password: str) -> bool:
        return username == self.script.username and password == self.script.password


def _make_process_handler(script: FakeDeviceScript):
    async def handle_client(process: asyncssh.SSHServerProcess) -> None:
        process.stdout.write(f"\r\n{script.prompt} ")
        async for line in process.stdin:
            command = line.rstrip("\r\n")
            process.stdout.write(f"{command}\r\n")  # real terminals echo input
            output = script.responses.get(command)
            if output is None:
                process.stdout.write("% Invalid input detected\r\n")
            elif output:
                process.stdout.write(output.rstrip("\n") + "\r\n")
            process.stdout.write(f"{script.prompt} ")
        process.exit(0)

    return handle_client


async def start_fake_device_server(script: FakeDeviceScript, host_key_path: str) -> asyncssh.SSHAcceptor:
    return await asyncssh.create_server(
        lambda: _FakeServer(script),
        host="127.0.0.1",
        port=0,
        server_host_keys=[host_key_path],
        process_factory=_make_process_handler(script),
        encoding="utf-8",
    )
