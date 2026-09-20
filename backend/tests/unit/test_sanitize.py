from app.configuration.sanitize import sanitize_config


def test_redacts_enable_secret():
    cfg = "enable secret 5 $1$abc$def123\ninterface Gi0/1\n description uplink"
    out = sanitize_config(cfg)
    assert "$1$abc$def123" not in out
    assert "<redacted>" in out
    assert "description uplink" in out  # untouched, non-secret lines preserved


def test_redacts_snmp_community():
    cfg = "snmp-server community SuperSecret123 RO"
    out = sanitize_config(cfg)
    assert "SuperSecret123" not in out


def test_redacts_username_secret():
    cfg = "username admin secret 5 $1$xyz$hashedvalue"
    out = sanitize_config(cfg)
    assert "$1$xyz$hashedvalue" not in out


def test_redacts_routeros_password():
    cfg = "/user set admin password=SuperSecret"
    out = sanitize_config(cfg)
    assert "SuperSecret" not in out


def test_does_not_touch_unrelated_lines():
    cfg = "interface Gi0/1\n switchport access vlan 20\n no shutdown"
    assert sanitize_config(cfg) == cfg
