"""Redact secrets from configuration text before it is shown in the UI.

The *original* backup on disk is preserved untouched (it has to be, for
restoration/rollback to work) -- this module only produces a sanitized copy
for display purposes.
"""
from __future__ import annotations

import re

_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    # Cisco: "username admin secret 5 $1$abc$..." / "password 7 0822455D0A16"
    (re.compile(r"(username\s+\S+\s+(?:secret|password)\s+\d?\s*)\S+", re.IGNORECASE), r"\1<redacted>"),
    (re.compile(r"(enable\s+secret\s+\d?\s*)\S+", re.IGNORECASE), r"\1<redacted>"),
    (re.compile(r"(enable\s+password\s+\d?\s*)\S+", re.IGNORECASE), r"\1<redacted>"),
    (re.compile(r"(snmp-server\s+community\s+)\S+", re.IGNORECASE), r"\1<redacted>"),
    (re.compile(r"(\bpassword\s+\d?\s*)\S+", re.IGNORECASE), r"\1<redacted>"),
    (re.compile(r"(pre-shared-key\s+)\S+", re.IGNORECASE), r"\1<redacted>"),
    (re.compile(r"(wpa-psk\s+\S+\s+)\S+", re.IGNORECASE), r"\1<redacted>"),
    # MikroTik: "set password=xxxxx"
    (re.compile(r"(password=)\S+", re.IGNORECASE), r"\1<redacted>"),
    (re.compile(r"(secret=)\S+", re.IGNORECASE), r"\1<redacted>"),
]


def sanitize_config(config_text: str) -> str:
    sanitized = config_text
    for pattern, replacement in _PATTERNS:
        sanitized = pattern.sub(replacement, sanitized)
    return sanitized
