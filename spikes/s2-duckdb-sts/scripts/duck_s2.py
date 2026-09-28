"""C2 + C3: DuckDB ATTACHes Lakekeeper and reads/writes s2.events using ONLY vended credentials.

Run in the duckdb container:  python /opt/s2/duck_s2.py
The session creates NO secret itself. The only S3 credentials it can use are the ones the iceberg
extension receives from Lakekeeper's loadTable response (vended STS creds).
Output lines start with DUCK_ (parsed by test.sh). Secret values are never printed.
"""
import os
import sys

import duckdb

CATALOG = "http://lakekeeper:8181/catalog"


def show_secrets(con, label):
    rows = con.sql("SELECT name, type, provider, persistent, scope, secret_string "
                   "FROM duckdb_secrets(redact=true)").fetchall()
    print(f"DUCK_SECRETS {label} count={len(rows)}")
    for name, typ, prov, pers, scope, s in rows:
        # secret_string is redacted by DuckDB; only report which key id family is in it
        kid = next((p.split("=", 1)[1][:4] for p in s.split(";") if p.startswith("key_id=")), "")
        print(f"DUCK_SECRET {label} name={name} type={typ} provider={prov} persistent={pers} "
              f"scope={scope} key_id_prefix={kid}")
    return rows


env_hits = sorted(k for k in os.environ if k.startswith("AWS_") or "S3" in k.upper())
print("DUCK_ENV_AWS_VARS", env_hits or "none")
print("DUCK_AWS_DIR", "present" if os.path.exists(os.path.expanduser("~/.aws")) else "absent")
print("DUCK_VERSION", duckdb.__version__)

con = duckdb.connect()
for ext in ("httpfs", "avro", "iceberg"):
    con.load_extension(ext)
print("DUCK_EXT", con.sql("SELECT extension_name, extension_version FROM duckdb_extensions() "
                          "WHERE extension_name IN ('httpfs','avro','iceberg') ORDER BY 1").fetchall())
show_secrets(con, "before-attach")

mode = sys.argv[1] if len(sys.argv) > 1 else "vended_credentials"
con.sql(f"ATTACH 'lakehouse' AS lk (TYPE iceberg, ENDPOINT '{CATALOG}', AUTHORIZATION_TYPE 'none', "
        f"ACCESS_DELEGATION_MODE '{mode}')")
print("DUCK_ATTACH ok mode", mode)
print("DUCK_TABLES", con.sql("SHOW ALL TABLES").fetchall())

try:
    n, s = con.sql("SELECT count(*), sum(amount) FROM lk.s2.events").fetchone()
    print(f"DUCK_READ {n} {s}")
except Exception as e:  # noqa: BLE001
    print("DUCK_READ_ERROR", type(e).__name__, str(e).replace("\n", " ")[:600])
    sys.exit(3)
show_secrets(con, "after-read")

if mode != "vended_credentials":
    sys.exit(0)
try:
    con.sql("INSERT INTO lk.s2.events VALUES (100, 'duck', 1000.0)")
    n, s = con.sql("SELECT count(*), sum(amount) FROM lk.s2.events").fetchone()
    print(f"DUCK_INSERT ok DUCK_AFTER {n} {s}")
except Exception as e:  # noqa: BLE001
    print("DUCK_INSERT_ERROR", type(e).__name__, str(e).replace("\n", " ")[:600])
