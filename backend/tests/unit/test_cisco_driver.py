import pytest

from app.drivers.base import SSHCredential
from app.drivers.cisco import CiscoIOSDriver

SHOW_VERSION = """Cisco IOS Software, C3560 Software (C3560-IPSERVICESK9-M), Version 15.0(2)SE11, RELEASE SOFTWARE (fc3)
Technical Support: http://www.cisco.com/techsupport
Copyright (c) 1986-2018 by Cisco Systems, Inc.
Compiled Thu 20-Sep-18 04:59 by prod_rel_team

ROM: Bootstrap program is C3560 boot loader

CORE-SW01 uptime is 12 weeks, 3 days, 4 hours, 22 minutes
System returned to ROM by power-on
System image file is "flash:/c3560-ipservicesk9-mz.150-2.SE11/c3560-ipservicesk9-mz.150-2.SE11.bin"


cisco WS-C3560X-24T-S (PowerPC405) processor (revision A0) with 131072K bytes of memory.
Processor board ID FOC1534X2AB
Last reset from power-on
1 Virtual Ethernet interface
24 FastEthernet interfaces
System serial number: FOC1534X2AB
"""

SHOW_INTERFACES = """GigabitEthernet1/0/24 is up, line protocol is up (connected)
  Hardware is Gigabit Ethernet, address is 0011.2233.4455 (bia 0011.2233.4455)
  Description: Uplink-ACCESS-02
  Internet address is 10.10.0.2/24
  MTU 1500 bytes, BW 1000000 Kbit/sec, DLY 10 usec,
     reliability 255/255, txload 1/255, rxload 1/255
  Encapsulation ARPA, loopback not set
  Full-duplex, 1000Mb/s, media type is 10/100/1000BaseTX
GigabitEthernet1/0/1 is administratively down, line protocol is down (disabled)
  Hardware is Gigabit Ethernet, address is 0011.2233.4456 (bia 0011.2233.4456)
  MTU 1500 bytes, BW 1000000 Kbit/sec, DLY 10 usec,
     reliability 255/255, txload 1/255, rxload 1/255
  Encapsulation ARPA, loopback not set
  Full-duplex, 1000Mb/s, media type is 10/100/1000BaseTX
"""

SHOW_VLAN_BRIEF = """VLAN Name                             Status    Ports
---- -------------------------------- --------- -------------------------------
1    default                          active    Gi1/0/2, Gi1/0/3
10   USERS                            active    Gi1/0/24
20   SERVERS                          active
999  UNUSED                           suspended
"""

SHOW_CDP_NEIGHBORS_DETAIL = """-------------------------
Device ID: ACCESS-02.lab.local
Entry address(es):
  IP address: 10.10.0.20
Platform: cisco WS-C2960X-24TS-L,  Capabilities: Switch IGMP
Interface: GigabitEthernet1/0/24,  Port ID (outgoing port): GigabitEthernet1/0/48
-------------------------
"""


class _FakeSession:
    """Stands in for InteractiveSSHSession, returning canned output per command."""

    def __init__(self, canned: dict[str, str]) -> None:
        self.canned = canned
        self.sent: list[str] = []

    async def send(self, line: str) -> str:
        self.sent.append(line)
        body = self.canned.get(line.strip(), "")
        return f"{line}\r\n{body}\r\nCORE-SW01#"

    async def close(self) -> None:
        pass


def _driver_with_canned_output(canned: dict[str, str]) -> CiscoIOSDriver:
    driver = CiscoIOSDriver("10.10.0.10", SSHCredential(username="admin", password="x"))
    driver._session = _FakeSession(canned)  # noqa: SLF001 - direct injection for unit testing
    return driver


@pytest.mark.asyncio
async def test_execute_strips_echo_and_prompt():
    driver = _driver_with_canned_output({"show clock": "*12:00:00.000 UTC Mon Jan 1 2026"})
    result = await driver.execute("show clock")
    assert result.success
    assert result.output == "*12:00:00.000 UTC Mon Jan 1 2026"


@pytest.mark.asyncio
async def test_execute_detects_invalid_input():
    driver = _driver_with_canned_output({"bogus command": "% Invalid input detected at '^' marker."})
    result = await driver.execute("bogus command")
    assert not result.success
    assert result.error is not None


@pytest.mark.asyncio
async def test_get_facts_parses_show_version():
    driver = _driver_with_canned_output({"show version": SHOW_VERSION})
    facts = await driver.get_facts()
    assert facts.hostname == "CORE-SW01"
    assert facts.vendor == "Cisco"
    assert facts.model == "WS-C3560X-24T-S"
    assert facts.os_version == "15.0(2)SE11"
    assert facts.serial_number == "FOC1534X2AB"
    assert facts.uptime_seconds is not None
    assert facts.uptime_seconds > 0


@pytest.mark.asyncio
async def test_get_interfaces_parses_admin_and_oper_state():
    driver = _driver_with_canned_output({"show interfaces": SHOW_INTERFACES})
    interfaces = await driver.get_interfaces()
    by_name = {i.name: i for i in interfaces}
    assert by_name["GigabitEthernet1/0/24"].admin_state == "up"
    assert by_name["GigabitEthernet1/0/24"].oper_state == "up"
    assert by_name["GigabitEthernet1/0/24"].description == "Uplink-ACCESS-02"
    assert by_name["GigabitEthernet1/0/24"].mac_address == "0011.2233.4455"
    assert "10.10.0.2/24" in by_name["GigabitEthernet1/0/24"].ipv4_addresses
    assert by_name["GigabitEthernet1/0/1"].admin_state == "down"
    assert by_name["GigabitEthernet1/0/1"].oper_state == "down"


@pytest.mark.asyncio
async def test_get_vlans_parses_vlan_brief():
    driver = _driver_with_canned_output({"show vlan brief": SHOW_VLAN_BRIEF})
    vlans = await driver.get_vlans()
    by_id = {v.vlan_id: v for v in vlans}
    assert by_id[10].name == "USERS"
    assert by_id[10].status == "active"
    assert by_id[999].status == "suspended"


@pytest.mark.asyncio
async def test_get_neighbors_parses_cdp_detail():
    driver = _driver_with_canned_output({"show cdp neighbors detail": SHOW_CDP_NEIGHBORS_DETAIL})
    neighbors = await driver.get_neighbors()
    assert len(neighbors) == 1
    n = neighbors[0]
    assert n.remote_hostname == "ACCESS-02.lab.local"
    assert n.local_interface == "GigabitEthernet1/0/24"
    assert n.remote_interface == "GigabitEthernet1/0/48"
    assert n.remote_management_address == "10.10.0.20"
    assert n.source == "CDP"


@pytest.mark.asyncio
async def test_apply_config_detects_rejected_lines():
    driver = _driver_with_canned_output(
        {
            "configure terminal": "Enter configuration commands, one per line.",
            "totally bogus syntax": "% Invalid input detected at '^' marker.",
            "end": "",
        }
    )
    result = await driver.apply_config(["totally bogus syntax"])
    assert not result.success
    assert result.error is not None
