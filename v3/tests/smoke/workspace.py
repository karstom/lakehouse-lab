"""Smoke checks 8-10 driver: a user's JupyterHub workspace, driven like a person would.

A headless Chromium logs the user into `jupyter.` through Keycloak, which spawns the user's
workspace (/hub/spawn). Code then runs INSIDE the workspace through the Jupyter server's own
REST API and kernel websocket, called from the user's JupyterLab page with the user's session
cookies (the hub has no exec API, and nothing here needs the Docker socket). The code is
kernel_probe.py plus one call; its JSON result comes back on stdout after MARKER.

The only interface assumptions about the hub are JupyterHub defaults: base URL "/",
GenericOAuthenticator's /hub/oauth_login, /hub/spawn, /user/<name>/, and the REST API
/hub/api/users/<name>/server for stopping the server again.
"""
import json
import os
import time
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
PROBE_FILE = os.path.join(HERE, "kernel_probe.py")
MARKER = "SMOKE_PROBE_RESULT "

# Runs in the JupyterLab page: create a kernel, execute `code`, collect stdout/stderr and the
# reply, delete the kernel. Uses the page's own cookies; POST/DELETE carry the _xsrf token
# like JupyterLab does. Legacy JSON websocket protocol (no subprotocol negotiated).
KERNEL_EXEC_JS = r"""
async ({base, code, timeoutMs}) => {
  const uuid = () => (window.crypto && crypto.randomUUID) ? crypto.randomUUID()
    : Array.from({length: 32}, () => Math.floor(Math.random() * 16).toString(16)).join("");
  const m = document.cookie.match(/(?:^|;\s*)_xsrf=([^;]*)/);
  const xsrf = m ? decodeURIComponent(m[1]) : "";
  const hdr = {"Content-Type": "application/json"};
  if (xsrf) hdr["X-XSRFToken"] = xsrf;
  const t0 = Date.now();
  const r = await fetch(base + "api/kernels", {method: "POST", headers: hdr,
    credentials: "same-origin", body: JSON.stringify({name: "python3"})});
  if (!r.ok) return {error: "create kernel: HTTP " + r.status + " " + (await r.text()).slice(0, 300)};
  const kernel = await r.json();
  const session = uuid();
  const msgId = uuid();
  const q = "session_id=" + session + (xsrf ? "&_xsrf=" + encodeURIComponent(xsrf) : "");
  const wsUrl = location.origin.replace(/^http/, "ws") + base + "api/kernels/" + kernel.id + "/channels?" + q;
  const res = await new Promise((resolve) => {
    let stdout = "", stderr = "", status = null, idle = false, done = false;
    const finish = (extra) => {
      if (done) return; done = true; clearTimeout(timer);
      try { ws.close(); } catch (e) {}
      resolve(Object.assign({stdout, stderr, status}, extra || {}));
    };
    const timer = setTimeout(() => finish({timeout: true}), timeoutMs);
    const ws = new WebSocket(wsUrl);
    ws.onerror = () => finish({error: "websocket error (" + wsUrl.split("?")[0] + ")"});
    ws.onclose = (ev) => finish({error: "websocket closed, code " + ev.code});
    ws.onopen = () => ws.send(JSON.stringify({
      header: {msg_id: msgId, username: "", session, msg_type: "execute_request",
               version: "5.3", date: new Date().toISOString()},
      parent_header: {}, metadata: {}, channel: "shell", buffers: [],
      content: {code, silent: false, store_history: false, user_expressions: {},
                allow_stdin: false, stop_on_error: true}}));
    ws.onmessage = (ev) => {
      if (typeof ev.data !== "string") return;
      let msg; try { msg = JSON.parse(ev.data); } catch (e) { return; }
      if (!msg.parent_header || msg.parent_header.msg_id !== msgId) return;
      const t = (msg.header && msg.header.msg_type) || msg.msg_type;
      const c = msg.content || {};
      if (t === "stream") { if (c.name === "stdout") stdout += c.text; else stderr += c.text; }
      else if (t === "error") { stderr += c.ename + ": " + c.evalue + "\n"; }
      else if (t === "execute_reply") { status = c.status; }
      else if (t === "status" && c.execution_state === "idle") { idle = true; }
      if (status !== null && idle) finish();
    };
  });
  res.kernel_seconds = Math.round((Date.now() - t0) / 100) / 10;
  try { await fetch(base + "api/kernels/" + kernel.id, {method: "DELETE", headers: hdr,
                    credentials: "same-origin"}); } catch (e) {}
  return res;
}
"""

# Runs on a hub page: stop the user's default server through the hub REST API with the
# page's session (xsrf header as the hub UI sends it), then wait until it is gone.
STOP_SERVER_JS = r"""
async ({user, timeoutMs}) => {
  const m = document.cookie.match(/(?:^|;\s*)_xsrf=([^;]*)/);
  const hdr = m ? {"X-XSRFToken": decodeURIComponent(m[1])} : {};
  const api = "/hub/api/users/" + encodeURIComponent(user);
  const r = await fetch(api + "/server", {method: "DELETE", headers: hdr, credentials: "same-origin"});
  const out = {delete_status: r.status};
  const t0 = Date.now();
  while (Date.now() - t0 < timeoutMs) {
    const g = await fetch(api, {headers: hdr, credentials: "same-origin"});
    if (!g.ok) { out.poll_status = g.status; break; }
    const u = await g.json();
    const s = (u.servers || {})[""];
    if (!s || (!s.ready && !s.pending)) { out.stopped = true; break; }
    await new Promise((res) => setTimeout(res, 2000));
  }
  out.seconds = Math.round((Date.now() - t0) / 100) / 10;
  return out;
}
"""


