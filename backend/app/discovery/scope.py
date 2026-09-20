"""Discovery scope: explicit, operator-authorized CIDR ranges only.

The platform never discovers or scans outside what the operator explicitly
configures for a given job. There is no "scan the internet" mode, no default
broad scope, and no automatic expansion beyond the given CIDRs.
"""
from __future__ import annotations

import ipaddress
from dataclasses import dataclass


class InvalidScopeError(ValueError):
    pass


_MAX_HOSTS_PER_JOB = 65536  # hard ceiling so a fat-fingered /8 can't be queued accidentally


@dataclass
class DiscoveryScope:
    cidrs: list[str]

    def __post_init__(self) -> None:
        if not self.cidrs:
            raise InvalidScopeError("At least one CIDR must be specified; there is no implicit default scope.")
        for cidr in self.cidrs:
            try:
                ipaddress.ip_network(cidr, strict=False)
            except ValueError as exc:
                raise InvalidScopeError(f"'{cidr}' is not a valid CIDR: {exc}") from exc

    def host_addresses(self) -> list[str]:
        addresses: list[str] = []
        for cidr in self.cidrs:
            network = ipaddress.ip_network(cidr, strict=False)
            if network.num_addresses > _MAX_HOSTS_PER_JOB:
                raise InvalidScopeError(
                    f"'{cidr}' contains {network.num_addresses} addresses, exceeding the "
                    f"per-job limit of {_MAX_HOSTS_PER_JOB}. Split it into smaller ranges."
                )
            if network.num_addresses <= 2:
                addresses.extend(str(ip) for ip in network)  # /31, /32 have no usable "hosts" iterator
            else:
                addresses.extend(str(ip) for ip in network.hosts())
        return addresses
