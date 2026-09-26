"""Job-side helpers (run in the /opt/lab/jobs virtualenv, started by the lab DAGs).

A job gets the lab-batch access token in LAB_BATCH_TOKEN (fetched by the DAG right before
the job starts) and never prints it. Trino is reached through Caddy with the lab CA, like
every other client (LAB_TRINO_HOST/PORT are derived from LAB_AUTH_URL by the image).
"""
import base64
import json
import os


def token():
    t = os.environ.get("LAB_BATCH_TOKEN")
    if not t:
        raise SystemExit("LAB_BATCH_TOKEN is not set (the DAG passes it)")
    return t


def claims(tok):
    part = tok.split(".")[1]
    return json.loads(base64.urlsafe_b64decode(part + "=" * (-len(part) % 4)))


def trino():
    """A Trino DB-API connection as lab-batch (JWT)."""
    import trino as trino_client
    tok = token()
    return trino_client.dbapi.connect(
        host=os.environ["LAB_TRINO_HOST"], port=int(os.environ["LAB_TRINO_PORT"]),
        http_scheme="https", verify=os.environ.get("SSL_CERT_FILE", True),
        auth=trino_client.auth.JWTAuthentication(tok),
        user=claims(tok)["preferred_username"], catalog="lakehouse", schema="analytics")


def query(cur, sql, params=None):
    cur.execute(sql, params) if params is not None else cur.execute(sql)
    return cur.fetchall()
