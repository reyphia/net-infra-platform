"""Semantic configuration diff.

Parses an IOS-style hierarchical configuration (top-level commands with
indented sub-commands, e.g. `interface Gi1/0/24` followed by its
`description`, `switchport access vlan`, etc.) into blocks, categorizes each
block, and diffs old vs. new at the block + line level -- not just a raw
text diff. A raw unified diff is still produced alongside, since it remains
useful for auditors who want the literal change.

This targets Cisco IOS/IOS-XE syntax specifically (it is the dominant
hierarchical-CLI format this project's drivers speak). RouterOS's `/export`
format is flatter and line-oriented; `semantic_diff_generic()` at the bottom
handles that case with plain line-level categorization instead of
indentation-based block parsing.
"""
from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field
from enum import Enum


class ChangeCategory(str, Enum):
    INTERFACES = "Interfaces"
    VLANS = "VLANs"
    ROUTES = "Routes"
    ACLS = "ACLs"
    NAT = "NAT"
    HOSTNAME = "Hostname"
    SSH = "SSH"
    SNMP = "SNMP"
    NTP = "NTP"
    USERS = "Users"
    SYSTEM = "System settings"
    OTHER = "Other"


_CATEGORY_PATTERNS: list[tuple[re.Pattern[str], ChangeCategory]] = [
    (re.compile(r"^interface\s+", re.IGNORECASE), ChangeCategory.INTERFACES),
    (re.compile(r"^vlan\s+\d+", re.IGNORECASE), ChangeCategory.VLANS),
    (re.compile(r"^ip route\s+", re.IGNORECASE), ChangeCategory.ROUTES),
    (re.compile(r"^router\s+", re.IGNORECASE), ChangeCategory.ROUTES),
    (re.compile(r"^(ip )?access-list\s+", re.IGNORECASE), ChangeCategory.ACLS),
    (re.compile(r"^ip nat\s+", re.IGNORECASE), ChangeCategory.NAT),
    (re.compile(r"^hostname\s+", re.IGNORECASE), ChangeCategory.HOSTNAME),
    (re.compile(r"^(ip ssh|line vty|line console)", re.IGNORECASE), ChangeCategory.SSH),
    (re.compile(r"^snmp-server", re.IGNORECASE), ChangeCategory.SNMP),
    (re.compile(r"^ntp\s+", re.IGNORECASE), ChangeCategory.NTP),
    (re.compile(r"^username\s+", re.IGNORECASE), ChangeCategory.USERS),
]


@dataclass
class ConfigBlock:
    key: str
    header: str
    category: ChangeCategory
    children: list[str] = field(default_factory=list)


@dataclass
class BlockChange:
    category: str
    entity: str
    change_type: str  # added | removed | modified
    added_lines: list[str] = field(default_factory=list)
    removed_lines: list[str] = field(default_factory=list)


@dataclass
class SemanticDiffReport:
    changes: list[BlockChange]
    raw_diff: str
    categories_touched: list[str]


def _categorize(header: str) -> ChangeCategory:
    for pattern, category in _CATEGORY_PATTERNS:
        if pattern.match(header.strip()):
            return category
    return ChangeCategory.SYSTEM if header.strip() else ChangeCategory.OTHER


def parse_ios_config(config_text: str) -> dict[str, ConfigBlock]:
    blocks: dict[str, ConfigBlock] = {}
    current: ConfigBlock | None = None
    for raw_line in config_text.splitlines():
        if not raw_line.strip() or raw_line.strip() == "!":
            current = None
            continue
        if raw_line[0] not in (" ", "\t"):
            header = raw_line.strip()
            key = header
            current = ConfigBlock(key=key, header=header, category=_categorize(header))
            # last-one-wins is intentional: a real running-config can repeat a
            # top-level command (e.g. multiple `ip route` lines); those are
            # merged into one synthetic block per unique header via the key.
            if key in blocks:
                current = blocks[key]
            else:
                blocks[key] = current
        elif current is not None:
            current.children.append(raw_line.strip())
    return blocks


def render_ios_blocks(blocks: dict[str, ConfigBlock]) -> str:
    lines: list[str] = []
    for block in blocks.values():
        lines.append(block.header)
        lines.extend(f" {child}" for child in block.children)
        lines.append("!")
    return "\n".join(lines)


