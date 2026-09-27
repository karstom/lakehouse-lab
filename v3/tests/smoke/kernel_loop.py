"""Workspace-kernel loop: the reproduction harness for the intermittent kernel failures
(CONTRACT Phase 4, "Required: root-cause the intermittent workspace-kernel failures").

Runs in the `smoke` container (tests/smoke/kernel-loop.sh starts it; never part of `lab test`).
One iteration, per user, is exactly what smoke checks 8-10 do, through the same code
(workspace.Workspace):

    fresh browser context -> Keycloak login -> spawn -> kernel -> Trino (+ Spark) step -> stop

Every iteration appends one JSON line to <out>/iterations.jsonl with UTC start/end times (so
kernel-loop.sh can slice the JupyterHub, single-user and Docker-proxy logs for that window),
an outcome class, and on failure the evidence the contract asks for: every HTTP response
>= 400 seen by the page (method, path, status, body head), the cookie jar's shape (names,
paths, expiry, value length; never values), the kernel's stderr and the probe's thread dump.

Usage (in the container):  python3 kernel_loop.py --iterations 30 --users alice,eddie,anna,victor
"""
import argparse
import datetime
import json
import os
import sys
import time
import traceback
import urllib.parse

import smoke as S
from workspace import Workspace

# Per-user probe steps: a Trino step, plus a Spark step on Spark profiles. Writers create and
# read an Iceberg table through Spark; readers get Lakekeeper's refusal (the path of
# WATCH_V3_SPARK_CONNECT_INTERMITTENT_HANG).
WRITERS = {"alice", "eddie"}


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="milliseconds")


def steps_for(user, spark):
    if user in WRITERS:
        return ["trino_samples"] + (["spark_iceberg"] if spark else [])
    return ["trino_write_denied"] + (["spark_write_denied"] if spark else [])


def cookie_shape(ctx):
    out = []
    for c in ctx.cookies():
        out.append({"name": c["name"], "domain": c.get("domain"), "path": c.get("path"),
                    "expires": round(c.get("expires", -1)), "len": len(c.get("value", "")),
                    "httpOnly": c.get("httpOnly")})
    return sorted(out, key=lambda c: (c["name"], c["path"] or ""))


def classify(login, result, raw, stop, steps):
    """-> outcome class. 'ok' only if every step passed and the server stopped."""
    if login is None or not login.get("ok"):
        if login and login.get("hub_error"):
            return "spawn_error"
        return "login_or_spawn_failed"
    if raw is None:
        return "kernel_not_run"
    err = raw.get("error") or ""
    if err.startswith("create kernel: HTTP"):
        return "kernel_create_http_" + err.split("HTTP", 1)[1].split()[0]
    if err.startswith("websocket"):
        return "kernel_websocket_error"
    if raw.get("timeout"):
        return "kernel_timeout"
    if result is None:
        return "kernel_no_result"
    bad = [n for n in steps if not result["steps"].get(n, {}).get("ok")]
    if bad:
        return "step_failed:" + ",".join(bad)
    if not (stop or {}).get("stopped"):
        return "stop_failed"
    return "ok"


