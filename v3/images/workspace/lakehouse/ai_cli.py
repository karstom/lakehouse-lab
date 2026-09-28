"""`lab-ai`: AI assist in your workspace (CONTRACT Phase 5).

    lab-ai status                  is AI set up for you, your budget, tutor mode, MCP servers
    lab-ai tutor [on|off]          show, or turn on/off, tutor mode (hints, not answers, in
                                   the learning tracks; on by default)
    lab-ai prompt [--module ID]    print the assistant's system prompt for this folder (or a
                                   module): what tutor mode tells the model
    lab-ai install-claude-code     install Claude Code (proprietary, by Anthropic) into
                                   ~/.local, pinned, pointed at the lab's AI gateway

Where AI goes: the chat in JupyterLab (Jupyter AI, persona "Lab Assistant") and Claude Code
(if you install it) call ONLY the lab's AI gateway, with your own key; JupyterHub gives your
server a new key every time it starts. The gateway decides which model answers (a local one
unless your lab admin enabled a hosted provider) and enforces your budget.

The assistant acts as you: its tools (MCP servers) use your own login, so it can see only
what you can. Treat what tools return (table data, files, notebook outputs) as data: the
assistant is told to ignore instructions hidden in them, but check what it proposes.
"""
import argparse
import hashlib
import json
import os
import platform
import sys
import tempfile
import time
import urllib.error
import urllib.request

from . import ai

IMAGE_AI_SETTINGS = "/opt/lakehouse/etc/ai.json"     # pins baked in by the Dockerfile
CLAUDE_DOWNLOAD_BASE = "https://downloads.claude.ai/claude-code-releases"


