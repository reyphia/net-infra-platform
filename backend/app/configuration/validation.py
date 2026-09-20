"""Pre-apply validation for proposed configuration changes.

Honest limitation: this is NOT a full IOS/RouterOS command grammar parser
(building one is a large project in itself). What it DOES do, for real:
  1. Blocks a denylist of destructive/out-of-band commands outright
     (reload, erase, format, factory-reset, etc.) so a change plan can never
     silently include them.
  2. Flags empty/whitespace-only proposed changes.
  3. For Cisco targets, checks that every non-blank line at least looks like
     a plausible IOS command token (starts with a known verb or is indented
     as a sub-command) -- this catches obvious typos/garbage, not deep
     semantic errors (e.g. an invalid VLAN range would NOT be caught here).
  4. Warns (does not block) on lines that touch AAA/authentication or the
     management interface itself, since a bad change there can lock the
     operator out.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

_DENYLIST_PATTERNS = [
    re.compile(r"^\s*reload\b", re.IGNORECASE),
    re.compile(r"^\s*erase\s+", re.IGNORECASE),
    re.compile(r"^\s*write\s+erase\b", re.IGNORECASE),
    re.compile(r"^\s*format\s+", re.IGNORECASE),
    re.compile(r"^\s*factory-reset\b", re.IGNORECASE),
    re.compile(r"^\s*/system\s+reset-configuration\b", re.IGNORECASE),
    re.compile(r"^\s*/system\s+reboot\b", re.IGNORECASE),
]

_RISKY_PATTERNS = [
    (re.compile(r"^\s*no\s+aaa\b", re.IGNORECASE), "Disables AAA -- verify this won't remove your own auth method."),
    (re.compile(r"^\s*no\s+username\b", re.IGNORECASE), "Removes a local user -- confirm it isn't the one you're using."),
    (
        re.compile(r"^\s*(interface\s+(vlan1|mgmt))", re.IGNORECASE),
        "Touches the management interface -- a mistake here can disconnect this session.",
    ),
    (re.compile(r"^\s*no\s+ip\s+ssh\b", re.IGNORECASE), "Disables SSH -- this could lock out remote management."),
]

_CISCO_KNOWN_VERBS = {
    "interface", "vlan", "ip", "ipv6", "no", "hostname", "router", "access-list", "line",
    "snmp-server", "ntp", "username", "enable", "description", "switchport", "shutdown",
    "end", "exit", "spanning-tree", "logging", "banner", "service", "clock", "crypto",
    "aaa", "boot", "vrf", "class-map", "policy-map", "vtp", "channel-group",
}


@dataclass
class ValidationIssue:
    severity: str  # "blocking" | "warning"
    line: str
    message: str


@dataclass
class ValidationReport:
    ok: bool
    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def blocking_issues(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == "blocking"]


def validate_proposed_config(lines: list[str], driver_type: str) -> ValidationReport:
    issues: list[ValidationIssue] = []

    non_blank = [ln for ln in lines if ln.strip()]
    if not non_blank:
        issues.append(ValidationIssue(severity="blocking", line="", message="Proposed change is empty."))
        return ValidationReport(ok=False, issues=issues)

    for line in non_blank:
        for pattern in _DENYLIST_PATTERNS:
            if pattern.match(line):
                issues.append(
                    ValidationIssue(
                        severity="blocking",
                        line=line,
                        message="This command is on the disallowed list for change plans "
                        "(destructive/out-of-band operation). Run it manually via the terminal if truly intended.",
                    )
                )
        for pattern, message in _RISKY_PATTERNS:
            if pattern.match(line):
                issues.append(ValidationIssue(severity="warning", line=line, message=message))

        if driver_type == "cisco_ios":
            stripped = line.strip()
            first_token = stripped.split()[0].lower() if stripped.split() else ""
            looks_like_subcommand = line.startswith((" ", "\t"))
            if not looks_like_subcommand and first_token not in _CISCO_KNOWN_VERBS and not first_token.isdigit():
                issues.append(
                    ValidationIssue(
                        severity="warning",
                        line=line,
                        message=f"'{first_token}' is not a recognized top-level IOS command keyword. "
                        "This is a heuristic check, not full grammar validation -- verify manually.",
                    )
                )

    ok = not any(i.severity == "blocking" for i in issues)
    return ValidationReport(ok=ok, issues=issues)