def iteration(browser, user, i, spark, probe_timeout):
    ws = Workspace(browser, S.url, S.D, user, S.PW)
    bad_responses = []

    def on_response(r):
        try:
            if r.status >= 400 and urllib.parse.urlparse(r.url).hostname == f"jupyter.{S.D}":
                body = ""
                if r.status in (400, 401, 403, 404, 500, 503):
                    try:
                        body = " ".join(r.text().split())[:300]
                    except Exception as e:  # noqa: BLE001
                        body = f"<{type(e).__name__}>"
                bad_responses.append({"t": now(), "method": r.request.method,
                                      "path": urllib.parse.urlparse(r.url).path,
                                      "status": r.status, "body": body})
        except Exception:  # noqa: BLE001 - evidence only
            pass

    ws.page.on("response", on_response)
    rec = {"iter": i, "user": user, "start": now()}
    login = result = raw = stop = None
    steps = steps_for(user, spark)
    t0 = time.time()
    try:
        login = ws.login_and_spawn()
        rec["login"] = login
        rec["cookies_after_login"] = cookie_shape(ws.ctx)
        if login.get("ok"):
            params = S.probe_params(user, steps)
            params["spark_table"] = f"loop_probe_{user}"
            params["write_probe_table"] = "lakehouse.smoke.events"
            result, raw = ws.run_probe(params, timeout=probe_timeout)
            rec["kernel"] = {k: raw.get(k) for k in ("status", "error", "timeout", "kernel_seconds",
                                                     "kernel_state", "trace")}
            rec["steps"] = {n: {k: v for k, v in (result or {}).get("steps", {}).get(n, {}).items()
                                if k in ("ok", "error", "seconds", "current_user", "created")}
                            for n in steps}
    except Exception as e:  # noqa: BLE001
        rec["exception"] = f"{type(e).__name__}: {e}"[:500]
        rec["trace"] = traceback.format_exc()[-1500:]
    finally:
        stop = ws.stop_server()
        rec["stop"] = stop
    rec["outcome"] = classify(login, result, raw, stop, steps) if "exception" not in rec \
        else "harness_exception"
    rec["seconds"] = round(time.time() - t0, 1)
    rec["end"] = now()
    if rec["outcome"] != "ok":
        rec["bad_responses"] = bad_responses[-30:]
        rec["cookies_at_end"] = cookie_shape(ws.ctx)
        if raw:
            rec["kernel_stderr"] = (raw.get("stderr") or "")[-1500:]
            rec["stack_dump"] = raw.get("stack_dump")
            rec["probe_progress"] = raw.get("probe_progress")
        if result:
            rec["steps_full"] = result.get("steps")
        try:
            ws.page.screenshot(path=f"{OUT}/fail-{i:03d}-{user}.png")
        except Exception:  # noqa: BLE001
            pass
    else:
        rec["bad_responses"] = bad_responses[-10:]   # 4xx seen even on success (context)
    ws.close()
    return rec


def ensure_probe_table():
    """lakehouse.smoke.events for the readers' denied write (smoke check 3 creates it too)."""
    cur = S.trino_conn(S.user_token("alice")).cursor()
    S.run(cur, f"CREATE SCHEMA IF NOT EXISTS lakehouse.{S.SCHEMA}")
    S.run(cur, f"CREATE TABLE IF NOT EXISTS lakehouse.{S.SCHEMA}.{S.TABLE} "
               "(id bigint, kind varchar, amount double)")


OUT = "/out/kernel-loop"

# --race: the kernel websocket alone, many times in ONE logged-in workspace (no spawn per try).
# Creates a kernel, opens its websocket and sends execute_request either at once on `open`
# (what KERNEL_EXEC_JS did) or only after a kernel_info_request/reply handshake on that
# websocket (what JupyterLab does), then records every message it saw until the reply and
# idle status arrive or `timeoutMs` passes.
RACE_JS = r"""
async ({base, handshake, timeoutMs}) => {
  const uuid = () => crypto.randomUUID();
  const m = document.cookie.match(/(?:^|;\s*)_xsrf=([^;]*)/);
  const xsrf = m ? decodeURIComponent(m[1]) : "";
  const hdr = {"Content-Type": "application/json", "X-XSRFToken": xsrf};
  const t0 = Date.now();
  const r = await fetch(base + "api/kernels", {method: "POST", headers: hdr, body: JSON.stringify({name: "python3"})});
  if (!r.ok) return {error: "create kernel: HTTP " + r.status};
  const kernel = await r.json();
  const session = uuid();
  const wsUrl = location.origin.replace(/^http/, "ws") + base + "api/kernels/" + kernel.id +
    "/channels?session_id=" + session + "&_xsrf=" + encodeURIComponent(xsrf);
  const mk = (type, channel, content) => ({header: {msg_id: uuid(), username: "", session,
    msg_type: type, version: "5.3", date: new Date().toISOString()}, parent_header: {},
    metadata: {}, channel, buffers: [], content});
  const res = await new Promise((resolve) => {
    const seen = []; let execId = null, infoId = null, status = null, idle = false, out = "";
    let done = false, tOpen = null, tSent = null;
    const finish = (extra) => { if (done) return; done = true; clearTimeout(timer);
      try { ws.close(); } catch (e) {}
      resolve(Object.assign({status, idle, out, seen: seen.slice(0, 40), t_open: tOpen, t_sent: tSent}, extra || {})); };
    const timer = setTimeout(() => finish({timeout: true}), timeoutMs);
    const ws = new WebSocket(wsUrl);
    const sendExec = () => { const e = mk("execute_request", "shell", {code: "print('race-ok')",
      silent: false, store_history: false, user_expressions: {}, allow_stdin: false, stop_on_error: true});
      execId = e.header.msg_id; tSent = Date.now() - t0; ws.send(JSON.stringify(e)); };
    ws.onopen = () => { tOpen = Date.now() - t0;
      if (handshake) { const k = mk("kernel_info_request", "shell", {}); infoId = k.header.msg_id; ws.send(JSON.stringify(k)); }
      else sendExec(); };
    ws.onerror = () => finish({error: "websocket error"});
    ws.onclose = (ev) => finish({error: "websocket closed " + ev.code});
    ws.onmessage = (ev) => {
      let msg; try { msg = JSON.parse(ev.data); } catch (e) { return; }
      const t = msg.header && msg.header.msg_type; const p = msg.parent_header && msg.parent_header.msg_id;
      const c = msg.content || {};
      seen.push([Date.now() - t0, msg.channel, t, p === execId ? "exec" : (p === infoId ? "info" : (p ? "other" : "-")),
                 t === "status" ? c.execution_state : ""]);
      if (handshake && p === infoId && t === "kernel_info_reply" && execId === null) sendExec();
      if (p !== execId || execId === null) return;
      if (t === "stream") out += c.text;
      else if (t === "execute_reply") status = c.status;
      else if (t === "status" && c.execution_state === "idle") idle = true;
      if (status !== null && idle) finish();
    };
  });
  res.kernel_state = null;
  try { const k = await (await fetch(base + "api/kernels/" + kernel.id, {headers: hdr})).json();
        res.kernel_state = k.execution_state; } catch (e) {}
  await fetch(base + "api/kernels/" + kernel.id, {method: "DELETE", headers: hdr});
  res.ms = Date.now() - t0;
  return res;
}
"""


