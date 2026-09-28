"""Migration test, load step (run.sh load): in the smoke container, log a lab admin into
JupyterHub in a headless browser (tests/smoke/workspace.py), then run load_kernel.py (the
guide's notebook cells) in that user's own workspace kernel, and check what the guide's
notebook-copy step put in the user's home.

Env: LAB_DOMAIN, LAB_AUTH_URL, LAB_TEST_USER_PASSWORD (compose), MIG_PARAMS (JSON file with
the landing-reader key, the expected sums and the profile; never printed), MIG_USER (alice),
MIG_LOGIN_ONLY=1 (only log in and spawn: creates the user's home volume).
Writes /out/load-result.json; exit 0 only if every step passed.
"""
import json
import os
import socket
import sys

sys.path.insert(0, "/opt/smoke")
from workspace import Workspace  # noqa: E402  (tests/smoke/workspace.py)

D = os.environ["LAB_DOMAIN"]
PORT_SUFFIX = os.environ["LAB_AUTH_URL"].removeprefix(f"https://auth.{D}")
USER = os.environ.get("MIG_USER", "alice")
MARKER = "MIGRATION_RESULT "

# Kernel code for the notebook-copy check: what arrived in ~/migrated-from-v2, and whether the
# user owns it (can edit and delete it).
HOME_CHECK = r"""
import json, os
root = os.path.expanduser("~/migrated-from-v2")
files = sorted(os.path.relpath(os.path.join(d, f), root) for d, _, fs in os.walk(root) for f in fs)
not_mine = [p for p in files if os.stat(os.path.join(root, p)).st_uid != os.getuid()]
writable = os.access(root, os.W_OK) and all(os.access(os.path.join(root, p), os.W_OK) for p in files)
print("MIGRATION_RESULT " + json.dumps({"files": files, "not_owned": not_mine, "writable": writable}))
"""


def url(svc, path=""):
    return f"https://{svc}.{D}{PORT_SUFFIX}{path}"


def parse(raw):
    for line in reversed((raw.get("stdout") or "").splitlines()):
        if line.startswith(MARKER):
            return json.loads(line[len(MARKER):])
    return None


def main():
    from playwright.sync_api import sync_playwright

    login_only = os.environ.get("MIG_LOGIN_ONLY") == "1"
    params, code = {}, ""
    if not login_only:
        with open(os.environ["MIG_PARAMS"], encoding="utf-8") as f:
            params = json.load(f)
        with open("/opt/migration/load_kernel.py", encoding="utf-8") as f:
            code = f"PARAMS_JSON = {json.dumps(json.dumps(params))}\n" + f.read()
    out = {"user": USER}
    ok = False
    with sync_playwright() as pw:
        caddy_ip = socket.gethostbyname(f"jupyter.{D}")
        browser = pw.chromium.launch(args=[f"--host-resolver-rules=MAP *.{D} {caddy_ip}"])
        ws = Workspace(browser, url, D, USER, os.environ["LAB_TEST_USER_PASSWORD"])
        try:
            out["login"] = ws.login_and_spawn()
            print("login:", json.dumps(out["login"]), flush=True)
            if login_only:
                print("LOGIN:", "PASS" if out["login"]["ok"] else "FAIL")
                return 0 if out["login"]["ok"] else 1
            if out["login"]["ok"]:
                raw = ws.run(code, timeout=1800)
                out["load"] = parse(raw)
                out["load_stdout_tail"] = (raw.get("stdout") or "")[-2500:]
                if out["load"] is None:
                    out["load_raw"] = {k: raw.get(k) for k in ("error", "timeout", "status")}
                    out["load_stderr_tail"] = (raw.get("stderr") or "")[-2500:]
                if params.get("check_home"):
                    out["home"] = parse(ws.run(HOME_CHECK, timeout=120))
                steps = (out["load"] or {}).get("steps", {})
                ok = bool(steps) and all(v.get("ok") for v in steps.values())
                if params.get("check_home"):
                    h = out["home"] or {}
                    ok = ok and bool(h.get("files")) and not h.get("not_owned") and h.get("writable")
        finally:
            ws.close()
            browser.close()
    out["ok"] = ok
    with open("/out/load-result.json", "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1, default=str)
    print(json.dumps(out, indent=1, default=str))
    print("LOAD:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
