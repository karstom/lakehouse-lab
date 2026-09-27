"""Trino as the logged-in user, for the MCP tools: one read-only statement, at most
MAX_ROWS rows, at most MAX_SECONDS seconds (Trino's own query_max_run_time, so the engine
stops it, plus a client timeout)."""
import os
import time

from . import sqlguard
from .common import MAX_ROWS, MAX_SECONDS, ToolFailure, clip, scrub, user_token


def _connect(catalog="lakehouse", schema=None, timeout=MAX_SECONDS):
    import trino
    host = os.environ.get("LAB_TRINO_HOST")
    port = os.environ.get("LAB_TRINO_PORT")
    if not host or not port:
        raise ToolFailure("unavailable", "LAB_TRINO_HOST / LAB_TRINO_PORT are not set")
    token = user_token(min_ttl=timeout + 30)
    from lakehouse.token import token_claims
    user = token_claims(token).get("preferred_username")
    return trino.dbapi.connect(
        host=host, port=int(port), http_scheme="https",
        verify=os.environ.get("SSL_CERT_FILE") or True,
        auth=trino.auth.JWTAuthentication(token), user=user,
        catalog=catalog, schema=schema, source="lab-mcp",
        session_properties={"query_max_run_time": f"{int(timeout)}s"},
        request_timeout=timeout + 5), user


def run(sql, max_rows=50, catalog="lakehouse", schema=None, timeout=MAX_SECONDS,
        guarded=True):
    """-> {"columns", "rows", "row_count", "truncated", "as_user", "seconds"}.
    `guarded=False` only for statements this package builds itself from validated
    identifiers (still reads)."""
    import trino
    if guarded:
        why = sqlguard.check(sql)
        if why:
            raise ToolFailure("invalid", f"refused (read-only): {why}. This tool runs only "
                              f"SELECT, SHOW, DESCRIBE and EXPLAIN.")
    sql = sqlguard.normalize(sql)
    max_rows = max(1, min(int(max_rows), MAX_ROWS))
    timeout = max(1, min(int(timeout), MAX_SECONDS))
    conn, user = _connect(catalog, schema, timeout)
    t0 = time.time()
    cur = conn.cursor()
    try:
        cur.execute(sql)
        rows = cur.fetchmany(max_rows + 1)
        truncated = len(rows) > max_rows
        rows = rows[:max_rows]
        cols = [d[0] for d in (cur.description or [])]
        if truncated:
            try:
                cur.cancel()
            except Exception:  # noqa: BLE001 - best effort
                pass
    except trino.exceptions.TrinoQueryError as e:
        # TrinoUserError is a TrinoQueryError; the time limit arrives as INSUFFICIENT_RESOURCES.
        name = getattr(e, "error_name", None) or "QUERY_ERROR"
        msg = scrub(getattr(e, "message", None) or str(e))[:400]
        if name == "EXCEEDED_TIME_LIMIT":
            raise ToolFailure("invalid", f"the query ran longer than {timeout}s and Trino "
                              f"stopped it; narrow it down") from None
        if name == "PERMISSION_DENIED" or "Access Denied" in msg:
            raise ToolFailure("denied", f"Trino refused this for {user}: {msg}") from None
        kind = "invalid" if isinstance(e, trino.exceptions.TrinoUserError) else "error"
        raise ToolFailure(kind, f"Trino: {name}: {msg}") from None
    except trino.exceptions.HttpError as e:
        text = scrub(str(e))[:300]
        if " 401" in text or "401:" in text:
            raise ToolFailure("denied", f"Trino did not accept your login: {text}") from None
        raise ToolFailure("unavailable", f"Trino: {text}") from None
    finally:
        try:
            conn.close()
        except Exception:  # noqa: BLE001
            pass
    return {"as_user": user, "columns": cols,
            "rows": [[clip(v) for v in r] for r in rows],
            "row_count": len(rows), "truncated": truncated,
            "row_limit": max_rows, "seconds": round(time.time() - t0, 2)}