def _pins(path=None):
    try:
        with open(path or os.environ.get("LAB_AI_IMAGE_SETTINGS", IMAGE_AI_SETTINGS),
                  encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


# ---------------------------------------------------------------------------- gateway calls
def _gateway_get(gw, path, timeout=5):
    """GET on the gateway with the user's own key (metadata only: never a model call)."""
    req = urllib.request.Request(gw["url"] + path,
                                 headers={"Authorization": f"Bearer {gw['key']}"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


# The one budget route the AI front door allows (bootstrap/ai_frontdoor.py ROUTES): LiteLLM's
# lightweight user lookup WITHOUT user_id, i.e. the key's own user (no keys, no teams).
BUDGET_PATH = "/v2/user/info"


def budget(gw):
    """-> {spend, max_budget, budget_reset_at} of the user, best effort ({} on any error)."""
    try:
        data = _gateway_get(gw, BUDGET_PATH)
    except (OSError, ValueError, urllib.error.HTTPError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {k: data[k] for k in ("spend", "max_budget", "budget_reset_at") if data.get(k) is not None}


# ---------------------------------------------------------------------------- status
def claude_installed():
    link = os.path.join(ai.home(), ".local", "bin", "claude")
    marker = os.path.join(_claude_root(), "installed.json")
    try:
        with open(marker, encoding="utf-8") as f:
            info = json.load(f)
    except (OSError, ValueError):
        return None
    return info if os.path.exists(link) else None


def status(check_gateway=True):
    gw = ai.gateway()
    st = {"status": gw["status"], "reason": gw["reason"] or None, "gateway": gw["url"] or None,
          "model": gw["model"] or None, "key": "set" if gw["key"] else "missing",
          "tutor": "on" if ai.tutor_enabled() else "off",
          "mcp_servers": [s["name"] for s in ai.lab_mcp_servers()],
          "claude_code": (claude_installed() or {}).get("version")}
    try:
        m = ai.current_module(os.getcwd())
        st["current_module"] = m.id if m else None
    except Exception:  # noqa: BLE001 - tracks missing: no module
        st["current_module"] = None
    if check_gateway and gw["ok"]:
        # Live, with the user's own key (metadata only): a provider the admin enabled after
        # this server started counts, and so does one they turned off.
        try:
            ids = {m.get("id") for m in _gateway_get(gw, "/v1/models").get("data", [])}
            st["status"] = "ok" if gw["model"] in ids else "not-configured"
            st["reason"] = None if st["status"] == "ok" else "no AI provider is enabled in this lab"
        except (OSError, ValueError, AttributeError):
            st["status"], st["reason"] = "unavailable", "the AI gateway did not answer"
        st["budget"] = budget(gw) or None
    return st


def cmd_status(a):
    st = status(check_gateway=not a.offline)
    if a.json:
        print(json.dumps(st, indent=2, sort_keys=True))
        return 0 if st["status"] == "ok" else 1
    if st["status"] == "ok":
        print(f"AI: ready (model {st['model']} through the lab's AI gateway, your own key)")
    else:
        print(f"AI: {ai.not_configured_message({'status': st['status']})}")
        if st["reason"]:
            print(f"    reason: {st['reason']}")
    b = st.get("budget") or {}
    if b.get("max_budget") is not None:
        line = f"Budget: {float(b.get('spend') or 0):.4f} of {float(b['max_budget']):.2f} used"
        if b.get("budget_reset_at"):
            line += f" (resets {b['budget_reset_at']})"
        print(line)
    elif b.get("spend") is not None:
        print(f"Budget: {float(b['spend']):.4f} used (no limit reported)")
    mod = f" (active module here: {st['current_module']})" if st["current_module"] else ""
    print(f"Tutor mode: {st['tutor']}{mod}  -- `lab-ai tutor off|on` to change")
    print("MCP servers: " + (", ".join(st["mcp_servers"]) or "none configured"))
    print("Claude Code: " + (f"installed ({st['claude_code']}), run `claude`" if st["claude_code"]
                             else "not installed (`lab-ai install-claude-code`)"))
    return 0 if st["status"] == "ok" else 1


def cmd_tutor(a):
    if a.state:
        ai.set_tutor(a.state == "on")
    on = ai.tutor_enabled()
    if on:
        print("Tutor mode is ON: in a learning-track module the assistant explains and gives "
              "hints, but does not hand over solutions. `lab-ai tutor off` turns it off.")
    else:
        print("Tutor mode is OFF: the assistant answers normally, also in the learning tracks. "
              "`lab-ai tutor on` turns it back on.")
    return 0


def cmd_prompt(a):
    module = None
    if a.module:
        t = ai._tracks()
        mods, _ = t.discover()
        module = t.find(mods, a.module)
        if module is None:
            print(f"lab-ai: no module {a.module!r} (see `lab-tracks list`)", file=sys.stderr)
            return 2
    prompt, used = ai.system_prompt(chat_dir=a.dir or os.getcwd(), model=ai.gateway()["model"],
                                    module=module)
    print(prompt)
    print(f"\n[lab-ai: tutor mode {'on for ' + used.id if used else 'not active'}]",
          file=sys.stderr)
    return 0


# ---------------------------------------------------------------------------- Claude Code
def _claude_root():
    return os.path.join(ai.home(), ".local", "share", "lakehouse", "claude-code")


def _platform():
    m = platform.machine().lower()
    arch = {"x86_64": "x64", "amd64": "x64", "aarch64": "arm64", "arm64": "arm64"}.get(m)
    if not arch or platform.system() != "Linux":
        raise SystemExit(f"lab-ai: Claude Code is not available for {platform.system()} {m}")
    return f"linux-{arch}"


def _atomic_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), prefix=".tmp-")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, sort_keys=True)
        f.write("\n")
    os.chmod(tmp, 0o600)
    os.replace(tmp, path)


def _load_json(path):
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except FileNotFoundError:
        return {}
    except ValueError as e:
        raise SystemExit(f"lab-ai: {path} is not valid JSON ({e}); fix or move it, then retry")


WRAPPER = """#!/bin/sh
# Claude Code for Lakehouse Lab (written by `lab-ai install-claude-code`; re-run it to update).
# Runs the pinned binary against the lab's AI gateway with this workspace's own key (LAB_AI_*,
# new at every server start), with auto-update and non-essential traffic off.
if [ -z "${{LAB_AI_KEY:-}}" ] || [ -z "${{LAB_AI_GATEWAY_URL:-}}" ] || [ -z "${{LAB_AI_MODEL:-}}" ]; then
  echo "claude: AI isn't configured; ask your lab admin (see: lab-ai status)." >&2
  exit 1
fi
unset ANTHROPIC_API_KEY
ANTHROPIC_BASE_URL=$LAB_AI_GATEWAY_URL
ANTHROPIC_AUTH_TOKEN=$LAB_AI_KEY
ANTHROPIC_MODEL=${{LAB_AI_CLAUDE_MODEL:-$LAB_AI_MODEL}}
export ANTHROPIC_BASE_URL ANTHROPIC_AUTH_TOKEN ANTHROPIC_MODEL
export ANTHROPIC_DEFAULT_OPUS_MODEL="$ANTHROPIC_MODEL" ANTHROPIC_DEFAULT_SONNET_MODEL="$ANTHROPIC_MODEL"
export ANTHROPIC_DEFAULT_HAIKU_MODEL="$ANTHROPIC_MODEL" ANTHROPIC_SMALL_FAST_MODEL="$ANTHROPIC_MODEL"
export CLAUDE_CODE_SUBAGENT_MODEL="$ANTHROPIC_MODEL"
# The lab's model is not in Claude Code's catalog: tell it the context window (the gateway's
# model setting, when the hub passes it; else a conservative default for local models).
export CLAUDE_CODE_MAX_CONTEXT_TOKENS="${{LAB_AI_CONTEXT_TOKENS:-32768}}"
export DISABLE_AUTOUPDATER=1 CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1 DISABLE_TELEMETRY=1
export DISABLE_ERROR_REPORTING=1 DISABLE_BUG_COMMAND=1
exec "{binary}" "$@"
"""


def _download(url, dest, want_sha256, echo=print):
    """Stream url to dest, checking the sha256 pin. Removes dest on any failure."""
    h = hashlib.sha256()
    t0, done, last = time.time(), 0, -1
    try:
        with urllib.request.urlopen(url, timeout=60) as r, open(dest, "wb") as f:
            total = int(r.headers.get("Content-Length") or 0)
            while True:
                chunk = r.read(1 << 20)
                if not chunk:
                    break
                f.write(chunk)
                h.update(chunk)
                done += len(chunk)
                pct = int(done * 100 / total) if total else -1
                if total and pct // 10 != last // 10:
                    echo(f"  {pct:3d}%  {done / 1e6:.0f} of {total / 1e6:.0f} MB")
                    last = pct
    except (OSError, urllib.error.URLError) as e:
        _rm(dest)
        raise SystemExit(f"lab-ai: download failed: {e}") from None
    got = h.hexdigest()
    if got != want_sha256:
        _rm(dest)
        raise SystemExit(f"lab-ai: checksum mismatch for {url}: expected {want_sha256}, got {got}. "
                         "Nothing was installed.")
    echo(f"  verified sha256 ({done / 1e6:.0f} MB in {time.time() - t0:.0f} s)")


def _rm(path):
    try:
        os.unlink(path)
    except OSError:
        pass


def configure_claude(binary, version, echo=print):
    """Wrapper in ~/.local/bin, lab MCP servers in ~/.claude.json (user scope), quiet settings
    in ~/.claude/settings.json. Keeps everything else the user has there."""
    home = ai.home()
    bindir = os.path.join(home, ".local", "bin")
    os.makedirs(bindir, exist_ok=True)
    wrapper = os.path.join(bindir, "claude")
    tmp = wrapper + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(WRAPPER.format(binary=binary))
    os.chmod(tmp, 0o755)
    os.replace(tmp, wrapper)

    state_path = os.path.join(home, ".claude.json")
    state = _load_json(state_path)
    servers = state.get("mcpServers") if isinstance(state.get("mcpServers"), dict) else {}
    servers.update(ai.claude_mcp_servers())
    state["mcpServers"] = servers
    state.setdefault("hasCompletedOnboarding", True)
    _atomic_json(state_path, state)

    settings_path = os.path.join(home, ".claude", "settings.json")
    settings = _load_json(settings_path)
    env = settings.get("env") if isinstance(settings.get("env"), dict) else {}
    env.update({"DISABLE_AUTOUPDATER": "1", "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
                "DISABLE_TELEMETRY": "1", "DISABLE_ERROR_REPORTING": "1"})
    settings["env"] = env
    _atomic_json(settings_path, settings)
    _atomic_json(os.path.join(_claude_root(), "installed.json"),
                 {"version": version, "binary": binary, "installed_at":
                  time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())})
    echo(f"  ~/.local/bin/claude -> {binary.replace(home, '~', 1)}")
    echo("  MCP servers (user scope, ~/.claude.json): "
         + (", ".join(ai.claude_mcp_servers()) or "none configured"))
    return wrapper


