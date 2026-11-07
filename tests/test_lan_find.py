"""Offline checks for scripts/lan_find.py. No network needed."""
import ipaddress
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'scripts'))
import lan_find  # noqa: E402

ARP = """? (172.20.10.1) at 02:00:00:00:00:05 on en0 ifscope [ethernet]
? (172.20.10.8) at 02:00:00:a:00:01 on en0 ifscope [ethernet]
? (172.20.10.9) at (incomplete) on en0 ifscope [ethernet]
"""


class Out:
    def __init__(self, text):
        self.stdout = text


class LanFindChecks(unittest.TestCase):
    def test_arp_table_pads_macos_short_octets(self):
        table = lan_find.arp_table(run=lambda *a, **k: Out(ARP))
        self.assertEqual(table['02:00:00:0a:00:01'], '172.20.10.8')
        self.assertNotIn('(incomplete)', ' '.join(table))

    def test_known_device_is_found_without_a_sweep(self):
        swept = []
        ip = lan_find.find('02:00:00:0A:00:01', 9100, table=lambda: {'02:00:00:0a:00:01': '172.20.10.8'},
                           network=lambda: swept.append(1), probe=lambda ip, port, t=0: True)
        self.assertEqual(ip, '172.20.10.8')
        self.assertEqual(swept, [])

    def test_unknown_device_triggers_one_sweep_then_lookup(self):
        tables = [{}, {'02:00:00:0a:00:01': '172.20.10.8'}]
        knocked = []
        ip = lan_find.find('02:00:00:0a:00:01', 9100, table=lambda: tables.pop(0),
                           network=lambda: ipaddress.ip_network('172.20.10.0/28'),
                           probe=lambda ip, port, t=0: knocked.append(ip) or True)
        self.assertEqual(ip, '172.20.10.8')
        self.assertEqual(len(knocked), 15)  # 14 hosts swept, then the found one confirmed

    def test_other_device_on_the_same_port_is_never_chosen(self):
        ip = lan_find.find('02:00:00:0a:00:01', 9100, table=lambda: {'02:00:00:00:00:09': '192.168.1.8'},
                           network=lambda: ipaddress.ip_network('192.168.1.0/24'), probe=lambda ip, port, t=0: True)
        self.assertIsNone(ip)

    def test_huge_networks_are_not_swept(self):
        ip = lan_find.find('aa:bb:cc:dd:ee:ff', 22, table=lambda: {},
                           network=lambda: ipaddress.ip_network('10.0.0.0/16'),
                           probe=lambda ip, port, t=0: self.fail('swept a /16'))
        self.assertIsNone(ip)


if __name__ == '__main__':
    unittest.main()
