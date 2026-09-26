#!/usr/bin/env python3
"""Print this container's IPv4 address on the network that routes to PEER (stdlib only).

  spark-bind-ip.py spark-master   -> e.g. 172.20.0.5 (spark-connect's address on `spark`)

Used by start-spark.sh for the Spark Connect server: spark-master is only on the internal
`spark` network, so the local address the kernel picks to reach it is spark-connect's `spark`
address. The driver's RPC, block manager and application UI bind to it alone, so none of them
listens on the `lab` network that workspaces join (CONTRACT Phase 3, Networks). A UDP
connect() sends nothing; it only asks the kernel for the route. Exits non-zero (and the
container restarts) rather than ever falling back to 0.0.0.0.
"""
import socket
import sys


def bind_ip(peer, port=7077):
    peer_ip = socket.getaddrinfo(peer, port, socket.AF_INET, socket.SOCK_DGRAM)[0][4][0]
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.connect((peer_ip, port))
        ip = s.getsockname()[0]
    if ip in ("0.0.0.0", "127.0.0.1"):
        raise RuntimeError(f"no routable local address towards {peer} ({peer_ip})")
    return ip


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: spark-bind-ip.py <peer-host>", file=sys.stderr)
        sys.exit(64)
    try:
        print(bind_ip(sys.argv[1]))
    except Exception as e:  # noqa: BLE001 - any failure stops the container start
        print(f"spark-bind-ip: {e}", file=sys.stderr)
        sys.exit(1)
