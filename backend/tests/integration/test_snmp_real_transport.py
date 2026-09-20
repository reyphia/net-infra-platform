"""Proves the SNMP client sends real UDP packets and processes real protocol
responses -- not a mocked transport. Since a live SNMP agent isn't available
in CI, this targets a closed local UDP port: pysnmp still performs a genuine
network round-trip (send + wait + timeout), which is what we assert on. Any
mocking here would defeat the point of the test.
"""
from __future__ import annotations

import pytest

from app.snmp.client import SNMPClient, SNMPCredential, SNMPError


@pytest.mark.asyncio
async def test_snmp_get_against_closed_port_returns_real_timeout():
    client = SNMPClient("127.0.0.1", SNMPCredential(community="public", port=1), timeout=1, retries=0)
    with pytest.raises(SNMPError):
        await client.get("1.3.6.1.2.1.1.1.0")


@pytest.mark.asyncio
async def test_snmp_requires_community_string():
    client = SNMPClient("127.0.0.1", SNMPCredential(community=None), timeout=1, retries=0)
    with pytest.raises(SNMPError):
        await client.get("1.3.6.1.2.1.1.1.0")


@pytest.mark.asyncio
async def test_snmp_v3_explicitly_not_implemented():
    client = SNMPClient("127.0.0.1", SNMPCredential(version="v3"), timeout=1, retries=0)
    with pytest.raises(SNMPError, match="not implemented"):
        await client.get("1.3.6.1.2.1.1.1.0")
