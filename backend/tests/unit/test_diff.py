from app.configuration.diff import (
    parse_ios_config,
    predict_applied_config,
    semantic_diff,
    semantic_diff_generic,
)

OLD_CONFIG = """hostname CORE-SW01
!
interface GigabitEthernet1/0/24
 description Uplink-OLD
 switchport access vlan 10
!
vlan 10
 name USERS
!
"""

NEW_CONFIG = """hostname CORE-SW01
!
interface GigabitEthernet1/0/24
 description Uplink-NEW
 switchport access vlan 20
!
vlan 10
 name USERS
!
vlan 20
 name VOICE
!
"""


def test_parse_ios_config_blocks():
    blocks = parse_ios_config(OLD_CONFIG)
    assert "interface GigabitEthernet1/0/24" in blocks
    assert "description Uplink-OLD" in blocks["interface GigabitEthernet1/0/24"].children


def test_semantic_diff_detects_interface_modification():
    report = semantic_diff(OLD_CONFIG, NEW_CONFIG)
    iface_changes = [c for c in report.changes if c.entity == "interface GigabitEthernet1/0/24"]
    assert len(iface_changes) == 1
    assert iface_changes[0].change_type == "modified"
    assert "description Uplink-NEW" in iface_changes[0].added_lines
    assert "description Uplink-OLD" in iface_changes[0].removed_lines


def test_semantic_diff_detects_added_vlan():
    report = semantic_diff(OLD_CONFIG, NEW_CONFIG)
    added = [c for c in report.changes if c.change_type == "added"]
    assert any(c.entity == "vlan 20" for c in added)


def test_semantic_diff_categorizes_changes():
    report = semantic_diff(OLD_CONFIG, NEW_CONFIG)
    assert "Interfaces" in report.categories_touched
    assert "VLANs" in report.categories_touched


def test_semantic_diff_no_changes_when_identical():
    report = semantic_diff(OLD_CONFIG, OLD_CONFIG)
    assert report.changes == []


def test_predict_applied_config_merges_proposed_lines():
    proposed = ["interface GigabitEthernet1/0/24", " description Uplink-NEW"]
    predicted = predict_applied_config(OLD_CONFIG, proposed)
    assert "description Uplink-NEW" in predicted
    assert "switchport access vlan 10" in predicted  # untouched sibling line preserved


def test_predict_applied_config_handles_negation():
    proposed = ["interface GigabitEthernet1/0/24", " no switchport access vlan 10", " switchport access vlan 30"]
    predicted = predict_applied_config(OLD_CONFIG, proposed)
    assert "switchport access vlan 30" in predicted
    assert "switchport access vlan 10" not in predicted


def test_semantic_diff_generic_routeros():
    old = "/interface bridge add name=bridge1\n/ip address add address=10.0.0.1/24 interface=ether1"
    new = "/interface bridge add name=bridge1\n/ip address add address=10.0.0.2/24 interface=ether1"
    report = semantic_diff_generic(old, new)
    assert any(c.change_type == "removed" and "10.0.0.1" in c.entity for c in report.changes)
    assert any(c.change_type == "added" and "10.0.0.2" in c.entity for c in report.changes)