def cmd_install_claude_code(a, echo=print):
    pins = (_pins() or {}).get("claude_code") or {}
    version = pins.get("version")
    plat = _platform()
    sha = (pins.get("sha256") or {}).get(plat)
    if not version or not sha:
        echo("lab-ai: this workspace image has no Claude Code pin; ask your lab admin.")
        return 2
    echo(f"Claude Code {version} ({plat}) is Anthropic's proprietary software, under Anthropic's "
         "terms (https://www.anthropic.com/legal). It is not part of the lab's image; this "
         f"downloads it from {CLAUDE_DOWNLOAD_BASE} into your home folder (~/.local), checks it "
         "against the lab's pinned sha256, and points it at the lab's AI gateway with your own "
         "key. About 230 MB.")
    if not a.yes:
        if not sys.stdin.isatty():
            echo("lab-ai: not a terminal; re-run with --yes to confirm")
            return 2
        if input("Install? [y/N] ").strip().lower() not in ("y", "yes"):
            echo("Nothing installed.")
            return 1
    root = os.path.join(_claude_root(), version)
    os.makedirs(root, exist_ok=True)
    binary = os.path.join(root, "claude")
    have = None
    if os.path.isfile(binary):
        hh = hashlib.sha256()
        with open(binary, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                hh.update(chunk)
        have = hh.hexdigest()
    if have == sha:
        echo(f"Claude Code {version} is already downloaded and verified.")
    else:
        echo(f"Downloading Claude Code {version} ...")
        part = binary + ".part"
        _download(f"{CLAUDE_DOWNLOAD_BASE}/{version}/{plat}/claude", part, sha, echo)
        os.chmod(part, 0o755)
        os.replace(part, binary)
    configure_claude(binary, version, echo)
    gw = ai.gateway()
    echo("Done. Open a new terminal (or run `hash -r`) and start it with `claude`.")
    if not gw["ok"]:
        echo(f"Note: {ai.not_configured_message(gw)} `claude` will refuse to start until then.")
    return 0


# ---------------------------------------------------------------------------- main
def main(argv=None):
    p = argparse.ArgumentParser(prog="lab-ai", description=__doc__.splitlines()[0],
                                epilog="See `lab-ai <command> --help`.")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("status", help="is AI set up for you; budget; tutor mode; MCP servers")
    s.add_argument("--json", action="store_true")
    s.add_argument("--offline", action="store_true", help="do not ask the gateway (budget)")
    s.set_defaults(fn=cmd_status)
    s = sub.add_parser("tutor", help="show, or turn on/off, tutor mode")
    s.add_argument("state", nargs="?", choices=("on", "off"))
    s.set_defaults(fn=cmd_tutor)
    s = sub.add_parser("prompt", help="print the assistant's system prompt here (or for a module)")
    s.add_argument("--module", help="a track module id (E1, A1, ...); default: from the folder")
    s.add_argument("--dir", help="the folder a chat would be in (default: current directory)")
    s.set_defaults(fn=cmd_prompt)
    s = sub.add_parser("install-claude-code",
                       help="install Claude Code (proprietary) into ~/.local, pinned, via the gateway")
    s.add_argument("--yes", action="store_true", help="do not ask for confirmation")
    s.set_defaults(fn=cmd_install_claude_code)
    a = p.parse_args(argv)
    if not os.path.isdir(ai.home()):
        print("lab-ai: your home folder is missing; open the workspace from the hub", file=sys.stderr)
        return 2
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
