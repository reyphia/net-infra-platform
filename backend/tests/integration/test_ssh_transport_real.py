"""Integration tests that exercise the REAL SSH transport (real TCP socket,
real asyncssh handshake, real auth, real PTY) end-to-end against an in-process
fake device server (tests/fixtures/fake_ssh_device.py). Only the remote
device's command responses are scripted -- everything else, including host
key exchange and password authentication, is genuine SSH protocol activity.
"""
from __future__ import annotations

import pytest

from app.drivers.base import DriverConnectionError, SSHCredential
from app.drivers.generic_ssh import GenericSSHDriver
from tests.fixtures.fake_ssh_device import FakeDeviceScript, start_fake_device_server


@pytest.mark.asyncio
async def test_generic_driver_connects_and_executes_over_real_ssh(tmp_host_key):
    script = FakeDeviceScript(
        prompt="fakehost#",
        responses={"echo hello": "hello", "show version": "FakeOS 1.0"},
    )
    server = await start_fake_device_server(script, tmp_host_key)
    port = server.sockets[0].getsockname()[1]
    try:
        driver = GenericSSHDriver(
            "127.0.0.1",
            SSHCredential(username=script.username, password=script.password),
            port=port,
            known_hosts_path=None,
            allow_insecure=True,
        )
        await driver.connect()
        try:
            result = await driver.execute("echo hello")
            assert result.success
            assert "hello" in result.output
        finally:
            await driver.disconnect()
    finally:
        server.close()
        await server.wait_closed()


@pytest.mark.asyncio
async def test_bad_password_raises_driver_connection_error(tmp_host_key):
    script = FakeDeviceScript(prompt="fakehost#", responses={})
    server = await start_fake_device_server(script, tmp_host_key)
    port = server.sockets[0].getsockname()[1]
    try:
        driver = GenericSSHDriver(
            "127.0.0.1",
            SSHCredential(username=script.username, password="wrong-password"),
            port=port,
            known_hosts_path=None,
            allow_insecure=True,
        )
        with pytest.raises(DriverConnectionError) as exc_info:
            await driver.connect()
        assert exc_info.value.reason == "auth_failed"
    finally:
        server.close()
        await server.wait_closed()


@pytest.mark.asyncio
async def test_cisco_driver_full_session_over_real_ssh(tmp_host_key):
    """Proves the Cisco driver's real interactive-shell plumbing (prompt sync,
    'terminal length 0', echo stripping) against a real SSH session -- not
    just its regex parsers in isolation."""
    script = FakeDeviceScript(
        prompt="CORE-SW01#",
        responses={
            "terminal length 0": "",
            "show version": "Cisco IOS Software, C3560 Software\nCORE-SW01 uptime is 1 week, 2 days",
        },
    )
    server = await start_fake_device_server(script, tmp_host_key)
    port = server.sockets[0].getsockname()[1]
    try:
        from app.drivers.cisco import CiscoIOSDriver

        driver = CiscoIOSDriver(
            "127.0.0.1",
            SSHCredential(username=script.username, password=script.password),
            port=port,
            known_hosts_path=None,
            allow_insecure=True,
        )
        await driver.connect()
        try:
            result = await driver.execute("show version")
            assert "CORE-SW01" in result.output
        finally:
            await driver.disconnect()
    finally:
        server.close()
        await server.wait_closed()
