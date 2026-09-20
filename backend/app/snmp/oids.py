"""Well-known OIDs used by discovery, identification, interfaces, and LLDP/CDP.

Sources: RFC 1213 (MIB-II), RFC 2863 (IF-MIB), RFC 2922 / IEEE 802.1AB
(LLDP-MIB), and Cisco's CISCO-CDP-MIB (proprietary but publicly documented).
"""

# --- System group (RFC 1213) ---
SYS_DESCR = "1.3.6.1.2.1.1.1.0"
SYS_OBJECT_ID = "1.3.6.1.2.1.1.2.0"
SYS_UPTIME = "1.3.6.1.2.1.1.3.0"
SYS_CONTACT = "1.3.6.1.2.1.1.4.0"
SYS_NAME = "1.3.6.1.2.1.1.5.0"
SYS_LOCATION = "1.3.6.1.2.1.1.6.0"

# --- IF-MIB (RFC 2863) — walk these tables ---
IF_INDEX = "1.3.6.1.2.1.2.2.1.1"
IF_DESCR = "1.3.6.1.2.1.2.2.1.2"
IF_TYPE = "1.3.6.1.2.1.2.2.1.3"
IF_MTU = "1.3.6.1.2.1.2.2.1.4"
IF_SPEED = "1.3.6.1.2.1.2.2.1.5"
IF_PHYS_ADDRESS = "1.3.6.1.2.1.2.2.1.6"
IF_ADMIN_STATUS = "1.3.6.1.2.1.2.2.1.7"  # 1=up 2=down 3=testing
IF_OPER_STATUS = "1.3.6.1.2.1.2.2.1.8"
IF_IN_OCTETS = "1.3.6.1.2.1.2.2.1.10"
IF_IN_ERRORS = "1.3.6.1.2.1.2.2.1.14"
IF_IN_DISCARDS = "1.3.6.1.2.1.2.2.1.13"
IF_OUT_OCTETS = "1.3.6.1.2.1.2.2.1.16"
IF_OUT_ERRORS = "1.3.6.1.2.1.2.2.1.20"
IF_OUT_DISCARDS = "1.3.6.1.2.1.2.2.1.19"
IF_NAME = "1.3.6.1.2.1.31.1.1.1.1"  # IF-MIB ifXTable ifName (more human friendly than ifDescr)
IF_HIGH_SPEED = "1.3.6.1.2.1.31.1.1.1.15"  # ifHighSpeed, in Mbps

# --- IP-MIB / ipAddrTable (legacy but broadly supported) ---
IP_AD_ENT_IF_INDEX = "1.3.6.1.2.1.4.20.1.2"
IP_AD_ENT_NET_MASK = "1.3.6.1.2.1.4.20.1.3"

# --- ARP / IP-to-MAC via ipNetToMediaTable ---
IP_NET_TO_MEDIA_PHYS_ADDRESS = "1.3.6.1.2.1.4.22.1.2"

# --- Host resources (CPU/memory), where supported ---
HR_PROCESSOR_LOAD = "1.3.6.1.2.1.25.3.3.1.2"  # HOST-RESOURCES-MIB hrProcessorLoad (per CPU, %)
HR_STORAGE_DESCR = "1.3.6.1.2.1.25.2.3.1.3"
HR_STORAGE_ALLOCATION_UNITS = "1.3.6.1.2.1.25.2.3.1.4"
HR_STORAGE_SIZE = "1.3.6.1.2.1.25.2.3.1.5"
HR_STORAGE_USED = "1.3.6.1.2.1.25.2.3.1.6"

# --- Cisco-specific CPU (widely supported on IOS/IOS-XE) ---
CISCO_CPU_5MIN = "1.3.6.1.4.1.9.9.109.1.1.1.1.8"  # cpmCPUTotal5minRev

# --- LLDP-MIB (IEEE 802.1AB) ---
LLDP_LOC_PORT_ID = "1.0.8802.1.1.2.1.3.7.1.3"
LLDP_REM_CHASSIS_ID = "1.0.8802.1.1.2.1.4.1.1.5"
LLDP_REM_PORT_ID = "1.0.8802.1.1.2.1.4.1.1.7"
LLDP_REM_PORT_DESCR = "1.0.8802.1.1.2.1.4.1.1.8"
LLDP_REM_SYS_NAME = "1.0.8802.1.1.2.1.4.1.1.9"
LLDP_REM_MGMT_ADDR = "1.0.8802.1.1.2.1.4.2.1.3"

# --- CISCO-CDP-MIB (proprietary, Cisco devices only) ---
CDP_CACHE_ADDRESS = "1.3.6.1.4.1.9.9.23.1.2.1.1.4"
CDP_CACHE_DEVICE_ID = "1.3.6.1.4.1.9.9.23.1.2.1.1.6"
CDP_CACHE_DEVICE_PORT = "1.3.6.1.4.1.9.9.23.1.2.1.1.7"
CDP_CACHE_PLATFORM = "1.3.6.1.4.1.9.9.23.1.2.1.1.8"

# --- dot1qVlanStaticTable (Q-BRIDGE-MIB), where supported ---
DOT1Q_VLAN_STATIC_NAME = "1.3.6.1.2.1.17.7.1.4.3.1.1"
