"""Read-only rule for the Trino MCP tool: which statements may run.

Decided on the parsed statement (sqlglot's Trino dialect), not on the first keyword: exactly
one statement; a query (SELECT / WITH / VALUES / set operations) with no write anywhere in
its tree (a CTE or subquery included); or SHOW / DESCRIBE / DESC; or EXPLAIN (never
EXPLAIN ANALYZE, which runs the statement) of a statement that is itself allowed. Anything
that does not parse is refused (fail closed). The approach follows the community server
akko-mcp-trino's sql_guard (evaluated for OQ-9; see mcp/README.md).

This rule is the product's "read-only" promise. The security boundary is still Trino: every
statement runs with the user's own token, so it can never do more than the user may.
"""
import re

_EXPLAIN_RE = re.compile(
    r"^\s*EXPLAIN\s*(?:\((?P<opts>[^)]*)\))?\s*(?P<analyze>ANALYZE\s+)?(?:VERBOSE\s+)?(?P<rest>.*)$",
    re.I | re.S)
# Trino's SHOW ... and DESCRIBE statements only read metadata (sqlglot keeps them opaque).
_READ_HEADS = ("SHOW", "DESCRIBE", "DESC")


def normalize(sql):
    """Trim; drop ONE trailing semicolon (models add it by habit; Trino refuses it)."""
    s = (sql or "").strip()
    if s.endswith(";"):
        s = s[:-1].rstrip()
    return s


def check(sql):
    """-> None if `sql` is an allowed read, else the reason it is refused."""
    s = normalize(sql)
    if not s:
        return "empty statement"
    head = s.split(None, 1)[0].upper()
    if head == "EXPLAIN":
        m = _EXPLAIN_RE.match(s)
        if m is None:
            return "malformed EXPLAIN"
        if m.group("analyze") or re.search(r"\bANALYZE\b", m.group("opts") or "", re.I):
            return "EXPLAIN ANALYZE runs the statement; only plain EXPLAIN is allowed"
        why = check(m.group("rest"))
        return None if why is None else f"EXPLAIN of a refused statement ({why})"
    if head in _READ_HEADS:
        if ";" in s:
            return "only one statement at a time"
        return None
    try:
        import logging

        import sqlglot
        from sqlglot import exp
        logging.getLogger("sqlglot").setLevel(logging.ERROR)   # its fallback warnings go to stderr
    except ImportError:  # pragma: no cover - the MCP venv always has it
        return "the SQL parser is missing; refusing"
    try:
        statements = [st for st in sqlglot.parse(s, read="trino") if st is not None]
    except Exception as e:  # noqa: BLE001 - cannot parse: refuse
        return f"could not parse the statement ({type(e).__name__})"
    if len(statements) != 1:
        return "only one statement at a time"
    st = statements[0]
    reads = (exp.Select, exp.Union, exp.Intersect, exp.Except, exp.Values, exp.Subquery,
             exp.Table)
    writes = (exp.Insert, exp.Update, exp.Delete, exp.Merge, exp.Create, exp.Drop, exp.Alter,
              exp.TruncateTable, exp.Grant, exp.Command, exp.Set, exp.Use, exp.Transaction,
              exp.Commit, exp.Rollback)
    if not isinstance(st, reads):
        return f"only SELECT, SHOW, DESCRIBE and EXPLAIN are allowed (got {st.key.upper()})"
    for node in st.walk():
        node = node[0] if isinstance(node, tuple) else node
        if isinstance(node, writes):
            return f"a {node.key.upper()} inside the query is not allowed"
    return None
