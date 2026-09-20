from pathlib import Path

import pytest

from app.drivers.base import CommandResult, SSHCredential
from app.drivers.mikrotik import MikroTikRouterOSDriver

FIXTURES = Path(__file__).parent.parent / "fixtures" / "cli_output"


def _fixture(name: str) -> str:
    return (FIXTURES / name).read_text()


@pytest.fixture()
def driver(monkeypatch):
    d = MikroTikRouterOSDriver("10.10.0.1", SSHCredential(username="admin", password="x"))

    canned = {
        "/system identity print": _fixture("routeros_identity.txt"),
        "/system resource print": _fixture("routeros_resource.txt"),
        "/system routerboard print": _fixture("routeros_routerboard.txt"),
        "/interface print detail without-paging": _fixture("routeros_interfaces.txt"),
        "/ip address print detail without-paging": _fixture("routeros_addresses.txt"),
        "/interface vlan print detail without-paging": _fixture("routeros_vlans.txt"),
        "/ip neighbor print detail without-paging": _fixture("routeros_neighbors.txt"),
    }

    async def fake_execute(command: str) -> CommandResult:
        return CommandResult(command=command, output=canned.get(command, ""), success=True)

    monkeypatch.setattr(d, "execute", fake_execute)
    return d


@pytest.mark.asyncio
async def test_get_facts(driver):
    facts = await driver.get_facts()
    assert facts.hostname == "MT-EDGE01"
    assert facts.vendor == "MikroTik"
    assert facts.model == "CHR"
    assert facts.os_version == "7.15"
    assert facts.serial_number == "ABCD1234EFGH"
    assert facts.uptime_seconds == (3 * 7 * 86400 + 4 * 86400 + 5 * 3600 + 6 * 60 + 7)


@pytest.mark.asyncio
async def test_get_interfaces_with_addresses(driver):
    interfaces = await driver.get_interfaces()
    assert len(interfaces) == 2
    ether1 = next(i for i in interfaces if i.name == "ether1")
    assert ether1.admin_state == "up"
    assert ether1.description == "WAN uplink"
    assert "203.0.113.5/30" in ether1.ipv4_addresses

    ether2 = next(i for i in interfaces if i.name == "ether2")
    assert ether2.admin_state == "down"


@pytest.mark.asyncio
async def test_get_vlans(driver):
    vlans = await driver.get_vlans()
    assert len(vlans) == 1
    assert vlans[0].vlan_id == 20
    assert vlans[0].name == "vlan20-voice"


@pytest.mark.asyncio
async def test_get_neighbors(driver):
    neighbors = await driver.get_neighbors()
    assert len(neighbors) == 1
    assert neighbors[0].remote_hostname == "CORE-SW01"
    assert neighbors[0].local_interface == "ether1"
    assert neighbors[0].source == "MNDP"
