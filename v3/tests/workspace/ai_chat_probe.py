#!/usr/bin/env python3
"""One Jupyter AI chat round-trip against a RUNNING workspace server (CONTRACT Phase 5):
opens (creates) a .chat file through jupyterlab-chat's WebSocket (`api/chat/ws/<path>`), sends
one message, and waits for the default persona's complete reply. Prints one JSON line:
{"ok", "reply", "sender", "seconds", ...}. Exit 0 when a persona replied.

Runs anywhere that reaches the server; in the lab, inside the user's own workspace:
  python3 ai_chat_probe.py --base "http://127.0.0.1:8888${JUPYTERHUB_SERVICE_PREFIX}" \
      --token "$JUPYTERHUB_API_TOKEN" --chat tracks/analyst/A1-sql-basics/probe.chat \
      --message "Why can't I create a table in samples?"
`personas` in the output are the persona users the chat document lists; a .chat file keeps
every user that ever joined it, so use a new chat file to see the personas offered now.
Needs `websocket-client` (in the workspace image). Test tool: it never calls a model itself;
whatever answers is the gateway's (use the mock model).
"""
import argparse
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

import websocket  # websocket-client


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--base", required=True, help="server base URL, e.g. http://127.0.0.1:8888/user/alice/")
    p.add_argument("--token", required=True)
    p.add_argument("--chat", required=True, help="chat file path relative to the server root")
    p.add_argument("--message", required=True)
    p.add_argument("--persona", default="jupyter-ai-personas::lakehouse::LabAssistant",
                   help="persona the message is addressed to (the chat input's persona picker "
                        "stamps metadata.to_persona; the lab's default is the Lab Assistant)")
    p.add_argument("--timeout", type=float, default=180)
    p.add_argument("--quiet-s", type=float, default=4.0,
                   help="a reply counts as complete after this long without updates")
    a = p.parse_args(argv)
    base = a.base.rstrip("/") + "/"
    headers = {"Authorization": f"token {a.token}"}

    # The folder must exist (the chat model saves the file there); the file itself is
    # created by the chat server on first save.
    folder = a.chat.rsplit("/", 1)[0] if "/" in a.chat else ""
    if folder:
        url = base + "api/contents/" + urllib.parse.quote(folder)
        try:
            urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=30).read()
        except urllib.error.HTTPError as e:
            if e.code != 404:
                raise
            req = urllib.request.Request(url, method="PUT", data=b'{"type": "directory"}',
                                         headers=dict(headers, **{"Content-Type": "application/json"}))
            urllib.request.urlopen(req, timeout=30).read()

    ws_url = base.replace("http://", "ws://").replace("https://", "wss://") \
        + "api/chat/ws/" + urllib.parse.quote(a.chat)
    t0 = time.time()
    ws = websocket.create_connection(ws_url, header=[f"Authorization: token {a.token}"],
                                     timeout=10)
    first = json.loads(ws.recv())
    if first.get("action") != "connection":
        print(json.dumps({"ok": False, "error": f"unexpected first frame {first.get('action')}"}))
        return 1
    me = first["user"]["username"]
    known = {m.get("id") for m in first.get("messages", [])}
    # The persona manager attaches to a chat when it opens; a message sent before that is
    # never routed. Wait until a persona shows up in the chat's users (max 60 s).
    personas = [u for u in first.get("users", {}) if u.startswith("jupyter-ai-personas::")]
    ws.settimeout(1.0)
    wait_until = time.time() + 60
    while not personas and time.time() < wait_until:
        try:
            frame = json.loads(ws.recv())
        except websocket.WebSocketTimeoutException:
            continue
        if frame.get("action") == "users":
            personas = [u for u in frame.get("users", {}) if u.startswith("jupyter-ai-personas::")]
    msg_id = uuid.uuid4().hex
    ws.send(json.dumps({"type": "client", "action": "send", "id": msg_id, "body": a.message,
                        "metadata": {"to_persona": a.persona}}))

    replies, system_msgs = {}, []
    sent_at = time.time()
    last_update, writing = None, None
    deadline = t0 + a.timeout
    while time.time() < deadline:
        try:
            frame = json.loads(ws.recv())
        except websocket.WebSocketTimeoutException:
            if replies and writing is not True and last_update and time.time() - last_update > a.quiet_s:
                break
            continue
        act = frame.get("action")
        if act == "message":
            m = frame["message"]
            if m.get("id") in known or m.get("id") == msg_id:
                continue
            sender = str(m.get("sender", ""))
            if sender.startswith("jupyter-ai-personas::"):
                replies[m["id"]] = m
                last_update = time.time()
            elif sender != me:
                system_msgs.append({"sender": sender, "body": str(m.get("body"))[:500]})
        elif act == "writing":
            u = (frame.get("user") or {}).get("username", "")
            if u.startswith("jupyter-ai-personas::"):
                writing = bool(frame.get("state"))
                last_update = time.time()
    ws.close()
    if not replies:
        print(json.dumps({"ok": False, "error": "no persona reply", "seconds": round(time.time() - t0, 1),
                          "personas": personas,
                          "system_messages": system_msgs}))
        return 1
    last = sorted(replies.values(), key=lambda m: m.get("time", 0))[-1]
    print(json.dumps({"ok": True, "sender": last.get("sender"), "reply": last.get("body"),
                      "replies": len(replies), "seconds": round(time.time() - t0, 1),
                      "reply_seconds": round(last_update - sent_at, 1), "personas": personas,
                      "chat": a.chat, "system_messages": system_msgs}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
