"""Pre-wired clients for the lab services. All of them act as the logged-in user and get
their token from lab_token() (lakehouse/token.py); none holds a storage key.

Endpoints come from the environment JupyterHub sets on every workspace
(config/jupyterhub/jupyterhub_config.py):

  LAB_TRINO_HOST / LAB_TRINO_PORT  public Trino host and port (TLS, lab CA)
  LAB_CATALOG_URL                  Iceberg REST catalog (Lakekeeper) on the lab network
  LAB_WAREHOUSE                    Lakekeeper warehouse name
  SPARK_REMOTE                     Spark Connect endpoint (profile `engineer`)
  SSL_CERT_FILE                    system CAs + the lab root
"""
import os

from .token import lab_token, token_claims


def _env(name, default=None):
    v = os.environ.get(name, default)
    if not v:
        raise RuntimeError(f"{name} is not set; is this workspace running under the lab's JupyterHub?")
    return v


def ca_bundle():
    return os.environ.get("SSL_CERT_FILE") or True


def whoami():
    """The logged-in user's name (the `preferred_username` claim, which Trino uses too)."""
    return token_claims(lab_token())["preferred_username"]


# ---------------------------------------------------------------------------- Trino
def _trino_auth():
    import requests
    import trino.auth

    class _FreshBearer(requests.auth.AuthBase):
        """Adds a current token to EVERY request, so a query that runs for hours keeps
        polling with a valid token."""
        def __call__(self, r):
            r.headers["Authorization"] = f"Bearer {lab_token()}"
            return r

    class LabJWTAuthentication(trino.auth.Authentication):
        def set_http_session(self, http_session):
            http_session.auth = _FreshBearer()
            return http_session

        def get_exceptions(self):
            return ()

    return LabJWTAuthentication()


def trino_connection(catalog="lakehouse", schema=None, **kwargs):
    """A trino.dbapi connection as the logged-in user."""
    import trino.dbapi
    return trino.dbapi.connect(
        host=_env("LAB_TRINO_HOST"), port=int(_env("LAB_TRINO_PORT")), http_scheme="https",
        verify=ca_bundle(), auth=_trino_auth(), user=whoami(),
        catalog=catalog, schema=schema, **kwargs)


def sql_engine(catalog="lakehouse", schema=None):
    """A SQLAlchemy engine for Trino (for JupySQL: `%sql engine`, or pandas.read_sql)."""
    import sqlalchemy
    path = f"/{catalog}" + (f"/{schema}" if schema else "")
    url = f"trino://{whoami()}@{_env('LAB_TRINO_HOST')}:{int(_env('LAB_TRINO_PORT'))}{path}"
    return sqlalchemy.create_engine(url, connect_args={
        "auth": _trino_auth(), "http_scheme": "https", "verify": ca_bundle()})


# ---------------------------------------------------------------------------- PyIceberg
def catalog(name="lakehouse"):
    """PyIceberg REST catalog (Lakekeeper) as the user, with vended storage credentials.
    Same as `pyiceberg.catalog.load_catalog("lakehouse")`: the config lives in
    $PYICEBERG_HOME/.pyiceberg.yaml and authenticates through lakehouse.pyiceberg_auth."""
    from pyiceberg.catalog import load_catalog
    return load_catalog(name)


# ---------------------------------------------------------------------------- DuckDB
def attach_lakehouse(con, alias="lakehouse"):
    """(Re-)ATTACH the lab catalog to a DuckDB connection with a fresh token. Storage access
    uses Lakekeeper-vended, table-scoped credentials (ADR-006); DuckDB gets no S3 key.
    Call it again to renew the token in a connection that lives for hours."""
    token = lab_token(min_ttl=900)
    if "'" in token:  # a JWT never contains quotes; refuse rather than build broken SQL
        raise RuntimeError("unexpected token format")
    con.execute("LOAD httpfs")
    con.execute("LOAD iceberg")
    con.execute(f"CREATE OR REPLACE SECRET lab_catalog (TYPE iceberg, TOKEN '{token}')")
    con.execute(f"DETACH DATABASE IF EXISTS {alias}")
    con.execute(
        f"ATTACH '{_env('LAB_WAREHOUSE', 'lakehouse')}' AS {alias} (TYPE iceberg, "
        f"ENDPOINT '{_env('LAB_CATALOG_URL')}', SECRET lab_catalog, "
        f"ACCESS_DELEGATION_MODE 'vended_credentials')")
    return con


def duckdb_connect(database=":memory:", alias="lakehouse"):
    """A DuckDB connection with the lab catalog attached as `alias`."""
    import duckdb
    return attach_lakehouse(duckdb.connect(database), alias)


# ---------------------------------------------------------------------------- Spark
def spark(app_name=None):
    """A Spark Connect session on the shared server (profile `engineer`), as the user.

    The session carries the user's name (Spark Connect user_id) and the user's token as
    the session's Iceberg catalog token (spark.sql.catalog.lakehouse.token), so the server
    can authorize the real user per session (OQ-15). Spark redacts *token* settings in its
    UI and logs.

    The catalog token is fixed when the session starts (Iceberg's own refresh would need a
    token exchange Keycloak rejects), and the session loses catalog access about a minute
    after it expires. So every call creates a NEW session (create(), never getOrCreate(),
    which would hand back an old session with an old token) with a token that has at least
    30 minutes left (the `jupyterhub` client's tokens live 1 h). For longer work, call
    spark() again; a session starts in 1-2 s."""
    from pyspark.sql import SparkSession
    remote = _env("SPARK_REMOTE", "sc://spark-connect:15002")
    b = SparkSession.builder.remote(f"{remote.rstrip('/')}/;user_id={whoami()}")
    b = b.config("spark.sql.catalog.lakehouse.token", lab_token(min_ttl=1800))
    if app_name:
        b = b.appName(app_name)
    return b.create()
