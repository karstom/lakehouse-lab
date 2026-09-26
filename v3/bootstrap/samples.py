"""Sample data: `python3 -m bootstrap.samples` (one-shot, idempotent; Python stdlib only).

Creates the Iceberg tables lakehouse.samples.{region,nation,customer,orders,lineitem} with
Trino `CREATE TABLE AS` from Trino's built-in tpch connector (`tiny` scale). Nothing is
downloaded. It runs after Trino is healthy, so it cannot be part of the main bootstrap
(Trino starts only after bootstrap completed).

Identity: the service account of the Keycloak client `trino` (client credentials), whose
Trino principal is `service-account-trino`. config/trino/rules.json lets that principal
read tpch and write only the `samples` schema; Lakekeeper already trusts it (modify +
create on the warehouse, lakekeeper_authz.py). No user password is involved, so this works
with LAB_SEED_TEST_USERS=false.

Idempotent: a table that exists is left alone (it is never re-created or overwritten, so
a lab admin's changes to the samples survive re-runs). A second run reports "unchanged".
The schema is created only when missing.

Trino is reached like every other client: https://trino.<LAB_DOMAIN>[:port] through Caddy,
trusting the lab CA (SSL_CERT_FILE). The origin is derived from LAB_AUTH_URL, the single
source of public origins (INV_V3_PUBLIC_ORIGIN_SINGLE_SOURCE), never rebuilt from the port.
"""
import os
import sys
import time

from . import keycloak, web

CATALOG = "lakehouse"
SCHEMA = "samples"
SOURCE = "tpch.tiny"
# Small tables first, so a partial first run still leaves the joins' dimension tables.
TABLES = ("region", "nation", "customer", "orders", "lineitem")
SERVICE_CLIENT = "trino"


def env(name):
    v = os.environ.get(name)
    if not v:
        raise SystemExit(f"[samples] missing required environment variable {name}")
    return v


def trino_origin():
    auth = env("LAB_AUTH_URL").rstrip("/")
    prefix = "https://auth."
    if not auth.startswith(prefix):
        raise SystemExit(f"[samples] LAB_AUTH_URL must start with {prefix}: {auth}")
    return "https://trino." + auth[len(prefix):]


class Trino:
    """Minimal Trino client protocol (POST /v1/statement, follow nextUri)."""

    def __init__(self, origin, secret):
        self.origin = origin
        self.secret = secret

    def _headers(self):
        # A fresh token per statement: access tokens last minutes, a cold CTAS may not.
        token = keycloak.client_credentials_token(SERVICE_CLIENT, self.secret)
        return {"Authorization": f"Bearer {token}", "X-Trino-Source": "lab-bootstrap-samples"}

    def query(self, sql):
        """Returns (rows, update_count). Raises RuntimeError on a query error."""
        h = self._headers()
        _, res, _ = web.request("POST", f"{self.origin}/v1/statement", data=sql.encode(),
                                headers={**h, "Content-Type": "text/plain"}, timeout=60)
        rows = []
        while True:
            if res.get("error"):
                e = res["error"]
                raise RuntimeError(f"{e.get('errorName')}: {e.get('message')} [{sql}]")
            rows.extend(res.get("data") or [])
            nxt = res.get("nextUri")
            if not nxt:
                return rows, res.get("updateCount")
            _, res, _ = web.request("GET", nxt, headers=h, timeout=120)


def wait_ready(origin, timeout=300):
    """Trino's /v1/info answers before the coordinator accepts queries ('starting')."""
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        try:
            _, info, _ = web.request("GET", f"{origin}/v1/info", expect=None, timeout=5)
            if isinstance(info, dict) and info.get("starting") is False:
                return
            last = info
        except OSError as e:
            last = str(e)
        time.sleep(3)
    raise RuntimeError(f"Trino at {origin} not ready after {timeout}s ({last})")


def ensure_samples(trino):
    """Create the schema and any missing sample table. Returns the list of created tables."""
    schemas = {r[0] for r in trino.query(f"SHOW SCHEMAS FROM {CATALOG}")[0]}
    if SCHEMA not in schemas:
        trino.query(f"CREATE SCHEMA IF NOT EXISTS {CATALOG}.{SCHEMA}")
        print(f"[samples] created schema {CATALOG}.{SCHEMA}", flush=True)
    existing = {r[0] for r in trino.query(f"SHOW TABLES FROM {CATALOG}.{SCHEMA}")[0]}
    created = []
    for t in TABLES:
        if t in existing:
            continue
        _, n = trino.query(f"CREATE TABLE IF NOT EXISTS {CATALOG}.{SCHEMA}.{t} "
                           f"AS SELECT * FROM {SOURCE}.{t}")
        print(f"[samples] created {CATALOG}.{SCHEMA}.{t} ({n} rows from {SOURCE}.{t})", flush=True)
        created.append(t)
    return created


def main():
    t0 = time.time()
    origin = trino_origin()
    wait_ready(origin)
    created = ensure_samples(Trino(origin, env("OIDC_CLIENT_SECRET_TRINO")))
    state = f"created {', '.join(created)}" if created else "unchanged"
    print(f"[samples] {CATALOG}.{SCHEMA}: {state} ({time.time() - t0:.1f}s)", flush=True)


if __name__ == "__main__":
    try:
        main()
    except (web.HTTPError, RuntimeError) as e:
        print(f"[samples] FAILED: {e}", file=sys.stderr)
        sys.exit(1)