def race(browser, user, n, handshake, timeout_s, label):
    ws = Workspace(browser, S.url, S.D, user, S.PW)
    login = ws.login_and_spawn()
    counts = {"ok": 0, "lost": 0, "error": 0}
    path = os.path.join(OUT, "race.jsonl")
    try:
        if not login.get("ok"):
            raise RuntimeError(f"spawn failed: {login}")
        for i in range(1, n + 1):
            r = ws.page.evaluate(RACE_JS, {"base": ws.base, "handshake": handshake,
                                           "timeoutMs": int(timeout_s * 1000)})
            if r.get("error"):
                outcome = "error"
            elif r.get("timeout"):
                outcome = "lost"
            else:
                outcome = "ok" if "race-ok" in (r.get("out") or "") else "error"
            counts[outcome] += 1
            rec = {"t": now(), "label": label, "user": user, "i": i, "handshake": handshake,
                   "outcome": outcome, **r}
            if outcome == "ok":
                rec.pop("seen", None)
            with open(path, "a") as f:
                f.write(json.dumps(rec) + "\n")
            print(f"[race] {rec['t']} {'handshake' if handshake else 'immediate'} {i:4d} {outcome:5s} "
                  f"{r.get('ms')}ms kernel={r.get('kernel_state')}", flush=True)
    finally:
        ws.stop_server()
        ws.close()
    return counts


def stress(browser, user, n, spark, probe_timeout, label):
    """N probe runs (each a new kernel) in ONE logged-in workspace: separates failures of the
    probe's own code (Trino/Spark clients) from login/spawn/websocket effects."""
    ws = Workspace(browser, S.url, S.D, user, S.PW)
    login = ws.login_and_spawn()
    counts = {}
    path = os.path.join(OUT, "stress.jsonl")
    steps = steps_for(user, spark)
    try:
        if not login.get("ok"):
            raise RuntimeError(f"spawn failed: {login}")
        for i in range(1, n + 1):
            t0 = time.time()
            params = S.probe_params(user, steps)
            params["spark_table"] = f"loop_probe_{user}"
            params["write_probe_table"] = "lakehouse.smoke.events"
            rec = {"t": now(), "label": label, "user": user, "i": i}
            result, raw = ws.run_probe(params, timeout=probe_timeout)
            outcome = classify(login, result, raw, {"stopped": True}, steps)
            rec.update(outcome=outcome, seconds=round(time.time() - t0, 1),
                       kernel={k: raw.get(k) for k in ("status", "error", "timeout",
                                                        "kernel_seconds", "kernel_state", "trace")},
                       steps={n_: {k: v for k, v in (result or {}).get("steps", {}).get(n_, {}).items()
                                   if k in ("ok", "error", "seconds")} for n_ in steps})
            if outcome != "ok":
                rec.update(stack_dump=raw.get("stack_dump"), probe_progress=raw.get("probe_progress"),
                           kernel_stderr=(raw.get("stderr") or "")[-1500:])
            counts[outcome] = counts.get(outcome, 0) + 1
            with open(path, "a") as f:
                f.write(json.dumps(rec, default=str) + "\n")
            print(f"[stress] {rec['t']} {user:7s} {i:4d} {outcome:28s} {rec['seconds']:6.1f}s", flush=True)
    finally:
        ws.stop_server()
        ws.close()
    return counts


