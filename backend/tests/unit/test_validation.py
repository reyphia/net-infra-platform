from app.configuration.validation import validate_proposed_config


def test_empty_change_is_blocking():
    report = validate_proposed_config([""], "cisco_ios")
    assert not report.ok
    assert report.blocking_issues


def test_denylisted_reload_is_blocked():
    report = validate_proposed_config(["reload"], "cisco_ios")
    assert not report.ok
    assert any("disallowed list" in i.message for i in report.blocking_issues)


def test_denylisted_erase_is_blocked():
    report = validate_proposed_config(["write erase"], "cisco_ios")
    assert not report.ok


def test_routeros_reset_is_blocked():
    report = validate_proposed_config(["/system reset-configuration"], "mikrotik_routeros")
    assert not report.ok


def test_normal_interface_change_passes():
    report = validate_proposed_config(["interface GigabitEthernet1/0/24", " description test"], "cisco_ios")
    assert report.ok


def test_risky_ssh_disable_warns_but_does_not_block():
    report = validate_proposed_config(["no ip ssh"], "cisco_ios")
    assert report.ok  # warning, not blocking
    assert any(i.severity == "warning" for i in report.issues)


def test_unknown_top_level_verb_warns():
    report = validate_proposed_config(["frobnicate-the-thing 123"], "cisco_ios")
    assert report.ok
    assert any("not a recognized" in i.message for i in report.issues)