def probe_code(params):
    """kernel_probe.py + the call that prints its result. Parameters travel as a JSON string
    literal (json.dumps twice), so no value is ever spliced into code unescaped."""
    with open(PROBE_FILE, encoding="utf-8") as f:
        src = f.read()
    call = (f"\nprint(MARKER + json.dumps(probe(json.loads({json.dumps(json.dumps(params))}), "
            f"globals()), default=str), flush=True)\n")
    return src + call


def parse_probe_output(stdout):
    for line in reversed((stdout or "").splitlines()):
        if line.startswith(MARKER):
            return json.loads(line[len(MARKER):])
    return None


class Workspace:
    """One user's browser session against the hub (a fresh browser context)."""

    def __init__(self, browser, url, domain, username, password):
        self.url = url            # url(svc, path) from smoke.py
        self.domain = domain
        self.user = username
        self.password = password
        self.ctx = browser.new_context()
        self.page = self.ctx.new_page()
        self.base = f"/user/{urllib.parse.quote(username)}/"

    def close(self):
        try:
            self.ctx.close()
        except Exception:  # noqa: BLE001
            pass

    def login_and_spawn(self, timeout=300):
        """Keycloak login via the hub, then wait for JupyterLab at /user/<name>/."""
        page = self.page
        t0 = time.time()
        page.goto(self.url("jupyter", "/hub/oauth_login?next=%2Fhub%2Fspawn"),
                  wait_until="domcontentloaded")
        prompts = 0
        seen = []
        hub_error = None
        statuses = {}
        page.on("response", lambda r: statuses.__setitem__(r.url, r.status)
                if r.request.is_navigation_request() else None)
        deadline = t0 + timeout
        while time.time() < deadline:
            cur = urllib.parse.urlparse(page.url)
            if not seen or seen[-1] != f"{cur.hostname}{cur.path}":
                seen.append(f"{cur.hostname}{cur.path}")
            if cur.hostname == f"auth.{self.domain}" and page.locator("#username").count() > 0:
                prompts += 1
                if prompts > 1:
                    raise RuntimeError("Keycloak asked for the password twice (login rejected?)")
                page.fill("#username", self.user)
                page.fill("#password", self.password)
                page.click("#kc-login")
                page.wait_for_load_state("domcontentloaded")
                continue
            if cur.hostname == f"jupyter.{self.domain}" and cur.path.startswith(self.base):
                # JupyterLab's shell is up once its main area exists.
                try:
                    page.wait_for_selector("#jp-main-dock-panel, #main-panel, .jp-LabShell",
                                           timeout=60000)
                except Exception:  # noqa: BLE001 - evidence records what was reached
                    pass
                break
            if cur.hostname == f"jupyter.{self.domain}" and cur.path.rstrip("/") == "/hub/home":
                page.goto(self.url("jupyter", "/hub/spawn"), wait_until="domcontentloaded")
                continue
            if cur.hostname == f"jupyter.{self.domain}" and statuses.get(page.url, 200) >= 500:
                # The hub answered with an error page (e.g. the spawner failed): stop waiting.
                try:
                    text = " ".join(page.locator("body").inner_text(timeout=5000).split())
                except Exception:  # noqa: BLE001
                    text = ""
                hub_error = f"HTTP {statuses[page.url]} at {cur.path}: {text[:300]}"
                break
            page.wait_for_timeout(1000)
        final = urllib.parse.urlparse(page.url)
        ok = final.hostname == f"jupyter.{self.domain}" and final.path.startswith(self.base)
        try:
            page.screenshot(path=f"/out/jupyter-{self.user}.png")
        except Exception:  # noqa: BLE001 - evidence only
            pass
        res = {"ok": ok, "final_url": page.url, "keycloak_password_prompts": prompts,
               "seconds": round(time.time() - t0, 1), "path": seen[-8:]}
        if hub_error:
            res["hub_error"] = hub_error
        return res

    def run(self, code, timeout=900):
        return self.page.evaluate(KERNEL_EXEC_JS, {"base": self.base, "code": code,
                                                   "timeoutMs": int(timeout * 1000)})

    def run_probe(self, params, timeout=900):
        # The probe dumps all thread stacks shortly before our timeout (kernel_probe.STACK_DUMP).
        params = dict(params, dump_after_s=max(30, timeout - 45))
        raw = self.run(probe_code(params), timeout)
        result = parse_probe_output(raw.get("stdout"))
        if raw.get("timeout"):
            raw["stack_dump"] = self.read_file(".smoke-stack.txt")[-4000:]
        return result, raw

    def read_file(self, path):
        """A text file from the user's home, through the Jupyter contents API."""
        try:
            return self.page.evaluate("""async ({base, path}) => {
              const r = await fetch(base + "api/contents/" + path + "?content=1&type=file&format=text",
                                    {credentials: "same-origin"});
              return r.ok ? ((await r.json()).content || "") : ("HTTP " + r.status);
            }""", {"base": self.base, "path": path}) or ""
        except Exception as e:  # noqa: BLE001 - diagnostics only
            return f"{type(e).__name__}: {e}"[:300]

    def stop_server(self, timeout=90):
        try:
            self.page.goto(self.url("jupyter", "/hub/home"), wait_until="domcontentloaded")
            return self.page.evaluate(STOP_SERVER_JS, {"user": self.user,
                                                       "timeoutMs": int(timeout * 1000)})
        except Exception as e:  # noqa: BLE001 - cleanup is best effort, and reported
            return {"error": f"{type(e).__name__}: {e}"[:300]}