def main():
    global OUT
    ap = argparse.ArgumentParser()
    ap.add_argument("--iterations", type=int, default=30)
    ap.add_argument("--users", default="alice,eddie,anna,victor")
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--probe-timeout", type=int, default=300)
    ap.add_argument("--label", default="")
    ap.add_argument("--race", type=int, default=0,
                    help="instead of the loop: N kernel-websocket tries per mode in one workspace")
    ap.add_argument("--race-modes", default="immediate,handshake")
    ap.add_argument("--race-timeout", type=float, default=20.0)
    ap.add_argument("--stress", type=int, default=0,
                    help="instead of the loop: N probe runs per user in ONE workspace each")
    a = ap.parse_args()
    OUT = a.out
    os.makedirs(OUT, exist_ok=True)
    users = [u.strip() for u in a.users.split(",") if u.strip()]
    spark = S.PROFILE in S.SPARK_PROFILES
    if a.race:
        from playwright.sync_api import sync_playwright
        out = {}
        with sync_playwright() as pw:
            browser = S._workspace_browser(pw)
            try:
                for mode in a.race_modes.split(","):
                    for user in users:
                        out[f"{mode}:{user}"] = race(browser, user, a.race, mode == "handshake",
                                                     a.race_timeout, a.label)
            finally:
                browser.close()
        print("[race] SUMMARY " + json.dumps(out), flush=True)
        with open(os.path.join(OUT, "race-summary.json"), "w") as f:
            json.dump({"label": a.label, "counts": out}, f, indent=1)
        return 0
    ensure_probe_table()
    from playwright.sync_api import sync_playwright
    if a.stress:
        out = {}
        with sync_playwright() as pw:
            browser = S._workspace_browser(pw)
            try:
                for user in users:
                    out[user] = stress(browser, user, a.stress, spark, a.probe_timeout, a.label)
            finally:
                browser.close()
        print("[stress] SUMMARY " + json.dumps(out), flush=True)
        with open(os.path.join(OUT, "stress-summary.json"), "w") as f:
            json.dump({"label": a.label, "counts": out}, f, indent=1)
        return 0 if all(set(c) <= {"ok"} for c in out.values()) else 1
    counts = {}
    path = os.path.join(OUT, "iterations.jsonl")
    with sync_playwright() as pw:
        browser = S._workspace_browser(pw)
        try:
            for i in range(1, a.iterations + 1):
                for user in users:
                    rec = iteration(browser, user, i, spark, a.probe_timeout)
                    rec["label"] = a.label
                    with open(path, "a") as f:
                        f.write(json.dumps(rec, default=str) + "\n")
                    counts.setdefault(user, {}).setdefault(rec["outcome"], 0)
                    counts[user][rec["outcome"]] += 1
                    print(f"[loop] {rec['end']} iter {i:3d} {user:7s} {rec['outcome']:28s} "
                          f"{rec['seconds']:6.1f}s spawn={rec.get('login', {}).get('seconds')}",
                          flush=True)
        finally:
            browser.close()
    summary = {"label": a.label, "profile": S.PROFILE, "iterations": a.iterations,
               "users": users, "counts": counts,
               "failures": sum(n for c in counts.values() for k, n in c.items() if k != "ok")}
    with open(os.path.join(OUT, "summary.json"), "w") as f:
        json.dump(summary, f, indent=1)
    print("[loop] SUMMARY " + json.dumps(summary), flush=True)
    return 0 if summary["failures"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
