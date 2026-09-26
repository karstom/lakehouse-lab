#!/usr/bin/env python3
"""Reproduce REG_V3_WORKSPACE_KERNEL_FIRST_MESSAGE_STALL without a lab.

Against a plain Jupyter Server (the versions of the workspace image), N times:
create a kernel -> open its websocket -> send an execute_request (at once on open, as the
smoke probe does, or after a kernel_info handshake, as JupyterLab does) -> wait for the
execute_reply. A try that gets no reply within --timeout is "lost"; the script then records
the kernel's execution_state and which extra message releases the stalled request:
  * a kernel_info_request on the control channel of the same websocket,
  * a kernel_info_request on the shell channel of a SECOND websocket (a new zmq peer),
  * another shell message on the same websocket.

With ipykernel 7.3.0 about 1 try in 10 is lost; the kernel stays idle, only a new shell peer
releases it (the kernel's shell socket had the message and missed the wakeup). With 6.31.0:
0 lost in 700 tries. Setup (a scratch venv, not the lab):

  python3 -m venv /tmp/jv && /tmp/jv/bin/pip install ipykernel==<v> jupyter_server==<v> \\
      pyzmq==<v> tornado==<v> websocket-client requests      # versions: images/workspace/lock
  /tmp/jv/bin/jupyter server --no-browser --port 18888 --ServerApp.token=racetoken &
  /tmp/jv/bin/python v3/tools/kernel_ws_race.py --n 300 [--handshake]

Prints one JSON line per lost try, and a summary line {"mode", "ok", "lost"}.
"""
import argparse
import json
import time
import uuid

import requests
import websocket


def msg(msg_type, session, content, channel="shell"):
    return {"header": {"msg_id": uuid.uuid4().hex, "username": "", "session": session,
                       "msg_type": msg_type, "version": "5.3", "date": ""},
            "parent_header": {}, "metadata": {}, "channel": channel, "buffers": [],
            "content": content}


def wait_for(ws, pred, timeout):
    end = time.time() + timeout
    seen = []
    while time.time() < end:
        ws.settimeout(max(0.05, end - time.time()))
        try:
            m = json.loads(ws.recv())
        except websocket.WebSocketTimeoutException:
            break
        seen.append((m.get("channel"), m["header"]["msg_type"]))
        if pred(m):
            return True, seen
    return False, seen


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--base", default="http://127.0.0.1:18888/")
    ap.add_argument("--token", default="racetoken")
    ap.add_argument("--n", type=int, default=100)
    ap.add_argument("--handshake", action="store_true", help="kernel_info first, like JupyterLab")
    ap.add_argument("--timeout", type=float, default=10.0)
    a = ap.parse_args()
    hdr = {"Authorization": f"token {a.token}"}
    wsbase = a.base.replace("http", "ws", 1)
    mode = "handshake" if a.handshake else "immediate"
    stats = {"ok": 0, "lost": 0, "handshake_lost": 0}
    for i in range(1, a.n + 1):
        k = requests.post(a.base + "api/kernels", headers=hdr, json={"name": "python3"}, timeout=60).json()
        chan = f"api/kernels/{k['id']}/channels?token={a.token}&session_id="
        session = uuid.uuid4().hex
        ws = websocket.create_connection(wsbase + chan + session)
        rec = {"i": i, "mode": mode}
        if a.handshake:
            ws.send(json.dumps(msg("kernel_info_request", session, {})))
            rec["handshake_reply"], _ = wait_for(
                ws, lambda m: m["header"]["msg_type"] == "kernel_info_reply", a.timeout)
            stats["handshake_lost"] += not rec["handshake_reply"]
        ex = msg("execute_request", session, {"code": "print('x')", "silent": False,
                                              "store_history": False, "user_expressions": {},
                                              "allow_stdin": False, "stop_on_error": True})
        eid = ex["header"]["msg_id"]

        def replied(m):
            return m["header"]["msg_type"] == "execute_reply" and m["parent_header"].get("msg_id") == eid

        ws.send(json.dumps(ex))
        ok, seen = wait_for(ws, replied, a.timeout)
        if not ok:
            rec["state_at_timeout"] = requests.get(a.base + f"api/kernels/{k['id']}", headers=hdr,
                                                   timeout=30).json().get("execution_state")
            rec["seen"] = seen[:12]
            ws.send(json.dumps(msg("kernel_info_request", session, {}, channel="control")))
            rec["released_by_control_msg"], _ = wait_for(ws, replied, 5)
            if not rec["released_by_control_msg"]:
                s2 = uuid.uuid4().hex
                ws2 = websocket.create_connection(wsbase + chan + s2)
                ws2.send(json.dumps(msg("kernel_info_request", s2, {})))
                rec["released_by_other_ws_shell"], _ = wait_for(ws, replied, 5)
                ws2.close()
                if not rec["released_by_other_ws_shell"]:
                    ws.send(json.dumps(msg("kernel_info_request", session, {})))
                    rec["released_by_same_ws_shell"], _ = wait_for(ws, replied, 5)
            print(json.dumps(rec), flush=True)
        stats["ok" if ok else "lost"] += 1
        ws.close()
        requests.delete(a.base + f"api/kernels/{k['id']}", headers=hdr, timeout=60)
    print(json.dumps({"mode": mode, **stats}), flush=True)
    return 0 if stats["lost"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
