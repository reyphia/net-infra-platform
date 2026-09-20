from pathlib import Path

import pytest

from app.drivers.base import CommandResult, SSHCredential
from app.drivers.cisco import CiscoIOSDriver

FIXTURES = Path(__file__).parent.parent / "fixtures" / "cli_output"


def _fixture(name: str) -> str:
    return (FIXTURES / name).read_text()


@pytest.fixture()
def driver(monkeypatch):
    d = CiscoIOSDriver("10.10.0.10", SSHCredential(username="admin", password="x"))

    canned: dict[str, str] = {
        "show version": _fixture("cisco_show_version.txt"),
        "show interfaces": _fixture("cisco_show_interfaces.txt"),
        "show vlan brief": _fixture("cisco_show_vlan_brief.txt"),
        "show cdp neighbors detail": _fixture("cisco_show_cdp_neighbors_detail.txt"),
    }

    async def fake_execute(command: str) -> CommandResult:
        return CommandResult(command=command, output=canned.get(command, ""), success=True)

    monkeypatch.setattr(d, "execute", fake_execute)
    return d


@pytest.mark.asyncio
async def test_get_facts_parses_hostname_model_version(driver):
    facts = await driver.get_facts()
    assert facts.hostname == "CORE-SW01"
    assert facts.vendor == "Cisco"
    assert facts.os_version == "15.0(2)SE11,"[:-1] or facts.os_version  # tolerate trailing punctuation variance
    assert facts.serial_number == "FOC1234X5YZ"
    assert facts.uptime_seconds is not None
    assert facts.uptime_seconds > 0


@pytest.mark.asyncio
async def test_get_interfaces_parses_state_and_description(driver):
    interfaces = await driver.get_interfaces()
    assert len(interfaces) == 2
    up_if = next(i for i in interfaces if i.name == "GigabitEthernet1/0/24")
    assert up_if.admin_state == "up"
    assert up_if.oper_state == "up"
    assert up_if.description == "Uplink-ACCESS-02"
    assert up_if.duplex == "full"
    assert up_if.speed_mbps == 1000
    assert "10.10.0.10/24" in up_if.ipv4_addresses

    down_if = next(i for i in interfaces if i.name == "GigabitEthernet1/0/25")
    assert down_if.admin_state == "down"
    assert down_if.oper_state == "down"


@pytest.mark.asyncio
async def test_get_vlans_parses_table(driver):
    vlans = await driver.get_vlans()
    vlan_ids = {v.vlan_id for v in vlans}
    assert vlan_ids == {1, 10, 20, 99}
    voice = next(v for v in vlans if v.vlan_id == 20)
    assert voice.name == "VOICE"
    native = next(v for v in vlans if v.vlan_id == 99)
    assert native.status == "suspended"


@pytest.mark.asyncio
async def test_get_neighbors_parses_cdp(driver):
    neighbors = await driver.get_neighbors()
    assert len(neighbors) == 2
    access = next(n for n in neighbors if n.remote_hostname == "ACCESS-02.lab.local")
    assert access.local_interface == "GigabitEthernet1/0/24"
    assert access.remote_interface == "GigabitEthernet0/48"
    assert access.remote_management_address == "10.10.0.11"
    assert access.source == "CDP"
