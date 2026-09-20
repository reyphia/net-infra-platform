from app.db.models import DeviceType
from app.discovery import identification as ident


def test_sys_descr_identifies_cisco_switch():
    evidence = ident.identify_from_sys_descr(
        "Cisco IOS Software, C3560 Software (C3560-IPSERVICESK9-M), Version 15.0(2)SE11"
    )
    assert evidence is not None
    assert evidence.source == "SNMP"


def test_sys_descr_no_match_returns_none():
    assert ident.identify_from_sys_descr("Unidentified Widget Model ZZZ-1") is None
    assert ident.identify_from_sys_descr(None) is None


def test_sys_object_id_vendor_hint():
    vendor, _ = ident.identify_from_sys_object_id("1.3.6.1.4.1.9.1.516")
    assert vendor == "Cisco"


def test_sys_object_id_unknown_vendor():
    vendor, _ = ident.identify_from_sys_object_id("1.3.6.1.4.1.99999.1")
    assert vendor is None


def test_sys_object_id_matches_by_oid_arc_not_string_prefix():
    # 1.3.6.1.4.1.99999 must NOT match the Cisco prefix 1.3.6.1.4.1.9 just
    # because "99999" starts with the digit "9" as a string.
    vendor, _ = ident.identify_from_sys_object_id("1.3.6.1.4.1.99999.2.3")
    assert vendor is None
    vendor2, _ = ident.identify_from_sys_object_id("1.3.6.1.4.1.9.1.516")
    assert vendor2 == "Cisco"


def test_combine_evidence_agreement_raises_confidence():
    ev1 = ident.identify_from_sys_descr("cisco ios software catalyst")
    ev2 = ident.identify_from_ssh_banner("SSH-2.0-Cisco-1.25")
    result = ident.combine_evidence([e for e in (ev1, ev2) if e])
    assert result.device_type in (DeviceType.SWITCH, DeviceType.ROUTER)
    assert result.confidence > 0
    assert "SNMP" in result.sources


def test_combine_evidence_empty_is_unknown():
    result = ident.combine_evidence([])
    assert result.device_type == DeviceType.UNKNOWN
    assert result.confidence == 0.0


def test_confidence_never_reaches_absolute_certainty():
    ev = ident.identify_from_sys_descr("cisco ios software catalyst")
    result = ident.combine_evidence([ev])
    assert result.confidence < 1.0
