"""C1: does Lakekeeper return vended TEMPORARY (STS) credentials for loadTable(s2.events)?

Run in the duckdb container (stdlib only):  python /opt/s2/probe_vended.py
Asks exactly like DuckDB does (X-Iceberg-Access-Delegation: vended-credentials). Secrets are redacted.
Prints VENDED <key> <redacted value> lines, then VENDED_VERDICT sts|static|none.
"""
import json
import urllib.request

LK = "http://lakekeeper:8181/catalog/v1"


def get(url, headers=None):
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers or {}), timeout=20) as r:
        return json.load(r)


c = get(f"{LK}/config?warehouse=lakehouse")
prefix = {**c["defaults"], **c["overrides"]}["prefix"]
t = get(f"{LK}/{prefix}/namespaces/s2/tables/events", {"X-Iceberg-Access-Delegation": "vended-credentials"})
cfg = dict(t.get("config", {}))
for sc in t.get("storage-credentials", []) or []:
    print("VENDED storage-credentials.prefix", sc.get("prefix"))
    cfg.update(sc.get("config", {}))
for k, v in sorted(cfg.items()):
    if any(s in k for s in ("secret", "token")):
        v = f"<redacted len={len(v)}>"
    elif "key-id" in k:
        v = v[:4] + "...<redacted>"
    print("VENDED", k, v)
ak, tok = cfg.get("s3.access-key-id", ""), cfg.get("s3.session-token", "")
verdict = "sts" if ak.startswith("ASIA") and tok else ("static" if ak else "none")
print("VENDED_VERDICT", verdict)
