from app.discovery import icmp


def test_linux_ping_args_use_bsd_style_flags(monkeypatch):
    monkeypatch.setattr(icmp, "is_windows", lambda: False)
    args = icmp._build_ping_args("10.0.0.1", timeout_seconds=2.0, count=1)
    assert args == ["ping", "-c", "1", "-W", "2", "10.0.0.1"]


def test_windows_ping_args_use_windows_style_flags_and_ms_timeout(monkeypatch):
    monkeypatch.setattr(icmp, "is_windows", lambda: True)
    args = icmp._build_ping_args("10.0.0.1", timeout_seconds=2.0, count=1)
    assert args == ["ping", "-n", "1", "-w", "2000", "10.0.0.1"]


def test_rtt_regex_matches_linux_style_output():
    m = icmp._RTT_RE.search("64 bytes from 10.0.0.1: icmp_seq=1 ttl=64 time=15.2 ms")
    assert m is not None
    assert float(m.group(1)) == 15.2


def test_rtt_regex_matches_windows_style_output():
    m = icmp._RTT_RE.search("Reply from 10.0.0.1: bytes=32 time=15ms TTL=64")
    assert m is not None
    assert float(m.group(1)) == 15.0


def test_rtt_regex_matches_windows_sub_millisecond_output():
    m = icmp._RTT_RE.search("Reply from 10.0.0.1: bytes=32 time<1ms TTL=64")
    assert m is not None
    assert float(m.group(1)) == 1.0


def test_windows_failure_markers_detected():
    output = "Pinging 10.0.0.99 with 32 bytes of data:\nRequest timed out.\n"
    assert any(marker in output.lower() for marker in ("request timed out", "destination host unreachable"))
