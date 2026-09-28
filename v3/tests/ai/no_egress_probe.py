"""Watch a container's TCP connections and fail on any peer outside the container's own
networks (CONTRACT Phase 5: "with no provider enabled, the lab makes no outbound AI calls").

Runs INSIDE the ai-gateway container (stdlib only; it only reads /proc, it opens no socket):

    docker compose exec -T -e PROBE_SECONDS=60 ai-gateway python3 - < tests/ai/no_egress_probe.py

Every PROBE_INTERVAL seconds (default 0.05) it reads /proc/net/tcp and /proc/net/tcp6 and
records the remote address of every socket that is not listening. "Inside" means loopback or
a subnet the container is directly attached to (routes without a gateway in
/proc/net/route: the lab's Docker networks). Anything else (the default route: internet or
the LAN, e.g. a model server on the host) is reported. Last line:
    NO_EGRESS_RESULT {"ok": bool, "samples": n, "peers": [...], "outside": [...]}
Exit 0 when nothing left the container's networks, 1 otherwise.

A connection that opens and closes between two samples can be missed; the gateway's calls to a
provider are HTTP requests that last far longer than 50 ms, and the rendered config (empty
model list) is the other half of the proof (tests/ai/gateway-e2e.sh checks both).
"""
import ipaddress
import json
import os
import socket
import struct
import sys
import time

LISTEN = "0A"


def local_networks():
    nets = [ipaddress.ip_network("127.0.0.0/8"), ipaddress.ip_network("::1/128")]
    with open("/proc/net/route") as f:
        next(f)
        for line in f:
            parts = line.split()
            dest, gateway, mask = parts[1], parts[2], parts[7]
            if gateway != "00000000" or dest == "00000000":
                continue  # routes via a gateway (the default route) are "outside"
            d = socket.inet_ntoa(struct.pack("<I", int(dest, 16)))
            m = socket.inet_ntoa(struct.pack("<I", int(mask, 16)))
            nets.append(ipaddress.ip_network(f"{d}/{m}", strict=False))
    return nets


def _addr(hexaddr):
    ip, port = hexaddr.split(":")
    if len(ip) == 8:
        return str(ipaddress.IPv4Address(struct.pack("<I", int(ip, 16)))), int(port, 16)
    raw = b"".join(struct.pack("<I", int(ip[i:i + 8], 16)) for i in range(0, 32, 8))
    a = ipaddress.IPv6Address(raw)
    return str(a.ipv4_mapped or a), int(port, 16)


def peers():
    out = set()
    for name in ("/proc/net/tcp", "/proc/net/tcp6"):
        try:
            with open(name) as f:
                next(f)
                for line in f:
                    parts = line.split()
                    if parts[3] == LISTEN:
                        continue
                    ip, port = _addr(parts[2])
                    if ip not in ("0.0.0.0", "::"):
                        out.add((ip, port))
        except FileNotFoundError:
            pass
    return out


def inside(ip, nets):
    a = ipaddress.ip_address(ip)
    return any(a.version == n.version and a in n for n in nets)


def main():
    seconds = float(os.environ.get("PROBE_SECONDS", "30"))
    interval = float(os.environ.get("PROBE_INTERVAL", "0.05"))
    nets = local_networks()
    seen, samples = set(), 0
    deadline = time.time() + seconds
    while time.time() < deadline:
        seen |= peers()
        samples += 1
        time.sleep(interval)
    outside = sorted(f"{ip}:{port}" for ip, port in seen if not inside(ip, nets))
    result = {"ok": not outside, "samples": samples, "seconds": seconds,
              "networks": [str(n) for n in nets],
              "peers": sorted(f"{ip}:{port}" for ip, port in seen), "outside": outside}
    print("NO_EGRESS_RESULT " + json.dumps(result, sort_keys=True), flush=True)
    return 0 if not outside else 1


if __name__ == "__main__":
    sys.exit(main())
