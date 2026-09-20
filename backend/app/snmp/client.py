"""Real SNMP client (GET / WALK) built on pysnmp's v3arch asyncio API.

Supports SNMPv2c today. The `SNMPCredential` shape and the `_auth_data()`
method are the extension point for SNMPv3 (USM users, auth/priv protocols) —
the credential model in app.credentials already carries the v3 fields; wiring
them into `UsmUserData` is the only change needed, and is not yet done. That
gap is intentional and documented rather than silently pretending v3 works.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from pysnmp.hlapi.asyncio import (
    CommunityData,
    ContextData,
    ObjectIdentity,
    ObjectType,
    SnmpEngine,
    UdpTransportTarget,
    bulkCmd,
    getCmd,
)

logger = logging.getLogger("app.snmp")


class SNMPError(RuntimeError):
    """Raised on SNMP transport/protocol errors (timeout, wrong community, etc.)."""


@dataclass
class SNMPCredential:
    version: str = "v2c"  # "v2c" | "v3" (v3 not yet implemented — see module docstring)
    community: str | None = None
    port: int = 161


@dataclass
class SNMPResult:
    oid: str
    value: str
    value_type: str


class SNMPClient:
    """One client per target host. Cheap to construct; does not hold a socket open."""

    def __init__(self, host: str, credential: SNMPCredential, timeout: float = 2.0, retries: int = 1) -> None:
        self.host = host
        self.credential = credential
        self.timeout = timeout
        self.retries = retries

    def _auth_data(self) -> CommunityData:
        if self.credential.version != "v2c":
            raise SNMPError(
                f"SNMP version '{self.credential.version}' is not implemented. "
                "Only SNMPv2c is currently supported (NOT IMPLEMENTED: SNMPv3)."
            )
        if not self.credential.community:
            raise SNMPError("No SNMP community string configured for this credential profile.")
        return CommunityData(self.credential.community, mpModel=1)  # mpModel=1 => SNMPv2c

    async def get(self, oid: str) -> SNMPResult | None:
        """SNMP GET for a single scalar OID. Returns None if the agent has no such object."""
        engine = SnmpEngine()
        target = UdpTransportTarget((self.host, self.credential.port), timeout=self.timeout, retries=self.retries)
        error_indication, error_status, _error_index, var_binds = await getCmd(
            engine,
            self._auth_data(),
            target,
            ContextData(),
            ObjectType(ObjectIdentity(oid)),
        )
        if error_indication:
            raise SNMPError(f"SNMP GET {oid} @ {self.host} failed: {error_indication}")
        if error_status:
            raise SNMPError(f"SNMP GET {oid} @ {self.host} error: {error_status.prettyPrint()}")
        for name, value in var_binds:
            type_name = type(value).__name__
            if type_name in {"NoSuchObject", "NoSuchInstance", "EndOfMibView"}:
                return None
            return SNMPResult(oid=str(name), value=str(value), value_type=type_name)
        return None

    async def walk(self, base_oid: str, max_rows: int = 2000) -> list[SNMPResult]:
        """SNMP walk via GETBULK, following the tree until it leaves `base_oid`."""
        engine = SnmpEngine()
        target = UdpTransportTarget((self.host, self.credential.port), timeout=self.timeout, retries=self.retries)
        results: list[SNMPResult] = []
        current = ObjectIdentity(base_oid)
        base_tuple = tuple(int(x) for x in base_oid.split("."))

        while len(results) < max_rows:
            error_indication, error_status, _error_index, var_bind_table = await bulkCmd(
                engine,
                self._auth_data(),
                target,
                ContextData(),
                0,
                25,
                ObjectType(current),
            )
            if error_indication:
                raise SNMPError(f"SNMP WALK {base_oid} @ {self.host} failed: {error_indication}")
            if error_status:
                raise SNMPError(f"SNMP WALK {base_oid} @ {self.host} error: {error_status.prettyPrint()}")
            if not var_bind_table:
                break

            advanced = False
            for name, value in var_bind_table:
                oid_tuple = tuple(int(x) for x in str(name).split("."))
                if oid_tuple[: len(base_tuple)] != base_tuple:
                    return results  # walked past the subtree we care about
                type_name = type(value).__name__
                if type_name in {"NoSuchObject", "NoSuchInstance", "EndOfMibView"}:
                    return results
                results.append(SNMPResult(oid=str(name), value=str(value), value_type=type_name))
                current = ObjectIdentity(str(name))
                advanced = True
            if not advanced:
                break
        return results

    async def walk_table(self, column_oids: dict[str, str], max_rows: int = 2000) -> dict[str, dict[str, str]]:
        """Walk several columns of the same conceptual SNMP table and correlate by index suffix.

        `column_oids` maps a friendly field name -> base column OID. Returns
        {index_suffix: {field_name: value}}.
        """
        table: dict[str, dict[str, str]] = {}
        for field, base_oid in column_oids.items():
            rows = await self.walk(base_oid, max_rows=max_rows)
            for row in rows:
                suffix = row.oid[len(base_oid) + 1 :]
                table.setdefault(suffix, {})[field] = row.value
        return table
