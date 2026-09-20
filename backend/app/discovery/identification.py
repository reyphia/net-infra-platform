"""Multi-signal device identification with explicit confidence scoring.

Identification is never asserted as certain. Each signal contributes bounded
evidence toward a `device_type` guess and the final `confidence` is capped
below 1.0 unless multiple independent signals agree.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.db.models import DeviceType

# sysObjectID enterprise prefixes -> (vendor, hint). Not exhaustive; extend as needed.
_ENTERPRISE_VENDOR_HINTS: dict[str, str] = {
    "1.3.6.1.4.1.9": "Cisco",
    "1.3.6.1.4.1.14988": "MikroTik",
    "1.3.6.1.4.1.2636": "Juniper",
    "1.3.6.1.4.1.30065": "Arista",
    "1.3.6.1.4.1.11": "HP",
    "1.3.6.1.4.1.25506": "H3C",
    "1.3.6.1.4.1.8072": "Net-SNMP (generic host agent)",
}

_SYSDESCR_TYPE_HINTS: list[tuple[str, DeviceType]] = [
    ("ios-xe", DeviceType.ROUTER),
    ("ios software", DeviceType.ROUTER),
    ("cisco ios", DeviceType.ROUTER),
    ("catalyst", DeviceType.SWITCH),
    ("nexus", DeviceType.SWITCH),
    ("routeros", DeviceType.ROUTER),
    ("mikrotik", DeviceType.ROUTER),
    ("asa", DeviceType.FIREWALL),
    ("firepower", DeviceType.FIREWALL),
    ("pan-os", DeviceType.FIREWALL),
    ("fortigate", DeviceType.FIREWALL),
    ("aironet", DeviceType.ACCESS_POINT),
    ("unifi", DeviceType.ACCESS_POINT),
    ("linux", DeviceType.SERVER),
    ("windows", DeviceType.SERVER),
]


@dataclass
class IdentificationEvidence:
    device_type: DeviceType
    weight: float
    source: str  # "SNMP" | "LLDP" | "CDP" | "SSH_BANNER" | "MAC_VENDOR"


@dataclass
class IdentificationResult:
    device_type: DeviceType
    confidence: float
    sources: list[str]
    vendor_hint: str | None = None


def identify_from_sys_object_id(sys_object_id: str | None) -> tuple[str | None, IdentificationEvidence | None]:
    if not sys_object_id:
        return None, None
    normalized = sys_object_id.lstrip(".")
    segments = normalized.split(".")
    for prefix, vendor in _ENTERPRISE_VENDOR_HINTS.items():
        prefix_segments = prefix.split(".")
        if segments[: len(prefix_segments)] == prefix_segments:
            return vendor, None
    return None, None


def identify_from_sys_descr(sys_descr: str | None) -> IdentificationEvidence | None:
    if not sys_descr:
        return None
    lowered = sys_descr.lower()
    for needle, device_type in _SYSDESCR_TYPE_HINTS:
        if needle in lowered:
            return IdentificationEvidence(device_type=device_type, weight=0.6, source="SNMP")
    return None


def identify_from_cdp_platform(platform: str | None) -> IdentificationEvidence | None:
    if not platform:
        return None
    lowered = platform.lower()
    if "switch" in lowered or "catalyst" in lowered or "nexus" in lowered:
        return IdentificationEvidence(device_type=DeviceType.SWITCH, weight=0.35, source="CDP")
    if "router" in lowered or "isr" in lowered or "asr" in lowered:
        return IdentificationEvidence(device_type=DeviceType.ROUTER, weight=0.35, source="CDP")
    if "ap" in lowered.split() or "aironet" in lowered:
        return IdentificationEvidence(device_type=DeviceType.ACCESS_POINT, weight=0.35, source="CDP")
    return None


def identify_from_ssh_banner(banner: str | None) -> IdentificationEvidence | None:
    if not banner:
        return None
    lowered = banner.lower()
    if "cisco" in lowered:
        return IdentificationEvidence(device_type=DeviceType.ROUTER, weight=0.25, source="SSH_BANNER")
    if "routeros" in lowered or "mikrotik" in lowered:
        return IdentificationEvidence(device_type=DeviceType.ROUTER, weight=0.25, source="SSH_BANNER")
    if "openssh" in lowered:
        return IdentificationEvidence(device_type=DeviceType.SERVER, weight=0.15, source="SSH_BANNER")
    return None


def combine_evidence(evidence: list[IdentificationEvidence]) -> IdentificationResult:
    """Combine independent signals. Agreement across sources raises confidence;
    conflicting signals lower it toward UNKNOWN rather than picking arbitrarily."""
    if not evidence:
        return IdentificationResult(device_type=DeviceType.UNKNOWN, confidence=0.0, sources=[])

    votes: dict[DeviceType, float] = {}
    sources: set[str] = set()
    for item in evidence:
        votes[item.device_type] = votes.get(item.device_type, 0.0) + item.weight
        sources.add(item.source)

    winner = max(votes.items(), key=lambda kv: kv[1])
    total_weight = sum(votes.values())
    # Confidence = winner's share of total evidence weight, scaled down if only
    # one weak signal exists, and never allowed to hit a false-certain 1.0
    # from a single low-weight source.
    share = winner[1] / total_weight if total_weight else 0.0
    raw_confidence = min(0.97, share * min(1.0, total_weight / 0.9))

    return IdentificationResult(
        device_type=winner[0],
        confidence=round(raw_confidence, 2),
        sources=sorted(sources),
    )
