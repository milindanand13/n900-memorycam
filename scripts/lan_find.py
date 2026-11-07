#!/usr/bin/env python3
"""Find a device on the Mac's current Wi-Fi by its hardware (MAC) address.

IP addresses change with every network (home, hotspot, a friend's Wi-Fi); a device's
MAC address does not. Usage: python3 scripts/lan_find.py MAC PORT  -> prints the IP or exits 1.

It reads the Mac's ARP table (`arp -an`); if the MAC is not there yet, it knocks once on
PORT at every address of the local network (connect and close, no data sent) so the
table fills in, then reads it again. Networks bigger than 1024 addresses are not swept.
"""

from concurrent.futures import ThreadPoolExecutor
import ipaddress
import re
import socket
import subprocess
import sys


def norm(mac):
    """macOS prints 02:00:00:a:00:01; compare as 02:00:00:0a:00:01."""
    return ":".join(part.zfill(2) for part in mac.lower().replace("-", ":").split(":"))


def arp_table(run=subprocess.run):
    out = run(["arp", "-an"], capture_output=True, text=True, timeout=10).stdout
    return {norm(mac): ip for ip, mac in re.findall(r"\((\d+\.\d+\.\d+\.\d+)\) at ([0-9a-fA-F:]+) ", out)}


def local_network(run=subprocess.run):
    """The network of the Mac's default-route interface, for example 172.20.10.0/28."""
    route = run(["route", "-n", "get", "default"], capture_output=True, text=True, timeout=5).stdout
    iface = re.search(r"interface: (\S+)", route)
    if not iface:
        return None
    info = run(["ifconfig", iface.group(1)], capture_output=True, text=True, timeout=5).stdout
    m = re.search(r"inet (\d+\.\d+\.\d+\.\d+) netmask 0x([0-9a-f]{8})", info)
    if not m:
        return None
    return ipaddress.ip_network("{}/{}".format(m.group(1), bin(int(m.group(2), 16)).count("1")), strict=False)


def knock(ip, port, timeout=0.7):
    try:
        socket.create_connection((ip, port), timeout).close()
        return True
    except OSError:
        return False


def find(mac, port, limit=1024, table=arp_table, network=local_network, probe=knock):
    """IP of the device with this MAC that answers on port, or None."""
    mac = norm(mac)
    ip = table().get(mac)
    if ip and probe(ip, port, 3):
        return ip
    net = network()
    if net is None or net.num_addresses > limit:
        return None
    with ThreadPoolExecutor(64) as pool:
        list(pool.map(lambda host: probe(str(host), port), net.hosts()))
    ip = table().get(mac)
    return ip if ip and probe(ip, port, 3) else None


if __name__ == "__main__":
    found = find(sys.argv[1], int(sys.argv[2]))
    print(found or "not found")
    sys.exit(0 if found else 1)
