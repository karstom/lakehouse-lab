#!/usr/bin/env python3
"""Container healthcheck for the Spark image (stdlib only).

  spark-health.py http://localhost:8080/json/   -> healthy on HTTP 200 (and, for the master,
                                                   at least one ALIVE worker)
  spark-health.py tcp localhost 15002           -> healthy when the port accepts connections
"""
import json
import socket
import sys
import urllib.request


def main(argv):
    if argv[:1] == ["tcp"]:
        with socket.create_connection((argv[1], int(argv[2])), timeout=3):
            return 0
    with urllib.request.urlopen(argv[0], timeout=3) as r:
        body = r.read()
    if argv[0].endswith("/json/"):
        state = json.loads(body)
        if "workers" in state:  # master: ready once a worker has registered
            return 0 if any(w.get("state") == "ALIVE" for w in state["workers"]) else 1
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except Exception as e:  # noqa: BLE001 - any failure means unhealthy
        print(f"unhealthy: {e}", file=sys.stderr)
        sys.exit(1)
