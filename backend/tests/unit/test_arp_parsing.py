from app.discovery.arp import _IP_NEIGH_LINE, _PROC_NET_ARP_LINE, parse_windows_arp_output


def test_ip_neigh_line_parses_reachable_entry():
    line = "192.168.1.1 dev eth0 lladdr aa:bb:cc:dd:ee:ff REACHABLE"
    m = _IP_NEIGH_LINE.match(line)
    assert m is not None
    assert m.group("ip") == "192.168.1.1"
    assert m.group("mac") == "aa:bb:cc:dd:ee:ff"
    assert m.group("dev") == "eth0"
    assert m.group("state") == "REACHABLE"


def test_ip_neigh_line_ignores_incomplete_entries():
    line = "192.168.1.50 dev eth0  FAILED"
    assert _IP_NEIGH_LINE.match(line) is None


def test_proc_net_arp_line_parses_complete_entry():
    line = "192.168.1.1     0x1         0x2         aa:bb:cc:dd:ee:ff     *        eth0"
    m = _PROC_NET_ARP_LINE.match(line)
    assert m is not None
    assert m.group("ip") == "192.168.1.1"
    assert m.group("mac") == "aa:bb:cc:dd:ee:ff"


# --- Windows `arp -a` parsing -------------------------------------------------

WINDOWS_ARP_OUTPUT = """
Interface: 192.168.1.5 --- 0x3
  Internet Address      Physical Address      Type
  192.168.1.1            00-11-22-33-44-55     dynamic
  192.168.1.254          aa-bb-cc-dd-ee-ff     static
  192.168.1.255          ff-ff-ff-ff-ff-ff     static
  224.0.0.22             01-00-5e-00-00-16     static

Interface: 10.0.0.8 --- 0x9
  Internet Address      Physical Address      Type
  10.0.0.1               00-1a-2b-3c-4d-5e     dynamic
"""


def test_parse_windows_arp_output_extracts_dynamic_entries():
    entries = parse_windows_arp_output(WINDOWS_ARP_OUTPUT)
    ips = {e.ip_address for e in entries}
    assert "192.168.1.1" in ips
    assert "10.0.0.1" in ips


def test_parse_windows_arp_output_normalizes_mac_format():
    entries = parse_windows_arp_output(WINDOWS_ARP_OUTPUT)
    entry = next(e for e in entries if e.ip_address == "192.168.1.1")
    assert entry.mac_address == "00:11:22:33:44:55"  # dashes converted to colons, lowercased


def test_parse_windows_arp_output_skips_broadcast_and_multicast_noise():
    entries = parse_windows_arp_output(WINDOWS_ARP_OUTPUT)
    ips = {e.ip_address for e in entries}
    assert "192.168.1.255" not in ips  # broadcast MAC ff-ff-ff-ff-ff-ff filtered out


def test_parse_windows_arp_output_tracks_interface_per_entry():
    entries = parse_windows_arp_output(WINDOWS_ARP_OUTPUT)
    first_iface_entry = next(e for e in entries if e.ip_address == "192.168.1.1")
    second_iface_entry = next(e for e in entries if e.ip_address == "10.0.0.1")
    assert first_iface_entry.interface == "192.168.1.5"
    assert second_iface_entry.interface == "10.0.0.8"


def test_parse_windows_arp_output_captures_entry_type():
    entries = parse_windows_arp_output(WINDOWS_ARP_OUTPUT)
    static_entry = next(e for e in entries if e.ip_address == "192.168.1.254")
    assert static_entry.state == "STATIC"


def test_parse_windows_arp_output_empty_input():
    assert parse_windows_arp_output("") == []
    assert parse_windows_arp_output("No ARP Entries Found.") == []