def predict_applied_config(before_config: str, proposed_lines: list[str]) -> str:
    """Best-effort prediction of what the running-config will look like after
    `proposed_lines` are applied, WITHOUT touching the device.

    This is an approximation, not a real parser/compiler for IOS semantics:
    for a top-level block that already exists, proposed child lines are
    merged in (a `no <line>` child removes a matching existing child; any
    other child is added if not already present). It cannot know about
    IOS-internal defaults, mutual exclusivity between commands, or ordering
    effects. It exists to give the operator a *preview* before APPLY; the
    authoritative diff is always recomputed from the device's real
    running-config after APPLY, during VERIFY.
    """
    before_blocks = parse_ios_config(before_config)
    proposed_blocks = parse_ios_config("\n".join(proposed_lines))

    merged: dict[str, ConfigBlock] = dict(before_blocks)
    for key, proposed_block in proposed_blocks.items():
        if key in merged:
            existing = merged[key]
            new_children = list(existing.children)
            for child in proposed_block.children:
                if child.lower().startswith("no "):
                    negated = child[3:].strip()
                    new_children = [c for c in new_children if c != negated]
                elif child not in new_children:
                    new_children.append(child)
            merged[key] = ConfigBlock(
                key=key, header=existing.header, category=existing.category, children=new_children
            )
        else:
            merged[key] = proposed_block
    return render_ios_blocks(merged)


def semantic_diff(old_config: str, new_config: str) -> SemanticDiffReport:
    old_blocks = parse_ios_config(old_config)
    new_blocks = parse_ios_config(new_config)

    changes: list[BlockChange] = []
    for key in sorted(set(old_blocks) - set(new_blocks)):
        block = old_blocks[key]
        changes.append(BlockChange(category=block.category.value, entity=block.header, change_type="removed"))
    for key in sorted(set(new_blocks) - set(old_blocks)):
        block = new_blocks[key]
        changes.append(BlockChange(category=block.category.value, entity=block.header, change_type="added"))
    for key in sorted(set(old_blocks) & set(new_blocks)):
        old_block, new_block = old_blocks[key], new_blocks[key]
        old_children, new_children = set(old_block.children), set(new_block.children)
        if old_children == new_children:
            continue
        changes.append(
            BlockChange(
                category=new_block.category.value,
                entity=new_block.header,
                change_type="modified",
                added_lines=sorted(new_children - old_children),
                removed_lines=sorted(old_children - new_children),
            )
        )

    raw_diff = "\n".join(
        difflib.unified_diff(
            old_config.splitlines(), new_config.splitlines(), fromfile="before", tofile="after", lineterm=""
        )
    )
    categories = sorted({c.category for c in changes})
    return SemanticDiffReport(changes=changes, raw_diff=raw_diff, categories_touched=categories)


def semantic_diff_generic(old_config: str, new_config: str) -> SemanticDiffReport:
    """Flat, line-oriented diff for non-hierarchical config formats (e.g.
    RouterOS `/export` output). Categorization is best-effort on each line's
    leading `/menu` path rather than IOS keyword matching.
    """
    old_lines = [line for line in old_config.splitlines() if line.strip() and not line.strip().startswith("#")]
    new_lines = [line for line in new_config.splitlines() if line.strip() and not line.strip().startswith("#")]

    old_set, new_set = set(old_lines), set(new_lines)
    changes: list[BlockChange] = []
    for line in sorted(old_set - new_set):
        changes.append(BlockChange(category=_routeros_category(line), entity=line, change_type="removed"))
    for line in sorted(new_set - old_set):
        changes.append(BlockChange(category=_routeros_category(line), entity=line, change_type="added"))

    raw_diff = "\n".join(
        difflib.unified_diff(old_lines, new_lines, fromfile="before", tofile="after", lineterm="")
    )
    categories = sorted({c.category for c in changes})
    return SemanticDiffReport(changes=changes, raw_diff=raw_diff, categories_touched=categories)


def _routeros_category(line: str) -> str:
    if line.startswith("/interface vlan"):
        return ChangeCategory.VLANS.value
    if line.startswith("/interface"):
        return ChangeCategory.INTERFACES.value
    if line.startswith("/ip route"):
        return ChangeCategory.ROUTES.value
    if line.startswith("/ip firewall"):
        return ChangeCategory.ACLS.value
    if line.startswith("/system ntp"):
        return ChangeCategory.NTP.value
    if line.startswith("/user"):
        return ChangeCategory.USERS.value
    if line.startswith("/ip service") or line.startswith("/ip ssh"):
        return ChangeCategory.SSH.value
    if line.startswith("/snmp"):
        return ChangeCategory.SNMP.value
    return ChangeCategory.OTHER.value
