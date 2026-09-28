"""Unit tests for tests/ai/no_egress_probe.py (address parsing and the inside/outside rule)."""
import importlib.util
import ipaddress
import os
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("no_egress_probe", os.path.join(HERE, "no_egress_probe.py"))
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


class Probe(unittest.TestCase):
    def test_ipv4_address(self):
        # /proc/net/tcp stores IPv4 little-endian: 0100007F = 127.0.0.1, port 0x0FA0 = 4000.
        self.assertEqual(probe._addr("0100007F:0FA0"), ("127.0.0.1", 4000))
        self.assertEqual(probe._addr("0200000A:270F"), ("10.0.0.2", 9999))

    def test_ipv6_mapped_and_loopback(self):
        self.assertEqual(probe._addr("0000000000000000FFFF00000100007F:0050"), ("127.0.0.1", 80))
        self.assertEqual(probe._addr("00000000000000000000000001000000:0050"), ("::1", 80))

    def test_inside_rule(self):
        nets = [ipaddress.ip_network("127.0.0.0/8"), ipaddress.ip_network("::1/128"),
                ipaddress.ip_network("172.30.0.0/16")]
        self.assertTrue(probe.inside("172.30.4.5", nets))
        self.assertTrue(probe.inside("::1", nets))
        self.assertFalse(probe.inside("8.8.8.8", nets))
        self.assertFalse(probe.inside("172.31.0.1", nets))


if __name__ == "__main__":
    unittest.main()
