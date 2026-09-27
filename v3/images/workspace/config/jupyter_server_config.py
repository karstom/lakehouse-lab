# Image-wide Jupyter Server config (/etc/jupyter). code-server is launched on demand by
# jupyter-server-proxy at <base_url>/code-server/ and gets a JupyterLab launcher tile.
c = get_config()  # noqa: F821

c.ServerProxy.servers = {
    "code-server": {
        "command": [
            "code-server",
            "--auth=none",               # JupyterHub/Jupyter auth already fronts the proxy
            "--bind-addr=127.0.0.1:{port}",
            "--disable-telemetry",
            "--disable-update-check",
            "--disable-workspace-trust",
            "/home/jovyan",
        ],
        "timeout": 60,
        "absolute_url": False,
        "launcher_entry": {"title": "VS Code", "enabled": True},
        "new_browser_tab": True,
    }
}
c.ServerApp.root_dir = "/home/jovyan"


# ---------------------------------------------------------------------------- Jupyter AI
# (CONTRACT Phase 5; lakehouse/ai.py.) The default persona is the lab's "Lab Assistant"
# (lakehouse/ai_persona.py): the lab's AI gateway with the user's own key (LAB_AI_*, minted by
# JupyterHub at spawn), the lab's system prompt and tutor mode, and the lab's MCP servers.
# Jupyter AI's stock Jupyternaut stays available and also defaults to the gateway. Nothing
# here ever calls a model; with no usable gateway the assistant says "AI isn't configured".
def _jupyter_ai(c):
    from lakehouse import ai

    c.PersonaManager.default_persona_id = ai.PERSONA_ID
    # Setting builtin_mcp_servers replaces Jupyter AI's default list, so keep its own
    # in-server MCP server (jupyter_server_mcp, localhost only) first, then the lab's
    # servers (stdio, started as the user, with the user's hub token in memory only).
    port = 3001
    try:
        port = int(c.MCPExtensionApp.mcp_port)
    except (AttributeError, TypeError, ValueError):
        pass
    c.PersonaManager.builtin_mcp_servers = (
        [{"type": "http", "name": "Jupyter MCP Server", "url": f"http://localhost:{port}/mcp",
          "headers": []}]
        + ai.jupyter_ai_mcp_servers())
    gw = ai.gateway()
    if gw["ok"]:
        model = f"openai/{gw['model']}"
        c.JupyternautExtension.initial_language_model = model
        # The key comes from OPENAI_API_KEY (set below); only the gateway URL is stored.
        c.JupyternautExtension.model_parameters = {model: {"api_base": gw["base_url"]}}


try:
    _jupyter_ai(c)
except Exception as _e:  # noqa: BLE001 - AI config must never stop the server from starting
    import sys
    print(f"jupyter_server_config: Jupyter AI not configured: {_e}", file=sys.stderr)
