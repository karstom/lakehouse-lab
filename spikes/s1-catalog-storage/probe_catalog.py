"""Ask Lakekeeper for the table config it hands out per access-delegation mode (secrets redacted).

Run inside any container on the v3-s1 network:  python3 - < probe_catalog.py
Prints one line per mode: PROBE <mode> <json of config keys -> redacted values>.
"""
import json
import urllib.request

LK = "http://lakekeeper:8181/catalog/v1"


def get(url, headers=None):
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)


c = get(f"{LK}/config?warehouse=lakehouse")
prefix = {**c["defaults"], **c["overrides"]}["prefix"]
for mode in ("remote-signing", "vended-credentials"):
    t = get(f"{LK}/{prefix}/namespaces/s1/tables/events",
            {"X-Iceberg-Access-Delegation": mode})
    cfg = t.get("config", {})
    for sc in t.get("storage-credentials", []) or []:
        cfg.update({"storage-credentials." + k: v for k, v in sc.get("config", {}).items()})
    red = {k: (v[:4] + "...<redacted>" if any(s in k for s in ("secret", "token", "key-id")) else v)
           for k, v in sorted(cfg.items())}
    print("PROBE", mode, json.dumps(red))
