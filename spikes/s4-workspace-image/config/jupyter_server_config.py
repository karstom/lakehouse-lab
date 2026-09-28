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
