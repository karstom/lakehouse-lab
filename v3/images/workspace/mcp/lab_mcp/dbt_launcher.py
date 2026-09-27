"""Start the official dbt-mcp server (dbt Labs, pinned DBT_MCP_VERSION) for one dbt project,
as the logged-in user, with only its read-only local tools.

  lab-mcp dbt            your project: ~/starter/dbt_lakehouse (or $LAB_DBT_PROJECT_DIR)
  lab-mcp dbt-analytics  the shared `analytics` project: the image's pristine starter project
                         with target `analytics` (what the lab_dbt_build DAG builds into
                         lakehouse.analytics), copied to ~/.cache/lab-mcp/analytics so dbt
                         can write its target/ folder

Tools (allowlist, DBT_MCP_ENABLE_TOOLS): list, parse, get_lineage_dev, get_node_details_dev.
They read the project and its manifest; none of them builds, runs, tests or queries data
(build/run/test/show/compile/docs/clone are not enabled). Every dbt-Platform feature (remote
tools, Discovery, Semantic Layer, Admin API, SQL, product docs, LSP download) is off, and so
is dbt-mcp's usage tracking (DO_NOT_TRACK): the server makes no outbound calls. dbt itself
runs through the lab's `dbt` shim (/opt/lakehouse/bin/dbt), which gives dbt-trino the user's
own token; `parse` and `list` never connect to Trino.
"""
import filecmp
import os
import shutil
import sys

MCP_HOME = os.environ.get("LAB_MCP_HOME", "/opt/lakehouse/mcp")
VENV_BIN = os.path.join(MCP_HOME, "venv", "bin")
STARTER = "/opt/lakehouse/starter/dbt_lakehouse"
DBT_SHIM = "/opt/lakehouse/bin/dbt"
READ_ONLY_TOOLS = ("list", "parse", "get_lineage_dev", "get_node_details_dev")
OFF = ("DISABLE_REMOTE", "DISABLE_DISCOVERY", "DISABLE_SEMANTIC_LAYER", "DISABLE_ADMIN_API",
       "DISABLE_SQL", "DISABLE_PRODUCT_DOCS", "DISABLE_LSP", "DISABLE_DBT_CODEGEN",
       "DISABLE_MCP_SERVER_METADATA", "DISABLE_MCP_APPS")

ANALYTICS_PROFILE = """\
# Written by lab-mcp dbt-analytics (read-only lineage of the shared `analytics` project).
# The same project the lab_dbt_build DAG builds, with target `analytics`. dbt-mcp only
# parses and lists it; it never builds. If dbt ever connects, it does so as YOU.
lakehouse:
  target: analytics
  outputs:
    analytics:
      type: trino
      method: jwt
      jwt_token: "{{ env_var('DBT_ENV_SECRET_LAB_TOKEN') }}"
      user: "{{ env_var('JUPYTERHUB_USER') }}"
      host: "{{ env_var('LAB_TRINO_HOST') }}"
      port: "{{ env_var('LAB_TRINO_PORT') | as_number }}"
      http_scheme: https
      cert: "{{ env_var('SSL_CERT_FILE') }}"
      database: lakehouse
      schema: analytics
      threads: 1
"""


def _sync_tree(src, dest):
    """Make dest's project files equal to src's (target/, logs/ and dbt_packages/ kept)."""
    keep = {"target", "logs", "dbt_packages"}
    os.makedirs(dest, exist_ok=True)
    for name in os.listdir(dest):
        if name in keep:
            continue
        if not os.path.exists(os.path.join(src, name)):
            p = os.path.join(dest, name)
            shutil.rmtree(p) if os.path.isdir(p) and not os.path.islink(p) else os.remove(p)
    for name in os.listdir(src):
        if name in keep:
            continue
        s, d = os.path.join(src, name), os.path.join(dest, name)
        if os.path.isdir(s):
            _sync_tree(s, d)
        elif not os.path.isfile(d) or not filecmp.cmp(s, d, shallow=False):
            shutil.copyfile(s, d)


def analytics_project(home):
    root = os.path.join(home, ".cache", "lab-mcp", "analytics")
    proj = os.path.join(root, "dbt_lakehouse")
    _sync_tree(STARTER, proj)
    prof_dir = os.path.join(root, "profiles")
    os.makedirs(prof_dir, exist_ok=True)
    prof = os.path.join(prof_dir, "profiles.yml")
    if not os.path.isfile(prof) or open(prof, encoding="utf-8").read() != ANALYTICS_PROFILE:
        with open(prof, "w", encoding="utf-8") as f:
            f.write(ANALYTICS_PROFILE)
    return proj, prof_dir


def server_env(which, home, base_env=None):
    """-> (env, project_dir) for dbt-mcp; raises SystemExit with a message when the project
    is missing."""
    env = dict(base_env if base_env is not None else os.environ)
    if which == "analytics":
        if not os.path.isdir(STARTER):
            raise SystemExit(f"lab-mcp dbt-analytics: {STARTER} is missing from this image")
        proj, prof_dir = analytics_project(home)
        env["DBT_PROFILES_DIR"] = prof_dir
    else:
        proj = env.get("LAB_DBT_PROJECT_DIR") or os.path.join(home, "starter", "dbt_lakehouse")
        if not os.path.isfile(os.path.join(proj, "dbt_project.yml")):
            raise SystemExit(
                f"lab-mcp dbt: no dbt project at {proj} (set LAB_DBT_PROJECT_DIR to your "
                f"project's folder, the one with dbt_project.yml)")
        env.pop("DBT_PROFILES_DIR", None)     # the project's own profiles.yml
    env.update({
        "DBT_PROJECT_DIR": proj,
        "DBT_PATH": DBT_SHIM,
        "DBT_MCP_ENABLE_TOOLS": ",".join(READ_ONLY_TOOLS),
        "DO_NOT_TRACK": "1",
        "DBT_SEND_ANONYMOUS_USAGE_STATS": "false",
        "MCP_TRANSPORT": "stdio",
        "DBT_CLI_TIMEOUT": env.get("DBT_CLI_TIMEOUT", "120"),
    })
    for k in OFF:
        env[k] = "true"
    for k in ("DBT_HOST", "DBT_TOKEN", "DBT_PROD_ENV_ID", "DBT_DEV_ENV_ID", "DBT_USER_ID",
              "DBT_ACCOUNT_ID", "MULTICELL_ACCOUNT_PREFIX"):
        env.pop(k, None)
    return env, proj


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    which = "analytics" if argv[:1] == ["analytics"] else "user"
    home = os.path.expanduser("~")
    try:
        env, proj = server_env(which, home)
    except SystemExit as e:
        print(str(e), file=sys.stderr)
        return 1
    exe = os.path.join(VENV_BIN, "dbt-mcp")
    os.chdir(proj)
    os.execve(exe, [exe], env)
    return 0  # pragma: no cover


if __name__ == "__main__":
    sys.exit(main())
